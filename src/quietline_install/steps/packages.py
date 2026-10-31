"""Шаги пакетов: обновление системы, пакеты Arch, графика, локали, службы, Flatpak, версии Node и Python,
локальный пакет `quietline`.

Пакеты Arch ставятся одной транзакцией `pacman -S --needed` без синхронизации баз: полное обновление
`pacman -Syu` — отдельный шаг, один раз за установку. В журнал изменений попадают только пакеты,
которых не было до установки, — откат не удаляет то, что стояло раньше.
"""

import re
import shutil
import subprocess
from pathlib import Path

from quietline_install.runner import (Ctx, Step, StepFailed, backup_system_file, read_system_file,
                                      write_system_file)

GRAPHICS = {'intel': ['mesa', 'vulkan-intel', 'intel-media-driver'], 'amd': ['mesa', 'vulkan-radeon'],
            'virtual': ['mesa'], 'unknown': ['mesa']}
VENDORS = {'0x8086': 'intel', '0x1002': 'amd', '0x10de': 'nvidia'}
LOCALES = ('en_US.UTF-8 UTF-8', 'ru_RU.UTF-8 UTF-8')
LOCALE_GEN = '/etc/locale.gen'
FLATHUB = 'https://dl.flathub.org/repo/flathub.flatpakrepo'
ARCH = 'Arch repositories'


def _installed(ctx: Ctx, names: list[str]) -> bool:
    return ctx.system.ok(['pacman', '-Q', *names])


def _install(ctx: Ctx, names: list[str]) -> None:
    """Проверяет, что все пакеты есть в репозиториях, и ставит их одной транзакцией; новые — в журнал."""
    missing = [name for name in names if not ctx.system.ok(['pacman', '-Si', name])]
    if missing:
        raise StepFailed(f'not in the Arch repositories: {", ".join(missing)}',
                         'Check the name in installer/catalog.toml (pacman -Ss) or run sudo pacman -Syu.')
    before = set(ctx.system.run(['pacman', '-Qq'], check=False).split())
    try:
        ctx.system.run(['pacman', '-S', '--needed', *names], sudo=True, interactive=True)
    except subprocess.CalledProcessError as exc:
        raise StepFailed('pacman did not install the packages', 'See the pacman output above.') from exc
    for name in names:
        if name not in before:
            ctx.record({'kind': 'package', 'name': name})


def upgrade_step() -> Step:
    """Полное обновление системы; выполняется один раз — отметка `done` в состоянии установки.

    Проверка сразу после успешного `pacman -Syu` проходит по флагу запуска: отметку `done` runner
    ставит только после проверки.
    """
    upgraded = []

    def run(ctx: Ctx) -> None:
        ctx.system.run(['pacman', '-Syu'], sudo=True, interactive=True)
        upgraded.append(True)

    return Step('system-upgrade', 'step.system-upgrade', ARCH,
                lambda ctx: bool(upgraded) or 'system-upgrade' in ctx.state.done, run)


def repo_step(packages: list[str]) -> Step:
    return Step('repo-packages', 'step.repo-packages', ARCH,
                lambda ctx: _installed(ctx, packages), lambda ctx: _install(ctx, packages))


def gpu_vendors(ctx: Ctx, drm: Path | None = None) -> set[str]:
    """Производители видеокарт: intel | amd | nvidia; в виртуальной машине — {'virtual'}; без данных — {'unknown'}."""
    virt = ctx.system.run(['systemd-detect-virt'], check=False).strip()
    if virt and virt != 'none':
        return {'virtual'}
    found = {VENDORS.get(path.read_text().strip())
             for path in Path(drm or '/sys/class/drm').glob('card*/device/vendor')} - {None}
    return found or {'unknown'}


def _graphics_packages(vendors: set[str]) -> list[str]:
    names = [name for vendor in ('intel', 'amd', 'virtual', 'unknown') if vendor in vendors
             for name in GRAPHICS[vendor]]
    return list(dict.fromkeys(names)) or ['mesa']


def graphics_step() -> Step:
    """Пакеты графики для Intel и AMD; драйвер NVIDIA ставится вручную, шаг ждёт `nvidia-utils`."""
    def nvidia_ready(ctx: Ctx, vendors: set[str]) -> bool:
        return 'nvidia' not in vendors or _installed(ctx, ['nvidia-utils'])

    def check(ctx: Ctx) -> bool:
        vendors = gpu_vendors(ctx)
        return nvidia_ready(ctx, vendors) and _installed(ctx, _graphics_packages(vendors))

    def run(ctx: Ctx) -> None:
        vendors = gpu_vendors(ctx)
        if not nvidia_ready(ctx, vendors):
            raise StepFailed('an NVIDIA graphics card needs a manually installed driver',
                             'Install it as described at https://wiki.archlinux.org/title/NVIDIA, '
                             'then run ./install.sh --from graphics')
        _install(ctx, _graphics_packages(vendors))

    return Step('graphics', 'step.graphics', ARCH, check, run)


def _active(text: str, locale: str) -> bool:
    return re.search(rf'^{re.escape(locale)}\s*$', text, re.M) is not None


