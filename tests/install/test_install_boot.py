"""Шаг «Тема меню загрузки»: строки /etc/default/grub, пропуск без GRUB, grub-mkconfig и возврат при ошибке."""

import subprocess

import pytest

from quietline_install.runner import StepFailed
from quietline_install.steps import boot

ARCH_DEFAULT_GRUB = """# GRUB boot loader configuration

GRUB_DEFAULT=0
GRUB_TIMEOUT=5
GRUB_CMDLINE_LINUX_DEFAULT="loglevel=3 quiet"

# Uncomment to use basic console
GRUB_TERMINAL_INPUT=console

# Uncomment to disable graphical terminal
#GRUB_TERMINAL_OUTPUT=console

GRUB_GFXMODE=auto

# Uncomment one of them for the gfx desired, a image background or a gfxtheme
#GRUB_BACKGROUND="/path/to/wallpaper"
#GRUB_THEME="/path/to/gfxtheme"
"""
RU_THEME = 'GRUB_THEME="/usr/share/quietline/grub/theme-ru.txt"'


@pytest.fixture
def root(ctx, tmp_path):
    ctx.root = tmp_path / 'root'
    (ctx.root / 'etc/default').mkdir(parents=True)
    (ctx.root / 'usr/bin').mkdir(parents=True)
    (ctx.root / 'usr/bin/grub-mkconfig').write_text('')
    (ctx.root / 'usr/share/quietline/grub').mkdir(parents=True)
    for language in ('ru', 'en'):
        (ctx.root / f'usr/share/quietline/grub/theme-{language}.txt').write_text('')
    (ctx.root / 'etc/default/grub').write_text(ARCH_DEFAULT_GRUB)
    ctx.state.system_language = 'ru'
    return ctx.root


def test_theme_replaces_the_commented_example_and_keeps_the_rest():
    lines = boot.with_theme(ARCH_DEFAULT_GRUB, '/usr/share/quietline/grub/theme-ru.txt').splitlines()
    assert RU_THEME in lines and '#GRUB_THEME="/path/to/gfxtheme"' not in lines
    assert lines.index(RU_THEME) == ARCH_DEFAULT_GRUB.splitlines().index('#GRUB_THEME="/path/to/gfxtheme"')
    assert 'GRUB_TERMINAL_INPUT=console' in lines and '#GRUB_TERMINAL_OUTPUT=console' in lines
    assert len(lines) == len(ARCH_DEFAULT_GRUB.splitlines())


def test_active_theme_lines_are_replaced_and_missing_one_is_appended():
    config = 'GRUB_TIMEOUT=5\nGRUB_THEME="/boot/grub/themes/old/theme.txt"\n'
    assert boot.with_theme(config, '/t.txt') == 'GRUB_TIMEOUT=5\nGRUB_THEME="/t.txt"\n'
    assert boot.with_theme('GRUB_TIMEOUT=5', '/t.txt') == 'GRUB_TIMEOUT=5\nGRUB_THEME="/t.txt"\n'


def test_text_output_is_commented_and_graphical_output_kept():
    config = 'GRUB_TERMINAL_OUTPUT=console\nGRUB_TERMINAL=console\n'
    assert boot.with_theme(config, '/t.txt').splitlines()[:2] == ['#GRUB_TERMINAL_OUTPUT=console',
                                                                  '#GRUB_TERMINAL=console']
    graphical = 'GRUB_TERMINAL_OUTPUT="gfxterm console"\n'
    assert boot.with_theme(graphical, '/t.txt').splitlines()[0] == 'GRUB_TERMINAL_OUTPUT="gfxterm console"'


def test_step_is_skipped_without_grub(ctx, system, tmp_path):
    ctx.root = tmp_path / 'empty'
    ctx.root.mkdir()
    assert boot.boot_theme_step().check(ctx) is True


def test_step_writes_theme_of_system_language_and_rebuilds_menu(ctx, system, root):
    step = boot.boot_theme_step()
    assert step.check(ctx) is False
    step.run(ctx)
    tee = next(call for call in system.calls if call['args'][:1] == ['tee'])
    assert tee['sudo'] and RU_THEME in tee['input'].splitlines()
    rebuild = next(call for call in system.calls if call['args'][0] == 'grub-mkconfig')
    assert rebuild['args'] == ['grub-mkconfig', '-o', '/boot/grub/grub.cfg'] and rebuild['sudo']
    commands = system.commands()
    assert commands.index(tee['args']) < commands.index(rebuild['args'])
    copy = next(call for call in system.calls if call['args'][:2] == ['cp', '-a'])
    # Запись grub в журнале раньше копии файла: откат вернёт файл, затем пересоберёт меню.
    assert ctx.state.changes == [{'kind': 'grub'},
                                 {'kind': 'file', 'path': '/etc/default/grub', 'backup': copy['args'][3]}]
    (root / 'etc/default/grub').write_text(tee['input'])
    assert step.check(ctx) is True


def test_english_system_gets_english_theme(ctx, system, root):
    ctx.state.system_language = 'en'
    boot.boot_theme_step().run(ctx)
    tee = next(call for call in system.calls if call['args'][:1] == ['tee'])
    assert 'GRUB_THEME="/usr/share/quietline/grub/theme-en.txt"' in tee['input'].splitlines()


def _mkconfig_fails(system, times: int) -> None:
    """Первые `times` вызовов grub-mkconfig завершаются ошибкой, остальные — успешно."""
    run = system.run
    failures = [times]

    def failing(args, **options):
        if args[0] == 'grub-mkconfig' and failures[0] > 0:
            failures[0] -= 1
            system.calls.append({'args': list(args), 'sudo': options.get('sudo', False)})
            raise subprocess.CalledProcessError(1, args)
        return run(args, **options)

    system.run = failing


def test_failed_mkconfig_restores_file_and_rebuilds_again(ctx, system, root):
    _mkconfig_fails(system, 1)
    with pytest.raises(StepFailed, match='was restored'):
        boot.boot_theme_step().run(ctx)
    commands = system.commands()
    backup = next(args for args in commands if args[:2] == ['cp', '-a'])[3]
    restore = ['cp', '-a', backup, '/etc/default/grub']
    rebuilds = [index for index, args in enumerate(commands) if args[0] == 'grub-mkconfig']
    assert len(rebuilds) == 2 and rebuilds[0] < commands.index(restore) < rebuilds[1]


def test_mkconfig_failing_twice_says_not_to_reboot(ctx, system, root):
    _mkconfig_fails(system, 2)
    with pytest.raises(StepFailed) as failure:
        boot.boot_theme_step().run(ctx)
    assert 'Do not reboot' in failure.value.action


def test_missing_theme_stops_before_touching_grub(ctx, system, root):
    (root / 'usr/share/quietline/grub/theme-ru.txt').unlink()
    with pytest.raises(StepFailed, match='theme-ru.txt'):
        boot.boot_theme_step().run(ctx)
    assert system.calls == [] and ctx.state.changes == []
