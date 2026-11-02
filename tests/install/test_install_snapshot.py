import re
import subprocess
from pathlib import Path

import pytest

from quietline_install import snapshot
from quietline_install.runner import State, StepFailed
from quietline_install.texts import TEXTS

TOP = '/run/quietline-top.abc123'
SOURCE = '/dev/nvme0n1p5'
HOOKS = 'base udev autodetect microcode modconf kms keyboard keymap consolefont block filesystems fsck'
SWAPS_HEADER = 'Filename\t\t\t\tType\t\tSize\t\tUsed\t\tPriority\n'
FSTAB = ('# /dev/nvme0n1p5\n'
         'UUID=x / btrfs rw,noatime,subvolid=256,subvol=/@ 0 0\n'
         '\n'
         'UUID=x /home btrfs rw,noatime,subvolid=257,subvol=/@home 0 0\n'
         'UUID=e /efi vfat rw,relatime 0 2\n')
NAME = 'quietline-pre-20261028-101500'


def make_root(ctx, system, tmp_path, fstype='btrfs', subvol='/@', boot='', hooks=HOOKS, swaps='',
              cmdline='BOOT_IMAGE=/@/boot/vmlinuz-linux root=UUID=abcd rw rootflags=subvol=@\n',
              modules=None, pacman_db=None):
    """Корень системы: ответы findmnt и файлы /etc, /proc во временном ctx.root."""
    ctx.root = tmp_path / 'root'
    (ctx.root / 'etc').mkdir(parents=True, exist_ok=True)
    (ctx.root / 'proc').mkdir(exist_ok=True)
    (ctx.root / 'usr/lib/initcpio/install').mkdir(parents=True, exist_ok=True)
    (ctx.root / 'usr/lib/initcpio/install/grub-btrfs-overlayfs').write_text('')
    if hooks is not None:
        (ctx.root / 'etc/mkinitcpio.conf').write_text(
            '# vim:set ft=sh\nMODULES=()\n#    HOOKS=(base systemd)\nHOOKS=(' + hooks + ')\nCOMPRESSION="zstd"\n')
    (ctx.root / 'proc/swaps').write_text(SWAPS_HEADER + swaps)
    (ctx.root / 'proc/cmdline').write_text(cmdline)
    if fstype == 'btrfs':
        line = f'btrfs {SOURCE}[{subvol}] rw,noatime,compress=zstd:3,ssd,subvolid=256,subvol={subvol}\n'
    elif fstype == 'overlay':
        line = 'overlay overlay rw,relatime,lowerdir=/run/rootfsbase,upperdir=/run/cow/upper\n'
    else:
        line = f'{fstype} /dev/sda2 rw,relatime\n'
    system.answer(['findmnt', '-no', 'FSTYPE,SOURCE,OPTIONS', '/'], line)
    system.answer(['findmnt', '-no', 'SOURCE', '/boot'], boot, 1 if not boot else 0)
    system.answer(['findmnt', '-no', 'SOURCE', '-T'], line.split()[1] + '\n')
    if modules is not None:
        system.answer(['findmnt', '-no', 'SOURCE', '-T', '/usr/lib/modules'], modules)
    if pacman_db is not None:
        system.answer(['findmnt', '-no', 'SOURCE', '-T', '/var/lib/pacman'], pacman_db)
    system.answer(['mktemp'], TOP + '\n')
    system.answer(['ls', '-A', TOP], '@\n@home\n@log\n@pkg\n@snapshots\n')


@pytest.mark.parametrize(('layout', 'kind', 'reason'), [
    ({}, 'btrfs-ro', 'snapshot.reason.ready'),
    ({'hooks': 'base systemd autodetect microcode modconf kms keyboard sd-vconsole block filesystems fsck'},
     'btrfs-rw', 'snapshot.reason.systemdHook'),
    ({'hooks': None}, 'btrfs-rw', 'snapshot.reason.hooksElsewhere'),
    ({'fstype': 'ext4'}, 'none', 'snapshot.reason.notBtrfs'),
    ({'boot': '/dev/nvme0n1p6\n'}, 'none', 'snapshot.reason.bootSeparate'),
    ({'boot': f'{SOURCE}[/@]\n'}, 'btrfs-ro', 'snapshot.reason.ready'),
    ({'modules': f'{SOURCE}[/@modules]\n'}, 'none', 'snapshot.reason.splitSystem'),
    ({'pacman_db': '/dev/nvme0n1p9\n'}, 'none', 'snapshot.reason.splitSystem'),
    ({'subvol': '/'}, 'none', 'snapshot.reason.subvol'),
    ({'fstype': 'overlay'}, 'none', 'snapshot.reason.overlay'),
    ({'swaps': '/swapfile\t\t\t\tfile\t\t8388604\t\t0\t\t-2\n'}, 'none', 'snapshot.reason.swapfile'),
])
def test_snapshot_plan_follows_root_layout(ctx, system, tmp_path, layout, kind, reason):
    make_root(ctx, system, tmp_path, **layout)
    info = snapshot.inspect_root(ctx)
    assert snapshot.snapshot_plan(info) == (kind, reason)
    assert reason in TEXTS['ru'] and reason in TEXTS['en']