def locales_step() -> Step:
    """Включает `en_US.UTF-8` и `ru_RU.UTF-8` в `/etc/locale.gen` (с копией) и запускает `locale-gen`."""
    def check(ctx: Ctx) -> bool:
        text = read_system_file(ctx, LOCALE_GEN) or ''
        return all(_active(text, locale) for locale in LOCALES)

    def run(ctx: Ctx) -> None:
        text = read_system_file(ctx, LOCALE_GEN) or ''
        for locale in LOCALES:
            if _active(text, locale):
                continue
            commented = re.compile(rf'^#\s*{re.escape(locale)}\s*$', re.M)
            if commented.search(text):
                text = commented.sub(locale, text, count=1)
            else:
                text = text + ('' if text.endswith('\n') or not text else '\n') + locale + '\n'
        backup_system_file(ctx, LOCALE_GEN)
        write_system_file(ctx, LOCALE_GEN, text)
        ctx.system.run(['locale-gen'], sudo=True)

    return Step('locales', 'step.locales', 'glibc', check, run)


def services_step(units: list[str]) -> Step:
    def enabled(ctx: Ctx, unit: str) -> bool:
        return ctx.system.ok(['systemctl', 'is-enabled', '--quiet', unit])

    def run(ctx: Ctx) -> None:
        for unit in units:
            if not enabled(ctx, unit):
                ctx.system.run(['systemctl', 'enable', '--now', unit], sudo=True)
                ctx.record({'kind': 'service', 'unit': unit})

    return Step('services', 'step.services', 'systemd',
                lambda ctx: all(enabled(ctx, unit) for unit in units), run)


def flatpak_step(ids: list[str]) -> Step:
    """Приложения Flathub ставятся для пользователя, без sudo."""
    def present(ctx: Ctx, app: str) -> bool:
        return ctx.system.ok(['flatpak', 'info', '--user', app])

    def run(ctx: Ctx) -> None:
        ctx.system.run(['flatpak', 'remote-add', '--user', '--if-not-exists', 'flathub', FLATHUB])
        for app in ids:
            if not present(ctx, app):
                ctx.system.run(['flatpak', 'install', '--user', '-y', 'flathub', app], interactive=True)
                ctx.record({'kind': 'flatpak', 'id': app})

    return Step('flatpak', 'step.flatpak', 'Flathub', lambda ctx: all(present(ctx, app) for app in ids), run)


def _fnm_has(listing: str, version: str) -> bool:
    if version == 'lts-latest':
        return re.search(r'\blts-latest\b', listing) is not None
    return re.search(rf'\bv{re.escape(version)}\.', listing) is not None


def fnm_step(versions: list[str]) -> Step:
    """Версии Node.js через fnm (`lts-latest` — последняя LTS); первая версия — по умолчанию."""
    def check(ctx: Ctx) -> bool:
        listing = ctx.system.run(['fnm', 'list'], check=False)
        return all(_fnm_has(listing, version) for version in versions)

    def run(ctx: Ctx) -> None:
        for version in versions:
            ctx.system.run(['fnm', 'install', '--lts'] if version == 'lts-latest' else ['fnm', 'install', version])
        ctx.system.run(['fnm', 'default', versions[0]])

    return Step('fnm', 'step.fnm', 'fnm', check, run)


def uv_step(versions: list[str]) -> Step:
    """Дополнительные версии Python через uv; системный Python не меняется."""
    def check(ctx: Ctx) -> bool:
        return all(ctx.system.ok(['uv', 'python', 'find', version]) for version in versions)

    def run(ctx: Ctx) -> None:
        ctx.system.run(['uv', 'python', 'install', *versions])

    return Step('uv', 'step.uv', 'uv', check, run)


def expected_version(ctx: Ctx) -> str:
    """То же правило, что `pkgver()` в PKGBUILD: `<версия>.r<число коммитов>.g<хеш>`."""
    version = re.search(r'^version = "([^"]+)"', (ctx.repo / 'pyproject.toml').read_text(), re.M).group(1)
    count = ctx.system.run(['git', '-C', str(ctx.repo), 'rev-list', '--count', 'HEAD']).strip()
    commit = ctx.system.run(['git', '-C', str(ctx.repo), 'rev-parse', '--short', 'HEAD']).strip()
    return f'{version}.r{count}.g{commit}'


def quietline_package_step() -> Step:
    """Локальный пакет `quietline` из закоммиченного клона; собирается вне клона, в кэше пользователя."""
    def check(ctx: Ctx) -> bool:
        try:
            installed = ctx.system.run(['pacman', '-Q', 'quietline']).split()
            return len(installed) == 2 and installed[1].rsplit('-', 1)[0] == expected_version(ctx)
        except (subprocess.CalledProcessError, OSError, AttributeError):
            return False

    def run(ctx: Ctx) -> None:
        new = not _installed(ctx, ['quietline'])
        build = ctx.home / '.cache/quietline/build'
        build.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ctx.repo / 'packaging/arch/PKGBUILD', build / 'PKGBUILD')
        ctx.system.run(['makepkg', '-si', '--cleanbuild'], cwd=build, interactive=True,
                       env={'QUIETLINE_REPO': str(ctx.repo)})
        if new:
            ctx.record({'kind': 'package', 'name': 'quietline'})

    return Step('quietline-package', 'step.quietline-package', 'Quietline (local build)', check, run)
