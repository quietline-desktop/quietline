"""Снимок корня Btrfs перед установкой и откат: подменой `@` из снимка или по журналу изменений.

Снимки лежат в неподключённом подтоме `@snapshots` верхнего уровня (`subvolid=5`), меню GRUB
строит `grub-btrfs` при `grub-mkconfig`. Верх монтируется только во временный каталог
`/run/quietline-top.XXXXXX` и всегда размонтируется. Подтом `@` не удаляется и не назначается
подтомом по умолчанию: откат собирает новый корень рядом, затем переименовывает `@` в
`@broken-<время>`, а новый корень — в `@`.

Общедоступные системные файлы (`/etc/mkinitcpio.conf`, `/proc/*`) читаются через `ctx.root`;
запись, проверки и чтение файлов root (`fstab` внутри верха) — командами под `sudo`.
Файлы домашнего каталога меняются напрямую.
"""

import os
import re
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from quietline_install.runner import Ctx, StepFailed
from quietline_install.runner import read_system_file as _read
from quietline_install.runner import system_path as _local
from quietline_install.runner import write_system_file as _write_system_file

__all__ = ['RootInfo', 'inspect_root', 'snapshot_plan', 'prepare', 'take', 'rollback_btrfs',
           'rollback_home', 'rollback_journal']

HOOK = 'grub-btrfs-overlayfs'
MKINITCPIO = '/etc/mkinitcpio.conf'
GRUB_CFG = '/boot/grub/grub.cfg'
TOP_PREFIX = '/run/quietline-top.'
SYSTEM_PATHS = ('/usr/lib/modules', '/var/lib/pacman')
SNAPSHOT_NAME = re.compile(r'quietline-pre-\d{8}-\d{6}')
_HOOKS_LINE = re.compile(r'^[ \t]*HOOKS=\(([^)]*)\)', re.M)
_FSTAB_ROOT = re.compile(r'^(\s*[^#\s]\S*\s+/\s+btrfs\s+)(\S+)(.*)$')


@dataclass
class RootInfo:
    """Устройство корня.

    `hooks_editable` — `HOOKS` задан в `/etc/mkinitcpio.conf` и не переопределён;
    `system_inside` — `/usr/lib/modules` и `/var/lib/pacman` в том же подтоме, что и `/`.
    """

    fstype: str
    device: str | None
    subvol: str | None
    boot_inside: bool
    systemd_hook: bool
    overlay: bool
    swapfile_in_root: bool
    hooks_editable: bool = True
    system_inside: bool = True


def _stamp() -> str:
    return time.strftime('%Y%m%d-%H%M%S')






def _hooks(text: str | None) -> list[str] | None:
    """Последнее действующее присваивание `HOOKS=(...)`; нет — None."""
    matches = _HOOKS_LINE.findall(text or '')
    return matches[-1].split() if matches else None


def _hooks_in_dropins(ctx: Ctx) -> bool:
    folder = _local(ctx, '/etc/mkinitcpio.conf.d')
    try:
        files = sorted(folder.glob('*.conf'))
    except OSError:
        return False
    return any(re.search(r'^\s*HOOKS\s*[+]?=', path.read_text(encoding='utf-8', errors='replace'), re.M)
               for path in files)


def _cmdline_device(ctx: Ctx) -> str | None:
    match = re.search(r'(?:^|\s)root=UUID=([0-9A-Fa-f-]+)(?:\s|$)', _read(ctx, '/proc/cmdline') or '')
    return f'/dev/disk/by-uuid/{match.group(1)}' if match else None


def _swapfile_in_root(ctx: Ctx, root_source: str) -> bool:
    """Активный файл подкачки лежит в том же подтоме, что и корень."""
    for line in (_read(ctx, '/proc/swaps') or '').splitlines()[1:]:
        fields = line.split()
        if len(fields) < 2 or fields[1] != 'file':
            continue
        path = fields[0].replace('\\040', ' ')
        source = ctx.system.run(['findmnt', '-no', 'SOURCE', '-T', path], check=False).strip()
        if not source or source == root_source:
            return True
    return False