def test_root_info_reads_device_and_layout(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path)
    info = snapshot.inspect_root(ctx)
    assert (info.fstype, info.device, info.subvol, info.boot_inside) == ('btrfs', SOURCE, '/@', True)
    assert not (info.systemd_hook or info.overlay or info.swapfile_in_root)


def test_swap_partition_and_swapfile_in_own_subvolume_do_not_block_snapshot(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path, swaps='/dev/nvme0n1p7\t\t\t\tpartition\t8388604\t\t0\t\t-2\n'
                                           '/swap/swapfile\t\t\t\tfile\t\t8388604\t\t0\t\t-3\n')
    system.answer(['findmnt', '-no', 'SOURCE', '-T', '/swap/swapfile'], f'{SOURCE}[/@swap]\n')
    assert snapshot.snapshot_plan(snapshot.inspect_root(ctx))[0] == 'btrfs-ro'


def test_booted_snapshot_takes_device_from_kernel_cmdline(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path, fstype='overlay',
              cmdline='BOOT_IMAGE=/@snapshots/x/boot/vmlinuz-linux root=UUID=1234-ab rw rootflags=subvol=@snapshots/x\n')
    info = snapshot.inspect_root(ctx)
    assert info.overlay and info.device == '/dev/disk/by-uuid/1234-ab'


STAMP = '20261028-120000'
MK = '/etc/mkinitcpio.conf'
NEW = f'@rollback-new-{STAMP}'
BROKEN = f'@broken-{STAMP}'
INSPECT = [(['findmnt', '-no', 'FSTYPE,SOURCE,OPTIONS', '/'], False),
           (['findmnt', '-no', 'SOURCE', '/boot'], False),
           (['findmnt', '-no', 'SOURCE', '-T', '/usr/lib/modules'], False),
           (['findmnt', '-no', 'SOURCE', '-T', '/var/lib/pacman'], False)]
MOUNT = [(['mktemp', '-d', '/run/quietline-top.XXXXXX'], True),
         (['mount', '-o', 'subvolid=5', SOURCE, TOP], True)]
UNMOUNT = [(['umount', TOP], True), (['rmdir', TOP], True)]
ROLLBACK_START = INSPECT + MOUNT + [(['btrfs', 'subvolume', 'show', f'{TOP}/@snapshots/{NAME}'], True),
                                    (['ls', '-A', TOP], True),
                                    (['btrfs', 'subvolume', 'snapshot', f'{TOP}/@snapshots/{NAME}', f'{TOP}/{NEW}'],
                                     True)]
FSTAB_FIX = [(['cat', f'{TOP}/{NEW}/etc/fstab'], True),
             (['tee', f'{TOP}/{NEW}/etc/fstab.quietline-new'], True),
             (['chmod', '0644', f'{TOP}/{NEW}/etc/fstab.quietline-new'], True),
             (['mv', '-f', f'{TOP}/{NEW}/etc/fstab.quietline-new', f'{TOP}/{NEW}/etc/fstab'], True)]
TO_BROKEN = (['mv', '-T', f'{TOP}/@', f'{TOP}/{BROKEN}'], True)
TO_ROOT = (['mv', '-T', f'{TOP}/{NEW}', f'{TOP}/@'], True)
BACK = (['mv', '-T', f'{TOP}/{BROKEN}', f'{TOP}/@'], True)


@pytest.fixture(autouse=True)
def fixed_time(monkeypatch):
    monkeypatch.setattr(snapshot, '_stamp', lambda: STAMP)


def calls(system):
    return [(call['args'], call['sudo']) for call in system.calls]


