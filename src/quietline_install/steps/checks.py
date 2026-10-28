"""Проверка готовности после установки: строка на пункт и общий итог."""

import shutil

from quietline_install.catalog import Plan
from quietline_install.runner import Ctx

COMMANDS = ('Hyprland', 'qs', 'quietline-engine', 'quietline-shell', 'ghostty', 'fish', 'starship', 'micro', 'git')
LOCALES = ('en_US.utf8', 'ru_RU.utf8')
DOFILE = 'dofile("/usr/share/quietline/hyprland/quietline.lua")'


def run_checks(ctx: Ctx, plan: Plan, which=shutil.which) -> tuple[list[str], bool]:
    """Команды основы, пакеты и приложения выбора, службы, пакет quietline, файлы оболочки, локали."""
    items: list[tuple[str, bool]] = []
    items += [(name, which(name) is not None) for name in COMMANDS]
    items += [(name, ctx.system.ok(['pacman', '-Q', name])) for name in [*plan.repo, *plan.aur, 'quietline']]
    items += [(app, ctx.system.ok(['flatpak', 'info', '--user', app])) for app in plan.flatpak]
    items += [(unit, ctx.system.ok(['systemctl', 'is-enabled', '--quiet', unit]))
              for unit in [*plan.services, 'greetd.service']]
    config = ctx.home / '.config'
    lock = config / 'quickshell/quietline/lock/LockScreen.qml'
    hypr = config / 'hypr/hyprland.lua'
    region = config / 'quietline/region.json'
    items.append((str(lock), lock.is_file()))
    items.append((f'{hypr}: {DOFILE}', hypr.is_file() and DOFILE in hypr.read_text(encoding='utf-8', errors='replace')))
    items.append((str(region), region.is_file()))
    available = ctx.system.run(['locale', '-a'], check=False).split()
    items += [(locale, locale in available) for locale in LOCALES]
    lines = [f'{name} — {ctx.t("ready.ok") if ok else ctx.t("ready.missing")}' for name, ok in items]
    return lines, all(ok for _, ok in items)
