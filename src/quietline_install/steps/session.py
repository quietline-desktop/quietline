"""Экран входа greetd, fish по умолчанию, доступ к Docker и программы, которые ставятся вручную.

Необязательные вопросы (оболочка, группа docker) после отказа больше не задаются: отказ помечается
файлом `~/.local/state/quietline/declined-<id>`. Ручные шаги показывают официальные инструкции,
ждут подтверждения и проверяют, что программа действительно появилась.
"""

import getpass
import shutil
import time
from pathlib import Path

from quietline_install.runner import (Ctx, Step, StepFailed, backup_system_file, read_system_file,
                                      system_path, write_system_file)

FILES = Path(__file__).resolve().parents[3] / 'installer/files'
GREETD_TEMPLATE = FILES / 'greetd-config.toml'
GREETD_CONFIG = '/etc/greetd/config.toml'
DOCKER_DESKTOP_DOCS = 'https://docs.docker.com/desktop/setup/install/linux/archlinux/'
AMNEZIA_RELEASES = 'https://github.com/amnezia-vpn/amnezia-client/releases'
AMNEZIA_SITE = 'https://amnezia.org/en/downloads'


def _marker(ctx: Ctx, step_id: str) -> Path:
    return ctx.home / '.local/state/quietline' / f'declined-{step_id}'


def declined(ctx: Ctx, step_id: str) -> bool:
    return _marker(ctx, step_id).exists()


def decline(ctx: Ctx, step_id: str) -> None:
    _marker(ctx, step_id).parent.mkdir(parents=True, exist_ok=True)
    _marker(ctx, step_id).write_text(time.strftime('%Y-%m-%d %H:%M:%S\n'))


def _greetd_enabled(ctx: Ctx) -> bool:
    return ctx.system.ok(['systemctl', 'is-enabled', '--quiet', 'greetd.service'])


def greetd_step() -> Step:
    """Конфигурация greetd с tuigreet (если в файле tuigreet нет) и служба на следующую загрузку."""
    def has_tuigreet(ctx: Ctx) -> bool:
        return 'tuigreet' in (read_system_file(ctx, GREETD_CONFIG) or '')

    def run(ctx: Ctx) -> None:
        if not has_tuigreet(ctx):
            if system_path(ctx, GREETD_CONFIG).exists():
                backup_system_file(ctx, GREETD_CONFIG)
            else:
                ctx.record({'kind': 'file', 'path': GREETD_CONFIG, 'backup': None})
            write_system_file(ctx, GREETD_CONFIG, GREETD_TEMPLATE.read_text(encoding='utf-8'))
        if not _greetd_enabled(ctx):
            # Служба включается на следующую загрузку: текущий сеанс не прерывается.
            ctx.system.run(['systemctl', 'enable', 'greetd.service'], sudo=True)
            ctx.record({'kind': 'service', 'unit': 'greetd.service'})
            ctx.out(ctx.t('session.greetdNextBoot'))

    return Step('greetd', 'step.greetd', 'Arch repositories: greetd, tuigreet',
                lambda ctx: has_tuigreet(ctx) and _greetd_enabled(ctx), run)


def default_shell_step() -> Step:
    def check(ctx: Ctx) -> bool:
        entry = ctx.system.run(['getent', 'passwd', getpass.getuser()], check=False).strip()
        return entry.endswith(':/usr/bin/fish') or declined(ctx, 'default-shell')

    def run(ctx: Ctx) -> None:
        if ctx.ask(ctx.t('session.shellQuestion')):
            ctx.system.run(['chsh', '-s', '/usr/bin/fish'], interactive=True)
        else:
            decline(ctx, 'default-shell')

    return Step('default-shell', 'step.default-shell', 'Quietline', check, run)


def docker_group_step() -> Step:
    def member(ctx: Ctx) -> bool:
        line = ctx.system.run(['getent', 'group', 'docker'], check=False).strip()
        return getpass.getuser() in line.rsplit(':', 1)[-1].split(',') if line else False

    def run(ctx: Ctx) -> None:
        ctx.out(ctx.t('session.dockerRoot'))
        if ctx.ask(ctx.t('session.dockerQuestion')):
            ctx.system.run(['usermod', '-aG', 'docker', getpass.getuser()], sudo=True)
            ctx.out(ctx.t('session.dockerRelogin'))
        else:
            decline(ctx, 'docker-group')
        context = ctx.system.run(['docker', 'context', 'show'], check=False).strip() or 'default'
        ctx.out(ctx.t('session.dockerContext', context=context))

    return Step('docker-group', 'step.docker-group', 'Quietline',
                lambda ctx: member(ctx) or declined(ctx, 'docker-group'), run)


def _manual(ctx: Ctx, instructions: str, question: str, present, missing: str) -> None:
    for line in instructions.splitlines():
        ctx.out(line)
    if not ctx.ask(question):
        raise StepFailed(f'{missing} is not installed yet', 'Follow the steps above, then run ./install.sh again.')
    if not present(ctx):
        raise StepFailed(f'{missing} was not found', 'Check that its installer finished, then run ./install.sh again.')


def docker_desktop_step() -> Step:
    def present(ctx: Ctx) -> bool:
        return ctx.system.ok(['pacman', '-Q', 'docker-desktop'])

    def run(ctx: Ctx) -> None:
        _manual(ctx, ctx.t('manual.dockerDesktop', docs=DOCKER_DESKTOP_DOCS),
                ctx.t('manual.dockerDesktopQuestion'), present, 'Docker Desktop')

    return Step('docker-desktop', 'step.docker-desktop', 'docker.com', present, run, manual=True)


def amneziavpn_step() -> Step:
    def present(ctx: Ctx) -> bool:
        return system_path(ctx, '/opt/AmneziaVPN').exists() or shutil.which('AmneziaVPN') is not None

    def run(ctx: Ctx) -> None:
        _manual(ctx, ctx.t('manual.amnezia', releases=AMNEZIA_RELEASES, site=AMNEZIA_SITE),
                ctx.t('manual.amneziaQuestion'), present, 'AmneziaVPN')

    return Step('amneziavpn', 'step.amneziavpn', 'amnezia.org', present, run, manual=True)