def no_sync(arg):
    return not re.fullmatch(r'-[A-Za-z]*y[A-Za-z]*', arg) and arg != '--refresh'


def test_prepare_adds_hook_once_and_never_syncs_databases(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path)
    conf = ctx.root / 'etc/mkinitcpio.conf'
    snapshot.prepare(ctx)
    assert calls(system) == INSPECT + [
        (['pacman', '-Q', 'grub-btrfs'], False),
        (['pacman', '-S', '--needed', '--noconfirm', 'grub-btrfs'], True),
        (['cp', '-a', MK, f'{MK}.quietline-{STAMP}'], True),
        (['tee', f'{MK}.quietline-new'], True),
        (['chmod', '0644', f'{MK}.quietline-new'], True),
        (['mv', '-f', f'{MK}.quietline-new', MK], True),
        (['mkinitcpio', '-P'], True)]
    assert all(no_sync(arg) for args in system.commands() if args[0] == 'pacman' for arg in args)
    new = next(call['input'] for call in system.calls if call['args'][0] == 'tee')
    assert re.search(r'^HOOKS=\(' + HOOKS + r' grub-btrfs-overlayfs\)$', new, re.M)
    assert '#    HOOKS=(base systemd)' in new
    assert ctx.state.changes == [{'kind': 'file', 'path': MK, 'backup': f'{MK}.quietline-{STAMP}'}]
    conf.write_text(new)

    system.calls.clear()
    snapshot.prepare(ctx)
    assert calls(system) == INSPECT + [
        (['pacman', '-Q', 'grub-btrfs'], False),
        (['pacman', '-S', '--needed', '--noconfirm', 'grub-btrfs'], True),
        (['mkinitcpio', '-P'], True)]
    assert conf.read_text().count('grub-btrfs-overlayfs') == 1


def test_prepare_adds_hook_to_multiline_hooks(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path, hooks='base udev\n       autodetect block\n       filesystems fsck')
    assert snapshot.snapshot_plan(snapshot.inspect_root(ctx))[0] == 'btrfs-ro'
    snapshot.prepare(ctx)
    new = next(call['input'] for call in system.calls if call['args'][0] == 'tee')
    assert 'HOOKS=(base udev\n       autodetect block\n       filesystems fsck grub-btrfs-overlayfs)\n' in new


def test_multiline_hooks_with_systemd_give_writable_snapshot(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path, hooks='base\n  systemd\n  block filesystems')
    assert snapshot.snapshot_plan(snapshot.inspect_root(ctx)) == ('btrfs-rw', 'snapshot.reason.systemdHook')


def test_dropin_hooks_override_gives_writable_snapshot(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path)
    (ctx.root / 'etc/mkinitcpio.conf.d').mkdir()
    (ctx.root / 'etc/mkinitcpio.conf.d/10-hooks.conf').write_text('HOOKS=(base udev block filesystems)\n')
    assert snapshot.snapshot_plan(snapshot.inspect_root(ctx)) == ('btrfs-rw', 'snapshot.reason.hooksElsewhere')
    snapshot.prepare(ctx)
    commands = [call['args'] for call in system.calls]
    assert ['pacman', '-S', '--needed', '--noconfirm', 'grub-btrfs'] in commands
    assert not any(command[:1] in (['mkinitcpio'], ['tee'], ['cp']) for command in commands)


def test_failed_mkinitcpio_restores_config_and_rebuilds(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path)
    run = system.run
    attempts = []

    def flaky(args, **kwargs):
        if args == ['mkinitcpio', '-P'] and not attempts:
            attempts.append(args)
            system.calls.append({'args': list(args), 'sudo': kwargs.get('sudo', False), 'input': None})
            raise subprocess.CalledProcessError(1, args)
        return run(args, **kwargs)

    system.run = flaky
    with pytest.raises(StepFailed) as failed:
        snapshot.prepare(ctx)
    backup = f'{MK}.quietline-{STAMP}'
    assert calls(system)[-4:] == [(['mkinitcpio', '-P'], True),
                                  (['cp', '-a', backup, f'{MK}.quietline-new'], True),
                                  (['mv', '-f', f'{MK}.quietline-new', MK], True),
                                  (['mkinitcpio', '-P'], True)]
    assert backup in str(failed.value) and 'btrfs-rw' in failed.value.action


