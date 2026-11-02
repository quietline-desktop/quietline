"""Файлы пользователя: конфигурация Hyprland, fish, micro, ссылка на оболочку, домашние папки,
язык системы и закрепления дока.

Заменяемый файл сохраняется копией `<файл>.quietline-<время>`; если текущее содержимое уже лежит
в последней копии, новая не создаётся. Каждое изменение записывается в журнал для отката.
Язык и закрепления пишет `quietline-shell` — тот же код, что у окна «Настройки».
"""

import json
import time
from pathlib import Path

from quietline_install.runner import Ctx, Step, system_path

FILES = Path(__file__).resolve().parents[3] / 'installer/files'
DOFILE = 'dofile("/usr/share/quietline/hyprland/quietline.lua")'
SHELL_DIR = Path('/usr/share/quietline/shell')
LOCALE_FISH = '/usr/share/quietline/fish/quietline-locale.fish'
FNM_HOOK = 'fnm env --use-on-cd --shell fish | source'
MICRO_SETTINGS = {'clipboard': 'external', 'mouse': True}
USER_DIRS = ('Desktop', 'Documents', 'Downloads', 'Music', 'Pictures', 'Public', 'Templates', 'Videos')
REGION_DEFAULTS = {'ru': {'clock': '24h', 'date': 'dmy'}, 'en': {'clock': '12h', 'date': 'mdy'}}


def _stamp() -> str:
    return time.strftime('%Y%m%d-%H%M%S')


def _config(ctx: Ctx, relative: str) -> Path:
    return ctx.home / '.config' / relative


def _latest_backup(target: Path) -> Path | None:
    backups = sorted(target.parent.glob(f'{target.name}.quietline-*'))
    return backups[-1] if backups else None


def _set_aside(target: Path) -> Path:
    """Убирает существующий файл в копию; одинаковую с последней копией не дублирует."""
    latest = _latest_backup(target)
    if (latest is not None and target.is_file() and not target.is_symlink() and latest.is_file()
            and latest.read_bytes() == target.read_bytes()):
        target.unlink()
        return latest
    backup = target.with_name(f'{target.name}.quietline-{_stamp()}')
    target.rename(backup)
    return backup


def write_text(ctx: Ctx, target: Path, content: str) -> str:
    """Пишет `content` в файл пользователя: `created | unchanged | updated, backup <путь>`."""
    if target.is_file() and not target.is_symlink() and target.read_text(encoding='utf-8') == content:
        return 'unchanged'
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = _set_aside(target) if target.exists() or target.is_symlink() else None
    target.write_text(content, encoding='utf-8')
    ctx.record({'kind': 'file', 'path': str(target), 'backup': str(backup) if backup else None})
    return f'updated, backup {backup}' if backup else 'created'


def install_file(ctx: Ctx, source: Path, target: Path) -> str:
    return write_text(ctx, target, Path(source).read_text(encoding='utf-8'))


def hyprland_step() -> Step:
    """Нет строки подключения Quietline — файл (в том числе пример Hyprland) заменяется шаблоном с копией."""
    def target(ctx: Ctx) -> Path:
        return _config(ctx, 'hypr/hyprland.lua')

    def check(ctx: Ctx) -> bool:
        path = target(ctx)
        return path.is_file() and DOFILE in path.read_text(encoding='utf-8', errors='replace')

    return Step('hyprland-config', 'step.hyprland-config', 'Quietline', check,
                lambda ctx: install_file(ctx, FILES / 'hyprland.lua', target(ctx)))


def _fish_main(with_fnm: bool) -> str:
    text = (FILES / 'quietline.fish').read_text(encoding='utf-8')
    return text + (f'{FNM_HOOK}\n' if with_fnm else '')


def fish_step(with_fnm: bool) -> Step:
    """`conf.d/quietline.fish` (редактор, starship, при выбранном Node — fnm) и английские сообщения терминала."""
    def wanted(ctx: Ctx) -> dict[Path, str]:
        locale = system_path(ctx, LOCALE_FISH).read_text(encoding='utf-8')
        return {_config(ctx, 'fish/conf.d/quietline.fish'): _fish_main(with_fnm),
                _config(ctx, 'fish/conf.d/quietline-locale.fish'): locale}

    def check(ctx: Ctx) -> bool:
        return all(path.is_file() and path.read_text(encoding='utf-8') == text
                   for path, text in wanted(ctx).items())

    def run(ctx: Ctx) -> None:
        for path, text in wanted(ctx).items():
            write_text(ctx, path, text)

    return Step('fish', 'step.fish', 'Quietline', check, run)