def _same_source(ctx: Ctx, path: str, root_source: str) -> bool:
    return ctx.system.run(['findmnt', '-no', 'SOURCE', '-T', path], check=False).strip() == root_source


def inspect_root(ctx: Ctx) -> RootInfo:
    """Читает устройство корня: `findmnt`, `/etc/mkinitcpio.conf`, `/proc/swaps`, `/proc/cmdline`."""
    line = ctx.system.run(['findmnt', '-no', 'FSTYPE,SOURCE,OPTIONS', '/']).strip().splitlines()
    fields = line[-1].split(None, 2) if line else []
    fstype, source, options = (fields + ['', '', ''])[:3]
    overlay = fstype == 'overlay'
    subvol = next((option[len('subvol='):] for option in options.split(',') if option.startswith('subvol=')),
                  None)
    if overlay:
        device = _cmdline_device(ctx)
    elif fstype == 'btrfs':
        device = source.split('[', 1)[0] or None
    else:
        device = None
    boot = ctx.system.run(['findmnt', '-no', 'SOURCE', '/boot'], check=False).strip()
    system_inside = fstype != 'btrfs' or all(_same_source(ctx, path, source) for path in SYSTEM_PATHS)
    hooks = _hooks(_read(ctx, MKINITCPIO))
    return RootInfo(
        fstype=fstype, device=device, subvol=subvol,
        boot_inside=not boot or boot == source,
        systemd_hook='systemd' in (hooks or []),
        overlay=overlay,
        swapfile_in_root=fstype == 'btrfs' and _swapfile_in_root(ctx, source),
        hooks_editable=hooks is not None and not _hooks_in_dropins(ctx),
        system_inside=system_inside,
    )


def snapshot_plan(info: RootInfo) -> tuple[str, str]:
    """Вид снимка (`btrfs-ro`, `btrfs-rw`, `none`) и ключ текста с причиной."""
    if info.overlay:
        return 'none', 'snapshot.reason.overlay'
    if info.fstype != 'btrfs' or not info.device:
        return 'none', 'snapshot.reason.notBtrfs'
    if info.subvol != '/@':
        return 'none', 'snapshot.reason.subvol'
    if not info.boot_inside:
        return 'none', 'snapshot.reason.bootSeparate'
    if not info.system_inside:
        return 'none', 'snapshot.reason.splitSystem'
    if info.swapfile_in_root:
        return 'none', 'snapshot.reason.swapfile'
    if info.systemd_hook:
        return 'btrfs-rw', 'snapshot.reason.systemdHook'
    if not info.hooks_editable:
        return 'btrfs-rw', 'snapshot.reason.hooksElsewhere'
    return 'btrfs-ro', 'snapshot.reason.ready'




def _installed(ctx: Ctx, package: str) -> bool:
    try:
        ctx.system.run(['pacman', '-Q', package])
        return True
    except subprocess.CalledProcessError:
        return False


def prepare(ctx: Ctx) -> None:
    """Ставит `grub-btrfs` (пункт снимка в меню GRUB); для `btrfs-ro` ещё добавляет хук overlayfs в конец `HOOKS`."""
    kind, reason = snapshot_plan(inspect_root(ctx))
    if kind == 'none':
        raise StepFailed(f'snapshots are not possible here ({reason})')
    new_package = not _installed(ctx, 'grub-btrfs')
    try:
        ctx.system.run(['pacman', '-S', '--needed', '--noconfirm', 'grub-btrfs'], sudo=True)
    except subprocess.CalledProcessError as exc:
        raise StepFailed('could not install grub-btrfs',
                         'The snapshot is taken without a GRUB menu entry.') from exc
    if new_package:
        ctx.record({'kind': 'package', 'name': 'grub-btrfs'})
    if kind != 'btrfs-ro':
        return
    if not _local(ctx, f'/usr/lib/initcpio/install/{HOOK}').exists():
        raise StepFailed(f'the {HOOK} mkinitcpio hook is missing after installing grub-btrfs',
                         'Check the grub-btrfs package, then run ./install.sh again.')
    text = _read(ctx, MKINITCPIO) or ''
    hooks = _hooks(text)
    if hooks is None:
        raise StepFailed(f'no HOOKS line in {MKINITCPIO}', 'Add the default HOOKS line, then run ./install.sh again.')
    if HOOK not in hooks:
        last = list(_HOOKS_LINE.finditer(text))[-1]
        inner = last.group(1).rstrip()
        new = text[:last.start(1)] + inner + (' ' if inner else '') + HOOK + text[last.end(1):]
        backup = f'{MKINITCPIO}.quietline-{_stamp()}'
        ctx.system.run(['cp', '-a', MKINITCPIO, backup], sudo=True)
        ctx.record({'kind': 'file', 'path': MKINITCPIO, 'backup': backup})
        _write_system_file(ctx, MKINITCPIO, new)
    try:
        ctx.system.run(['mkinitcpio', '-P'], sudo=True)
    except subprocess.CalledProcessError as exc:
        _undo_hook(ctx, exc)