def test_snapshot_commands_use_top_level_and_regenerate_grub(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path)
    system.answer(['ls', '-A', TOP], '@\n@home\n@log\n@pkg\n')
    name = snapshot.take(ctx, 'btrfs-ro')
    assert name == f'quietline-pre-{STAMP}'
    assert calls(system) == INSPECT + MOUNT + [
        (['ls', '-A', TOP], True),
        (['btrfs', 'subvolume', 'create', f'{TOP}/@snapshots'], True),
        (['sync'], False),
        (['btrfs', 'subvolume', 'snapshot', '-r', f'{TOP}/@', f'{TOP}/@snapshots/{name}'], True),
    ] + UNMOUNT + [
        (['test', '-e', '/boot/grub/grub.cfg'], True),
        (['grub-mkconfig', '-o', '/boot/grub/grub.cfg'], True)]
    assert ctx.state.snapshot == {'kind': 'btrfs-ro', 'name': name}
    assert State.load(ctx.state.path).snapshot == {'kind': 'btrfs-ro', 'name': name}


def test_writable_snapshot_and_existing_snapshots_subvolume(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path, hooks='base systemd block filesystems fsck')
    name = snapshot.take(ctx, 'btrfs-rw')
    assert calls(system) == INSPECT + MOUNT + [
        (['ls', '-A', TOP], True),
        (['ls', '-A', f'{TOP}/@snapshots'], True),
        (['sync'], False),
        (['btrfs', 'subvolume', 'snapshot', f'{TOP}/@', f'{TOP}/@snapshots/{name}'], True),
    ] + UNMOUNT + [
        (['test', '-e', '/boot/grub/grub.cfg'], True),
        (['grub-mkconfig', '-o', '/boot/grub/grub.cfg'], True)]


def test_snapshot_unmounts_after_failure(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path)
    system.answer(['btrfs', 'subvolume', 'snapshot'], code=1)
    with pytest.raises(StepFailed, match='snapshot was not taken'):
        snapshot.take(ctx, 'btrfs-ro')
    assert calls(system) == INSPECT + MOUNT + [
        (['ls', '-A', TOP], True),
        (['ls', '-A', f'{TOP}/@snapshots'], True),
        (['sync'], False),
        (['btrfs', 'subvolume', 'snapshot', '-r', f'{TOP}/@', f'{TOP}/@snapshots/quietline-pre-{STAMP}'], True),
    ] + UNMOUNT
    assert ctx.state.snapshot is None


@pytest.mark.parametrize('layout', [{'fstype': 'ext4'}, {'boot': '/dev/nvme0n1p6\n'}, {'fstype': 'overlay'}])
def test_snapshot_refuses_unsupported_root(ctx, system, tmp_path, layout):
    make_root(ctx, system, tmp_path, **layout)
    with pytest.raises(StepFailed):
        snapshot.take(ctx, 'btrfs-rw')
    assert not [args for args in system.commands() if args[0] in ('mount', 'btrfs', 'mktemp')]


def test_btrfs_rollback_commands(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path)
    system.answer(['cat', f'{TOP}/{NEW}/etc/fstab'], FSTAB)
    assert snapshot.rollback_btrfs(ctx, NAME) == BROKEN
    assert calls(system) == ROLLBACK_START + FSTAB_FIX + [TO_BROKEN, TO_ROOT, (['sync'], False)] + UNMOUNT
    written = next(call['input'] for call in system.calls if call['args'][0] == 'tee')
    assert 'UUID=x / btrfs rw,noatime,subvol=/@ 0 0\n' in written
    assert 'UUID=x /home btrfs rw,noatime,subvolid=257,subvol=/@home 0 0\n' in written
    assert written == FSTAB.replace('subvolid=256,', '')
    assert ctx.state.snapshot == {'rolledBackTo': NAME, 'broken': BROKEN}
    assert State.load(ctx.state.path).snapshot == {'rolledBackTo': NAME, 'broken': BROKEN}


def test_rollback_refuses_missing_snapshot(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path)
    system.answer(['btrfs', 'subvolume', 'show', f'{TOP}/@snapshots/{NAME}'], code=1)
    with pytest.raises(StepFailed):
        snapshot.rollback_btrfs(ctx, NAME)
    assert calls(system) == INSPECT + MOUNT + [
        (['btrfs', 'subvolume', 'show', f'{TOP}/@snapshots/{NAME}'], True)] + UNMOUNT