def _micro(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def micro_step() -> Step:
    """Добавляет в настройки micro системный буфер и мышь, остальные ключи сохраняет."""
    def target(ctx: Ctx) -> Path:
        return _config(ctx, 'micro/settings.json')

    def check(ctx: Ctx) -> bool:
        current = _micro(target(ctx)) or {}
        return all(current.get(key) == value for key, value in MICRO_SETTINGS.items())

    def run(ctx: Ctx) -> None:
        current = _micro(target(ctx)) or {}
        write_text(ctx, target(ctx), json.dumps({**current, **MICRO_SETTINGS}, indent=4, ensure_ascii=False) + '\n')

    return Step('micro', 'step.micro', 'Quietline', check, run)


def quickshell_link_step() -> Step:
    """`~/.config/quickshell/quietline` указывает на оболочку из пакета; прежний каталог уходит в копию."""
    def target(ctx: Ctx) -> Path:
        return _config(ctx, 'quickshell/quietline')

    def check(ctx: Ctx) -> bool:
        path = target(ctx)
        return path.is_symlink() and path.readlink() == SHELL_DIR

    def run(ctx: Ctx) -> None:
        path = target(ctx)
        path.parent.mkdir(parents=True, exist_ok=True)
        backup = None
        if path.is_symlink():
            path.unlink()
        elif path.exists():
            backup = path.with_name(f'{path.name}.quietline-{_stamp()}')
            path.rename(backup)
        path.symlink_to(SHELL_DIR)
        ctx.record({'kind': 'file', 'path': str(path), 'backup': str(backup) if backup else None})

    return Step('quickshell-link', 'step.quickshell-link', 'Quietline', check, run)


def user_dirs_step() -> Step:
    """Английские домашние папки для нового пользователя; существующие пути не трогаются.

    `user-dirs.conf` с `enabled=False` пишется всегда: имена папок не переводятся при смене языка.
    """
    def check(ctx: Ctx) -> bool:
        conf = _config(ctx, 'user-dirs.conf')
        return (_config(ctx, 'user-dirs.dirs').is_file() and conf.is_file()
                and 'enabled=False' in conf.read_text(encoding='utf-8'))

    def run(ctx: Ctx) -> None:
        dirs = _config(ctx, 'user-dirs.dirs')
        if dirs.exists():
            paths = [line.split('=', 1)[1].strip().strip('"') for line in dirs.read_text(encoding='utf-8').splitlines()
                     if line.startswith('XDG_') and '=' in line]
            ctx.out(ctx.t('configs.userDirsKept', paths=', '.join(paths)))
        else:
            install_file(ctx, FILES / 'user-dirs.dirs', dirs)
            for folder in USER_DIRS:
                (ctx.home / folder).mkdir(exist_ok=True)
        install_file(ctx, FILES / 'user-dirs.conf', _config(ctx, 'user-dirs.conf'))

    return Step('user-dirs', 'step.user-dirs', 'Quietline', check, run)


def _remember(ctx: Ctx, path: Path) -> None:
    """Записывает в журнал файл, который изменит `quietline-shell`: копия прежнего или пометка «создан»."""
    backup = None
    if path.exists():
        backup = path.with_name(f'{path.name}.quietline-{_stamp()}')
        backup.write_bytes(path.read_bytes())
    ctx.record({'kind': 'file', 'path': str(path), 'backup': str(backup) if backup else None})


def region_step() -> Step:
    """Язык системы через `quietline-shell region --set`; формат даты и времени — только при первой установке."""
    def region(ctx: Ctx) -> Path:
        return _config(ctx, 'quietline/region.json')

    def current_language(ctx: Ctx) -> str | None:
        try:
            return json.loads(region(ctx).read_text(encoding='utf-8')).get('language')
        except (OSError, ValueError, AttributeError):
            return None

    def run(ctx: Ctx) -> None:
        language = ctx.state.system_language
        fields = {'language': language}
        if not region(ctx).exists():
            fields.update(REGION_DEFAULTS[language])
        for path in (_config(ctx, 'locale.conf'), region(ctx), _config(ctx, 'quietline/keyboard.lua')):
            _remember(ctx, path)
        ctx.system.run(['quietline-shell', 'region', '--set', json.dumps(fields)])

    return Step('region', 'step.region', 'quietline-shell',
                lambda ctx: current_language(ctx) == ctx.state.system_language, run)


def pins_step(pins: list[str]) -> Step:
    """Закрепления дока из выбора — только если `pins.json` ещё нет."""
    def target(ctx: Ctx) -> Path:
        return _config(ctx, 'quietline/pins.json')

    def run(ctx: Ctx) -> None:
        ctx.system.run(['quietline-shell', 'pins', '--set', json.dumps(pins)])
        ctx.record({'kind': 'file', 'path': str(target(ctx)), 'backup': None})

    return Step('pins', 'step.pins', 'quietline-shell', lambda ctx: target(ctx).exists(), run)