def _undo_hook(ctx: Ctx, error: subprocess.CalledProcessError) -> None:
    """`mkinitcpio -P` с хуком не прошёл: возвращает копию `mkinitcpio.conf` и собирает образы заново."""
    backups = [change['backup'] for change in ctx.state.changes
               if change.get('kind') == 'file' and change.get('path') == MKINITCPIO and change.get('backup')]
    ctx.log(f'mkinitcpio -P failed with the {HOOK} hook: {error}')
    if not backups:
        raise StepFailed(f'mkinitcpio -P failed and there is no copy of {MKINITCPIO}',
                         'Fix the HOOKS line, run sudo mkinitcpio -P, then run ./install.sh again.') from error
    backup = backups[-1]
    temp = MKINITCPIO + '.quietline-new'
    try:
        ctx.system.run(['cp', '-a', backup, temp], sudo=True)
        ctx.system.run(['mv', '-f', temp, MKINITCPIO], sudo=True)
        ctx.system.run(['mkinitcpio', '-P'], sudo=True)
    except subprocess.CalledProcessError as exc:
        ctx.log(f'restoring {MKINITCPIO} from {backup} failed: {exc}')
        raise StepFailed(f'mkinitcpio -P failed with the {HOOK} hook, and restoring {MKINITCPIO} from {backup} '
                         f'failed too',
                         f'Run: sudo cp -a {backup} {MKINITCPIO} && sudo mkinitcpio -P, '
                         'then run ./install.sh again.') from exc
    ctx.log(f'{MKINITCPIO} restored from {backup}, initramfs rebuilt without {HOOK}')
    raise StepFailed(f'mkinitcpio -P failed with the {HOOK} hook; {MKINITCPIO} was restored from {backup}',
                     'The installer falls back to a writable snapshot (btrfs-rw).') from error


def _unmount(ctx: Ctx, top: str, strict: bool) -> None:
    """Размонтирует верх и удаляет пустой каталог; при `strict` ошибка — StepFailed, иначе строка журнала."""
    try:
        ctx.system.run(['umount', top], sudo=True)
        ctx.system.run(['rmdir', top], sudo=True)
    except subprocess.CalledProcessError as exc:
        ctx.log(f'could not unmount {top}: {exc}')
        if strict:
            raise StepFailed(f'could not unmount {top}', f'Run: sudo umount {top} && sudo rmdir {top}') from exc


@contextmanager
def _top_level(ctx: Ctx, device: str):
    """Верхний уровень Btrfs (`subvolid=5`) во временном каталоге под `/run`; всегда размонтируется."""
    top = ctx.system.run(['mktemp', '-d', TOP_PREFIX + 'XXXXXX'], sudo=True).strip()
    if not re.fullmatch(re.escape(TOP_PREFIX) + r'[A-Za-z0-9]+', top):
        raise StepFailed(f'unexpected temporary directory: {top!r}')
    try:
        ctx.system.run(['mount', '-o', 'subvolid=5', device, top], sudo=True)
    except BaseException:
        ctx.system.run(['rmdir', top], sudo=True, check=False)
        raise
    try:
        yield top
    except BaseException:
        _unmount(ctx, top, strict=False)
        raise
    _unmount(ctx, top, strict=True)