@pytest.mark.parametrize('name', ['../@', '@', 'quietline-pre-x', f'{NAME}/..', ''])
def test_rollback_refuses_foreign_snapshot_names(ctx, system, tmp_path, name):
    make_root(ctx, system, tmp_path)
    with pytest.raises(StepFailed):
        snapshot.rollback_btrfs(ctx, name)
    assert system.calls == []


def test_rollback_leaves_root_alone_when_new_root_cannot_be_built(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path)
    system.answer(['btrfs', 'subvolume', 'snapshot'], code=1)
    with pytest.raises(StepFailed) as failed:
        snapshot.rollback_btrfs(ctx, NAME)
    assert calls(system) == ROLLBACK_START + UNMOUNT
    assert NEW in str(failed.value) and '@ was not changed' in str(failed.value)
    assert ctx.state.snapshot is None


def test_rollback_leaves_root_alone_when_fstab_fix_fails(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path)
    system.answer(['cat', f'{TOP}/{NEW}/etc/fstab'], code=1)
    with pytest.raises(StepFailed) as failed:
        snapshot.rollback_btrfs(ctx, NAME)
    assert calls(system) == ROLLBACK_START + FSTAB_FIX[:1] + UNMOUNT
    assert NEW in str(failed.value) and '@ was not changed' in str(failed.value)


def test_rollback_moves_old_root_back_when_new_root_cannot_take_its_place(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path)
    system.answer(['cat', f'{TOP}/{NEW}/etc/fstab'], FSTAB)
    system.answer(['mv', '-T', f'{TOP}/{NEW}'], code=1)
    lines = []
    ctx.log = lines.append
    with pytest.raises(StepFailed) as failed:
        snapshot.rollback_btrfs(ctx, NAME)
    assert calls(system) == ROLLBACK_START + FSTAB_FIX + [TO_BROKEN, TO_ROOT, BACK] + UNMOUNT
    assert NEW in str(failed.value) and 'old root is back' in str(failed.value)
    assert any('moved back' in line for line in lines)
    assert ctx.state.snapshot is None


def test_rollback_names_both_subvolumes_when_move_back_fails(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path)
    system.answer(['cat', f'{TOP}/{NEW}/etc/fstab'], FSTAB)
    system.answer(['mv', '-T', f'{TOP}/{NEW}'], code=1)
    system.answer(['mv', '-T', f'{TOP}/{BROKEN}'], code=1)
    lines = []
    ctx.log = lines.append
    with pytest.raises(StepFailed) as failed:
        snapshot.rollback_btrfs(ctx, NAME)
    assert calls(system) == ROLLBACK_START + FSTAB_FIX + [TO_BROKEN, TO_ROOT, BACK] + UNMOUNT
    message = str(failed.value)
    assert NEW in message and BROKEN in message
    assert f'sudo mv -T /mnt/{BROKEN} /mnt/@' in failed.value.action
    assert f'sudo mount -o subvolid=5 {SOURCE} /mnt' in failed.value.action
    assert any(BROKEN in line and 'failed' in line for line in lines)


def test_rollback_reports_replaced_root_when_unmount_fails(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path)
    system.answer(['cat', f'{TOP}/{NEW}/etc/fstab'], FSTAB)
    system.answer(['umount'], code=1)
    created = ctx.home / 'created.txt'
    created.write_text('x')
    ctx.record({'kind': 'file', 'path': str(created), 'backup': None})
    with pytest.raises(StepFailed) as failed:
        snapshot.rollback_btrfs(ctx, NAME)
    assert f'replaced with a copy of {NAME}' in str(failed.value) and BROKEN in str(failed.value)
    assert f'sudo umount {TOP}' in failed.value.action
    assert State.load(ctx.state.path).snapshot == {'rolledBackTo': NAME, 'broken': BROKEN}
    assert not created.exists()


def test_rollback_from_booted_snapshot_uses_cmdline_device(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path, fstype='overlay',
              cmdline='root=UUID=1234-ab rw rootflags=subvol=@snapshots/x\n')
    system.answer(['cat', f'{TOP}/{NEW}/etc/fstab'], FSTAB)
    snapshot.rollback_btrfs(ctx, NAME)
    assert ['mount', '-o', 'subvolid=5', '/dev/disk/by-uuid/1234-ab', TOP] in system.commands()


