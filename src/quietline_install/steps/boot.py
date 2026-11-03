"""Тема меню загрузки: GRUB показывает тему Quietline на языке системы.

Шаг меняет только `/etc/default/grub` и пересобирает `/boot/grub/grub.cfg` командой
`grub-mkconfig`; загрузчик, разделы и записи EFI не трогаются. Без GRUB шаг пропускается.
"""

import re
import subprocess

from quietline_install.runner import Ctx, Step, StepFailed, backup_system_file, read_system_file, system_path, \
    write_system_file

GRUB_DEFAULT = '/etc/default/grub'
GRUB_CFG = '/boot/grub/grub.cfg'
GRUB_MKCONFIG = '/usr/bin/grub-mkconfig'
THEME_DIR = '/usr/share/quietline/grub'

_ACTIVE_THEME = re.compile(r'^\s*GRUB_THEME=')
_COMMENTED_THEME = re.compile(r'^\s*#\s*GRUB_THEME=')
# GRUB_TERMINAL задаёт и ввод, и вывод, поэтому с текстовым выводом мешает так же, как GRUB_TERMINAL_OUTPUT.
_TERMINAL = re.compile(r'^\s*GRUB_TERMINAL(?:_OUTPUT)?=(.*)$')


def theme_path(language: str | None) -> str:
    return f'{THEME_DIR}/theme-{"ru" if language == "ru" else "en"}.txt'


def with_theme(config: str, theme: str) -> str:
    """`/etc/default/grub` с `GRUB_THEME` на тему Quietline и графическим выводом меню.

    Действующие строки `GRUB_THEME` заменяются; без них — первая закомментированная, иначе строка
    добавляется в конец. Действующие `GRUB_TERMINAL_OUTPUT` и `GRUB_TERMINAL` без `gfxterm`
    закомментируются: с текстовым выводом тема не видна, а без них GRUB выводит меню графически.
    """
    line_theme = f'GRUB_THEME="{theme}"'
    lines = config.splitlines()
    active = any(_ACTIVE_THEME.match(line) for line in lines)
    placed = False
    result = []
    for line in lines:
        if _ACTIVE_THEME.match(line) or (not active and not placed and _COMMENTED_THEME.match(line)):
            result.append(line_theme)
            placed = True
            continue
        terminal = _TERMINAL.match(line)
        if terminal and 'gfxterm' not in terminal.group(1):
            result.append('#' + line)
            continue
        result.append(line)
    if not placed:
        result.append(line_theme)
    return '\n'.join(result) + '\n'


def _grub_present(ctx: Ctx) -> bool:
    return system_path(ctx, GRUB_DEFAULT).exists() and system_path(ctx, GRUB_MKCONFIG).exists()


def _mkconfig(ctx: Ctx) -> None:
    ctx.system.run(['grub-mkconfig', '-o', GRUB_CFG], sudo=True, interactive=True)


def boot_theme_step() -> Step:
    """GRUB_THEME в `/etc/default/grub` и пересборка меню; при ошибке `grub-mkconfig` файл возвращается.

    Запись `grub` в журнале стоит перед копией файла: откат по журналу сначала возвращает файл,
    затем снова запускает `grub-mkconfig`.
    """
    def check(ctx: Ctx) -> bool:
        if not _grub_present(ctx):
            return True
        config = read_system_file(ctx, GRUB_DEFAULT) or ''
        return with_theme(config, theme_path(ctx.state.system_language)).splitlines() == config.splitlines()

    def run(ctx: Ctx) -> None:
        theme = theme_path(ctx.state.system_language)
        if not system_path(ctx, theme).exists():
            raise StepFailed(f'{theme} was not found', 'Install the quietline package, then run ./install.sh again.')
        config = read_system_file(ctx, GRUB_DEFAULT)
        if config is None:
            raise StepFailed(f'{GRUB_DEFAULT} could not be read', 'Check the file, then run ./install.sh again.')
        ctx.record({'kind': 'grub'})
        backup = backup_system_file(ctx, GRUB_DEFAULT)
        write_system_file(ctx, GRUB_DEFAULT, with_theme(config, theme))
        try:
            _mkconfig(ctx)
        except subprocess.CalledProcessError:
            ctx.system.run(['cp', '-a', backup, GRUB_DEFAULT], sudo=True)
            try:
                _mkconfig(ctx)
            except subprocess.CalledProcessError:
                raise StepFailed('grub-mkconfig failed, and failed again after restoring ' + GRUB_DEFAULT,
                                 f'Do not reboot: fix the error above, then run sudo grub-mkconfig -o {GRUB_CFG}.') \
                    from None
            raise StepFailed('grub-mkconfig failed with the Quietline theme; ' + GRUB_DEFAULT + ' was restored',
                             'The boot menu is unchanged. See the output above, then run ./install.sh again.') \
                from None
        ctx.out(ctx.t('boot.themeNextBoot'))

    return Step('boot-theme', 'step.boot-theme', 'Quietline', check, run)