def _entries(ctx: Ctx, folder: str) -> set[str]:
    return set(ctx.system.run(['ls', '-A', folder], sudo=True).splitlines())


def take(ctx: Ctx, kind: str) -> str:
    """Снимок `@` в `@snapshots/quietline-pre-<время>` (`btrfs-ro` — только для чтения); имя — в состоянии.

    Сбой любой команды снимка — StepFailed: установка без обещанного снимка не продолжается.
    """
    try:
        return _take(ctx, kind)
    except subprocess.CalledProcessError as exc:
        raise StepFailed(f'the root snapshot was not taken: {" ".join(map(str, exc.cmd))} failed',
                         'Fix the cause, then run ./install.sh again: it takes the snapshot before any step.') from exc


def _take(ctx: Ctx, kind: str) -> str:
    if kind not in ('btrfs-ro', 'btrfs-rw'):
        raise ValueError(kind)
    info = inspect_root(ctx)
    plan, reason = snapshot_plan(info)
    if plan == 'none' or (kind == 'btrfs-ro' and plan != 'btrfs-ro'):
        raise StepFailed(f'cannot take a {kind} snapshot here ({reason})')
    name = f'quietline-pre-{_stamp()}'
    with _top_level(ctx, info.device) as top:
        found = _entries(ctx, top)
        if '@' not in found:
            raise StepFailed('subvolume @ is not at the top level of the root filesystem')
        if '@snapshots' not in found:
            ctx.system.run(['btrfs', 'subvolume', 'create', f'{top}/@snapshots'], sudo=True)
        elif name in _entries(ctx, f'{top}/@snapshots'):
            raise StepFailed(f'snapshot {name} already exists', 'Run ./install.sh again in a second.')
        ctx.system.run(['sync'])
        readonly = ['-r'] if kind == 'btrfs-ro' else []
        ctx.system.run(['btrfs', 'subvolume', 'snapshot', *readonly, f'{top}/@', f'{top}/@snapshots/{name}'],
                       sudo=True)
        ctx.state.snapshot = {'kind': kind, 'name': name}
        ctx.state.save()
    try:
        ctx.system.run(['test', '-e', GRUB_CFG], sudo=True)
    except subprocess.CalledProcessError:
        ctx.log(f'{GRUB_CFG} not found: the snapshot is not added to the GRUB menu')
        return name
    try:
        ctx.system.run(['grub-mkconfig', '-o', GRUB_CFG], sudo=True)
    except subprocess.CalledProcessError as exc:
        ctx.log(f'grub-mkconfig failed, the snapshot is not in the GRUB menu yet: {exc}')
    return name


def _strip_root_subvolid(fstab: str) -> str:
    """Убирает `subvolid=N` из параметров строки `/`; без `subvol=` добавляет `subvol=/@`."""
    lines = []
    for line in fstab.splitlines(keepends=True):
        body = line.rstrip('\n')
        match = _FSTAB_ROOT.match(body)
        if match:
            options = [option for option in match.group(2).split(',') if not option.startswith('subvolid=')]
            if not any(option.startswith('subvol=') for option in options):
                options.append('subvol=/@')
            line = match.group(1) + ','.join(options) + match.group(3) + line[len(body):]
        lines.append(line)
    return ''.join(lines)