@pytest.mark.parametrize(('before', 'after'), [
    ('UUID=x\t/\tbtrfs\trw,noatime,subvolid=256,subvol=/@\t0 0\n', 'UUID=x\t/\tbtrfs\trw,noatime,subvol=/@\t0 0\n'),
    ('UUID=x / btrfs rw,subvolid=256,subvol=@ 0 0\n', 'UUID=x / btrfs rw,subvol=@ 0 0\n'),
    ('UUID=x / btrfs subvolid=256,subvol=/@,rw 0 0\n', 'UUID=x / btrfs subvol=/@,rw 0 0\n'),
    ('UUID=x / btrfs subvolid=256 0 0\n', 'UUID=x / btrfs subvol=/@ 0 0\n'),
    ('#UUID=x / btrfs rw,subvolid=256,subvol=/@ 0 0\n', '#UUID=x / btrfs rw,subvolid=256,subvol=/@ 0 0\n'),
    ('  # UUID=x / btrfs subvolid=256 0 0\n', '  # UUID=x / btrfs subvolid=256 0 0\n'),
    ('UUID=x / btrfs rw,subvolid=256,subvol=/@ 0 0', 'UUID=x / btrfs rw,subvol=/@ 0 0'),
    ('UUID=x /home btrfs rw,subvolid=257,subvol=/@home 0 0\n', 'UUID=x /home btrfs rw,subvolid=257,subvol=/@home 0 0\n'),
])
def test_fstab_root_line_loses_only_subvolid(before, after):
    assert snapshot._strip_root_subvolid(before) == after


def test_home_rollback_reports_every_failure(ctx):
    broken = ctx.home / 'a.conf'
    broken.write_text('new')
    (ctx.home / 'a.conf.quietline-1').mkdir()
    (ctx.home / 'a.conf.quietline-1/x').write_text('')
    created = ctx.home / 'b.conf'
    created.write_text('new')
    ctx.record({'kind': 'file', 'path': str(broken), 'backup': str(ctx.home / 'a.conf.quietline-1')})
    ctx.record({'kind': 'file', 'path': str(created), 'backup': None})
    with pytest.raises(StepFailed) as failed:
        snapshot.rollback_home(ctx)
    assert str(broken) in str(failed.value)
    assert not created.exists()


def test_rollback_restores_home_files_and_removes_created(ctx, system, tmp_path):
    home = ctx.home
    changed = home / '.config/fish/config.fish'
    changed.parent.mkdir(parents=True)
    changed.write_text('new')
    backup = home / '.config/fish/config.fish.quietline-20261028-101500'
    backup.write_text('old')
    created = home / '.config/quietline/pins.json'
    created.parent.mkdir(parents=True)
    created.write_text('[]')
    link = home / '.config/quickshell/quietline'
    link.parent.mkdir(parents=True)
    link.symlink_to('/usr/share/quietline/shell')
    music = home / 'Music'
    music.mkdir()
    (music / 'song.flac').write_text('data')
    for change in [{'kind': 'file', 'path': str(changed), 'backup': str(backup)},
                   {'kind': 'file', 'path': str(created), 'backup': None},
                   {'kind': 'file', 'path': str(link), 'backup': None},
                   {'kind': 'file', 'path': str(music), 'backup': None},
                   {'kind': 'file', 'path': '/etc/locale.gen', 'backup': '/etc/locale.gen.quietline-1'},
                   {'kind': 'package', 'name': 'fnm'}]:
        ctx.record(change)
    snapshot.rollback_home(ctx)
    assert changed.read_text() == 'old' and not backup.exists()
    assert not created.exists() and not link.is_symlink()
    assert (music / 'song.flac').read_text() == 'data'
    assert system.calls == []
    snapshot.rollback_home(ctx)
    assert changed.read_text() == 'old'


def test_btrfs_rollback_also_restores_home(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path)
    system.answer(['cat', f'{TOP}/{NEW}/etc/fstab'], FSTAB)
    created = ctx.home / '.config/quietline/region.json'
    created.parent.mkdir(parents=True)
    created.write_text('{}')
    ctx.record({'kind': 'file', 'path': str(created), 'backup': None})
    snapshot.rollback_btrfs(ctx, NAME)
    assert not created.exists()


def test_journal_rollback_keeps_preexisting_packages(ctx, system, tmp_path):
    ctx.root = tmp_path / 'root'
    config = ctx.home / '.config/hypr/hyprland.lua'
    config.parent.mkdir(parents=True)
    config.write_text('quietline')
    config.with_name('hyprland.lua.quietline-20261028-101500').write_text('mine')
    for change in [{'kind': 'package', 'name': 'hyprland'},
                   {'kind': 'file', 'path': '/etc/locale.gen', 'backup': '/etc/locale.gen.quietline-20261028-101500'},
                   {'kind': 'file', 'path': '/etc/greetd/quietline.toml', 'backup': None},
                   {'kind': 'service', 'unit': 'greetd.service'},
                   {'kind': 'package', 'name': 'fnm'},
                   {'kind': 'flatpak', 'id': 'com.brave.Browser'},
                   {'kind': 'file', 'path': str(config), 'backup': str(config) + '.quietline-20261028-101500'},
                   {'kind': 'package', 'name': 'slack-desktop'},
                   {'kind': 'package', 'name': 'fnm'}]:
        ctx.record(change)
    system.answer(['pacman', '-Qq'], 'hyprland\nfnm\n', 1)
    snapshot.rollback_journal(ctx)
    commands = system.commands()
    removals = [call for call in system.calls if call['args'][:2] == ['pacman', '-Rns']]
    assert len(removals) == 1 and removals[0]['sudo']
    assert removals[0]['args'][2:] == ['fnm', 'hyprland']
    assert 'git' not in removals[0]['args']
    assert commands.index(removals[0]['args']) == len(commands) - 1
    assert ['flatpak', 'uninstall', '--user', '-y', 'com.brave.Browser'] in commands
    assert ['systemctl', 'disable', 'greetd.service'] in commands
    assert ['mv', '-fT', '/etc/locale.gen.quietline-20261028-101500', '/etc/locale.gen'] in commands
    assert ['rm', '-f', '/etc/greetd/quietline.toml'] in commands
    system_calls = [call for call in system.calls if call['args'][0] in ('mv', 'rm', 'systemctl')]
    assert all(call['sudo'] for call in system_calls)
    flatpak = next(call for call in system.calls if call['args'][0] == 'flatpak')
    assert not flatpak['sudo']
    assert config.read_text() == 'mine'


def test_journal_rollback_rebuilds_grub_menu_after_restoring_its_file(ctx, system):
    ctx.record({'kind': 'grub'})
    ctx.record({'kind': 'file', 'path': '/etc/default/grub', 'backup': '/etc/default/grub.quietline-20261102-120000'})
    snapshot.rollback_journal(ctx)
    commands = system.commands()
    restore = ['mv', '-fT', '/etc/default/grub.quietline-20261102-120000', '/etc/default/grub']
    rebuild = ['grub-mkconfig', '-o', '/boot/grub/grub.cfg']
    assert restore in commands and rebuild in commands
    assert commands.index(restore) < commands.index(rebuild)
    assert next(call for call in system.calls if call['args'] == rebuild)['sudo']


def test_journal_rollback_without_new_packages_runs_no_pacman(ctx, system):
    ctx.record({'kind': 'service', 'unit': 'bluetooth.service'})
    snapshot.rollback_journal(ctx)
    assert not [args for args in system.commands() if args[0] == 'pacman']


FORBIDDEN = re.compile(r'\b(?:parted|sfdisk|fdisk|mkfs|wipefs|sgdisk|grub-install|bootctl|efibootmgr)\b'
                       r'|set-default|subvolume[\'"]?,?\s*[\'"]?delete')


def test_installer_never_touches_partitions():
    repo = Path(__file__).resolve().parents[2]
    files = sorted((repo / 'src/quietline_install').rglob('*.py'))
    if (repo / 'install.sh').exists():
        files.append(repo / 'install.sh')
    assert repo / 'src/quietline_install/snapshot.py' in files
    for path in files:
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            assert not FORBIDDEN.search(line), f'{path.relative_to(repo)}:{number}: {line.strip()}'
    assert not FORBIDDEN.search('grub-mkconfig -o /boot/grub/grub.cfg')
    assert FORBIDDEN.search("['btrfs', 'subvolume', 'delete', top]")
    assert FORBIDDEN.search('mkfs.btrfs -L arch /dev/x')


def test_snapshot_without_grub_cfg_in_boot_skips_menu(ctx, system, tmp_path):
    make_root(ctx, system, tmp_path)
    system.answer(['test', '-e', '/boot/grub/grub.cfg'], code=1)
    name = snapshot.take(ctx, 'btrfs-ro')
    assert ctx.state.snapshot == {'kind': 'btrfs-ro', 'name': name}
    assert not [args for args in system.commands() if args[0] == 'grub-mkconfig']