def _swap_roots(ctx: Ctx, top: str, device: str, new: str, broken: str, has_root: bool) -> None:
    """Ставит готовый `new` на место `@`, старый `@` — в `broken`; при сбое возвращает `@` назад."""
    if has_root:
        try:
            ctx.system.run(['mv', '-T', f'{top}/@', f'{top}/{broken}'], sudo=True)
        except subprocess.CalledProcessError as exc:
            ctx.log(f'rollback: moving @ to {broken} failed: {exc}')
            raise StepFailed(f'could not move @ aside; @ was not changed, the new root is left as {new}',
                             'See the install log.') from exc
    try:
        ctx.system.run(['mv', '-T', f'{top}/{new}', f'{top}/@'], sudo=True)
        return
    except subprocess.CalledProcessError as exc:
        ctx.log(f'rollback: moving {new} to @ failed: {exc}')
        failure = exc
    if not has_root:
        raise StepFailed(f'could not move {new} to @; there is no @ now',
                         f'From a live system: sudo mount -o subvolid=5 {device} /mnt && '
                         f'sudo mv -T /mnt/{new} /mnt/@') from failure
    try:
        ctx.system.run(['mv', '-T', f'{top}/{broken}', f'{top}/@'], sudo=True)
    except subprocess.CalledProcessError as exc:
        ctx.log(f'rollback: moving {broken} back to @ failed: {exc}')
        raise StepFailed(f'could not move {new} to @, and could not move the old root {broken} back to @; '
                         'there is no @ now',
                         f'Before rebooting: sudo mount -o subvolid=5 {device} /mnt && '
                         f'sudo mv -T /mnt/{broken} /mnt/@') from exc
    ctx.log(f'rollback: old root moved back from {broken} to @')
    raise StepFailed(f'could not move {new} to @; the old root is back as @, the new root is left as {new}',
                     'See the install log.') from failure


def rollback_btrfs(ctx: Ctx, name: str) -> str:
    """Собирает новый корень из снимка `name` рядом с `@`, затем подменяет `@`; возвращает имя старого `@`.

    Пока новый корень (`@rollback-new-<время>` с исправленным `fstab`) не готов, `@` не меняется.
    Подмена — два переименования подряд; результат сразу пишется в `state.snapshot`.
    Затем возвращаются файлы домашнего каталога.
    """
    if not isinstance(name, str) or not SNAPSHOT_NAME.fullmatch(name):
        raise StepFailed(f'not a Quietline snapshot name: {name!r}')
    info = inspect_root(ctx)
    if not info.device or not (info.overlay or (info.fstype == 'btrfs' and info.subvol == '/@')):
        raise StepFailed('the root filesystem is not Btrfs with the @ subvolume')
    stamp = _stamp()
    new, broken = f'@rollback-new-{stamp}', f'@broken-{stamp}'
    swapped = False
    errors = []
    action = 'Reboot to use the restored root; see the install log.'
    try:
        with _top_level(ctx, info.device) as top:
            source = f'{top}/@snapshots/{name}'
            try:
                ctx.system.run(['btrfs', 'subvolume', 'show', source], sudo=True)
            except subprocess.CalledProcessError:
                raise StepFailed(f'snapshot {name} not found', 'Nothing was changed.') from None
            found = _entries(ctx, top)
            if new in found or broken in found:
                raise StepFailed(f'{new} or {broken} already exists', 'Run the rollback again in a second.')
            try:
                ctx.system.run(['btrfs', 'subvolume', 'snapshot', source, f'{top}/{new}'], sudo=True)
            except subprocess.CalledProcessError as exc:
                raise StepFailed(f'could not create {new} from {name}; @ was not changed',
                                 'See the install log.') from exc
            try:
                fstab = f'{top}/{new}/etc/fstab'
                text = ctx.system.run(['cat', fstab], sudo=True)
                fixed = _strip_root_subvolid(text)
                if fixed != text:
                    _write_system_file(ctx, fstab, fixed)
            except subprocess.CalledProcessError as exc:
                raise StepFailed(f'could not fix /etc/fstab in {new}; @ was not changed, {new} is left in place',
                                 'See the install log.') from exc
            _swap_roots(ctx, top, info.device, new, broken, '@' in found)
            swapped = True
            ctx.state.snapshot = {**(ctx.state.snapshot or {}), 'rolledBackTo': name, 'broken': broken}
            ctx.state.save()
            ctx.log(f'rollback: @ replaced with a copy of {name}, old root kept as {broken}')
            ctx.system.run(['sync'], check=False)
    except StepFailed as exc:
        if not swapped:
            raise
        errors.append(str(exc))
        action = exc.action or action
    try:
        rollback_home(ctx)
    except StepFailed as exc:
        errors.append(str(exc))
    if errors:
        raise StepFailed(f'the root was replaced with a copy of {name} (old root kept as {broken}), but: '
                         + '; '.join(errors), action)
    return broken


def _in_home(ctx: Ctx, path: str) -> bool:
    return Path(path).is_relative_to(ctx.home)


def _restore_home_file(ctx: Ctx, path: str, backup: str | None) -> None:
    """Возвращает копию или удаляет созданный файл; непустой каталог и чужие данные не трогает."""
    target = Path(path)
    if backup:
        if not os.path.lexists(backup):
            ctx.log(f'rollback: backup {backup} is missing, {path} left as is')
        elif target.is_dir() and not target.is_symlink():
            ctx.log(f'rollback: {path} is a directory, backup {backup} left in place')
        else:
            os.replace(backup, target)
        return
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.is_dir():
        try:
            target.rmdir()
        except OSError:
            ctx.log(f'rollback: {path} is not empty, left in place')


def rollback_home(ctx: Ctx) -> None:
    """Файлы домашнего каталога из журнала, в обратном порядке: копия возвращается, созданный удаляется.

    Сбой одной записи не останавливает остальные; все сбои — в одном StepFailed в конце.
    """
    failures = []
    for change in reversed(ctx.state.changes):
        if change.get('kind') == 'file' and _in_home(ctx, change['path']):
            try:
                _restore_home_file(ctx, change['path'], change.get('backup'))
            except OSError as exc:
                ctx.log(f'rollback: {change["path"]} failed: {exc}')
                failures.append(change['path'])
    if failures:
        raise StepFailed(f'{len(failures)} file(s) in the home folder were not restored: {", ".join(failures)}',
                         'See the install log.')


def _restore_system_file(ctx: Ctx, path: str, backup: str | None) -> None:
    if backup:
        try:
            ctx.system.run(['test', '-e', backup], sudo=True)
        except subprocess.CalledProcessError:
            ctx.log(f'rollback: backup {backup} is missing, {path} left as is')
            return
        ctx.system.run(['mv', '-fT', backup, path], sudo=True)
    else:
        ctx.system.run(['rm', '-f', path], sudo=True)


def rollback_journal(ctx: Ctx) -> None:
    """Откат по журналу без снимка: файлы, оболочка входа, службы, Flatpak, меню GRUB, затем один `pacman -Rns` новых пакетов."""
    failures = []
    packages = []
    for change in reversed(ctx.state.changes):
        kind = change.get('kind')
        try:
            if kind == 'file':
                if _in_home(ctx, change['path']):
                    _restore_home_file(ctx, change['path'], change.get('backup'))
                else:
                    _restore_system_file(ctx, change['path'], change.get('backup'))
            elif kind == 'shell':
                ctx.system.run(['chsh', '-s', change['previous']], interactive=True)
            elif kind == 'service':
                ctx.system.run(['systemctl', 'disable', change['unit']], sudo=True)
            elif kind == 'flatpak':
                ctx.system.run(['flatpak', 'uninstall', '--user', '-y', change['id']])
            elif kind == 'grub':
                # Запись стоит в журнале перед копией /etc/default/grub: файл к этому моменту уже возвращён.
                ctx.system.run(['grub-mkconfig', '-o', '/boot/grub/grub.cfg'], sudo=True, interactive=True)
            elif kind == 'package' and change['name'] not in packages:
                packages.append(change['name'])
        except (OSError, subprocess.CalledProcessError) as exc:
            ctx.log(f'rollback: {change} failed: {exc}')
            failures.append(change)
    if packages:
        present = set(ctx.system.run(['pacman', '-Qq', *packages], check=False).split())
        packages = [package for package in packages if package in present]
    if packages:
        try:
            ctx.system.run(['pacman', '-Rns', *packages], sudo=True, interactive=True)
        except subprocess.CalledProcessError as exc:
            ctx.log(f'rollback: pacman -Rns failed: {exc}')
            failures.append({'kind': 'package', 'name': ' '.join(packages)})
    if failures:
        raise StepFailed(f'rollback incomplete: {len(failures)} change(s) were not undone',
                         'See the install log for each one.')
