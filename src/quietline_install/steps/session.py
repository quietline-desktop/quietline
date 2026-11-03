"""Экран входа Quietline через greetd, хранилище паролей, fish по умолчанию, доступ к Docker и программы, которые ставятся вручную.

Необязательные вопросы (оболочка, группа docker) задаёт экран «Параметры» до сводки; ответ лежит в
`state.selection['options']`, без него шаг спрашивает в терминале. После отказа вопрос больше не
задаётся: отказ помечается файлом `~/.local/state/quietline/declined-<id>`. Ручные шаги показывают официальные инструкции,
ждут подтверждения и проверяют, что программа действительно появилась.
"""

import getpass
import re
import shutil
import time
from pathlib import Path

from quietline_install.runner import (Ctx, Step, StepFailed, backup_system_file, read_system_file,
                                      system_path, write_system_file)

FILES = Path(__file__).resolve().parents[3] / 'installer/files'
GREETD_TEMPLATE = FILES / 'greetd-config.toml'
GREETD_CONFIG = '/etc/greetd/config.toml'
# Первая строка шаблонов Quietline для greetd: по ней свой файл пользователя отличается от шаблона.
GREETD_MARK = '# Quietline:'
PAM_GREETD = '/etc/pam.d/greetd'
KEYRING_AUTH = 'auth       optional     pam_gnome_keyring.so'
KEYRING_SESSION = 'session    optional     pam_gnome_keyring.so auto_start'
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
    """greetd открывает экран входа Quietline (`quietline-greeter`); служба — на следующую загрузку.

    Свой `config.toml` пользователя с tuigreet (без отметки шаблона Quietline в первой строке)
    сохраняется. Прежний шаблон Quietline с tuigreet и любой другой файл заменяются шаблоном,
    старый файл остаётся копией.
    """
    def configured(ctx: Ctx) -> bool:
        config = read_system_file(ctx, GREETD_CONFIG) or ''
        own = config.lstrip().startswith(GREETD_MARK)
        return 'quietline-greeter' in config or ('tuigreet' in config and not own)

    def run(ctx: Ctx) -> None:
        if not configured(ctx):
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

    return Step('greetd', 'step.greetd', 'Quietline, Arch repositories: greetd, tuigreet',
                lambda ctx: configured(ctx) and _greetd_enabled(ctx), run)


def _has_keyring(pam: str, kind: str) -> bool:
    return any(line.split()[:1] in ([kind], [f'-{kind}']) and 'pam_gnome_keyring.so' in line
               for line in pam.splitlines())


def with_keyring(pam: str) -> str:
    """PAM greetd, в котором вход открывает gnome-keyring паролем пользователя.

    Строка `auth` встаёт после последней строки `auth`, строка `session` с `auto_start` — после
    последней строки `session`; без таких строк — в конец. Уже подключённый модуль не дублируется.
    """
    lines = pam.splitlines()
    for kind, line in (('auth', KEYRING_AUTH), ('session', KEYRING_SESSION)):
        if _has_keyring(pam, kind):
            continue
        last = max((index for index, current in enumerate(lines)
                    if current.split()[:1] in ([kind], [f'-{kind}'])), default=len(lines) - 1)
        lines.insert(last + 1, line)
    return '\n'.join(lines) + '\n'


def keyring_step() -> Step:
    """Хранилище секретов gnome-keyring открывается при входе через greetd.

    Без службы `org.freedesktop.secrets` программы на libsecret (1Password, Chrome, VS Code) не
    сохраняют пароли и токены. Изменённый PAM greetd сохраняется копией; хранилище с паролем
    входа появляется при следующем входе в систему.
    """
    def current(ctx: Ctx) -> str | None:
        return read_system_file(ctx, PAM_GREETD)

    def check(ctx: Ctx) -> bool:
        pam = current(ctx) or ''
        return _has_keyring(pam, 'auth') and _has_keyring(pam, 'session')

    def run(ctx: Ctx) -> None:
        pam = current(ctx)
        if pam is None:
            raise StepFailed(f'{PAM_GREETD} was not found', 'Install greetd, then run ./install.sh again.')
        backup_system_file(ctx, PAM_GREETD)
        write_system_file(ctx, PAM_GREETD, with_keyring(pam))
        ctx.out(ctx.t('session.keyringRelogin'))

    return Step('keyring', 'step.keyring', 'Arch repositories: gnome-keyring', check, run)


def current_shell(ctx: Ctx) -> str:
    return ctx.system.run(['getent', 'passwd', getpass.getuser()], check=False).strip().rsplit(':', 1)[-1]


def docker_member(ctx: Ctx) -> bool:
    line = ctx.system.run(['getent', 'group', 'docker'], check=False).strip()
    return getpass.getuser() in line.rsplit(':', 1)[-1].split(',') if line else False


def open_questions(ctx: Ctx, docker: bool) -> list[str]:
    """Id необязательных шагов, которые ещё нужно спросить: не сделаны и не отклонены раньше."""
    ids = []
    if current_shell(ctx) != '/usr/bin/fish' and not declined(ctx, 'default-shell'):
        ids.append('default-shell')
    if docker and not docker_member(ctx) and not declined(ctx, 'docker-group'):
        ids.append('docker-group')
    return ids


def _answer(ctx: Ctx, step_id: str, question: str, default: bool) -> bool:
    """Ответ с экрана «Параметры»; без него — вопрос в терминале."""
    options = ctx.state.selection.get('options', {})
    if step_id in options:
        return bool(options[step_id])
    return ctx.ask(question, default=default)


def default_shell_step() -> Step:
    def check(ctx: Ctx) -> bool:
        return current_shell(ctx) == '/usr/bin/fish' or declined(ctx, 'default-shell')

    def run(ctx: Ctx) -> None:
        if _answer(ctx, 'default-shell', ctx.t('session.shellQuestion'), default=True):
            previous = current_shell(ctx)
            ctx.system.run(['chsh', '-s', '/usr/bin/fish'], interactive=True)
            # Откат возвращает прежнюю оболочку до удаления fish, иначе вход станет невозможен.
            if previous:
                ctx.record({'kind': 'shell', 'previous': previous})
        else:
            decline(ctx, 'default-shell')

    return Step('default-shell', 'step.default-shell', 'Quietline', check, run)


def docker_group_step() -> Step:
    def run(ctx: Ctx) -> None:
        if 'docker-group' not in ctx.state.selection.get('options', {}):
            ctx.out(ctx.t('session.dockerRoot'))
        if _answer(ctx, 'docker-group', ctx.t('session.dockerQuestion'), default=False):
            ctx.system.run(['usermod', '-aG', 'docker', getpass.getuser()], sudo=True)
            ctx.out(ctx.t('session.dockerRelogin'))
        else:
            decline(ctx, 'docker-group')
        context = ctx.system.run(['docker', 'context', 'show'], check=False).strip() or 'default'
        ctx.out(ctx.t('session.dockerContext', context=context))

    return Step('docker-group', 'step.docker-group', 'Quietline',
                lambda ctx: docker_member(ctx) or declined(ctx, 'docker-group'), run)


def _manual(ctx: Ctx, step_id: str, instructions: str, question: str, present, missing: str) -> None:
    """Инструкции ручного шага; без установленной программы шаг можно пропустить — id попадает в `state.skipped`.

    Enter отвечает «да» на оба вопроса: программа установлена, а если её нет — шаг пропускается.
    """
    for line in instructions.splitlines():
        ctx.out(line)
    if not ctx.ask(question, default=True):
        failure = StepFailed(f'{missing} is not installed yet', 'Follow the steps above, then run ./install.sh again.')
    elif not present(ctx):
        failure = StepFailed(f'{missing} was not found', 'Check that its installer finished, then run ./install.sh again.')
    else:
        return
    if not ctx.ask(ctx.t('manual.skip', step=step_id), default=True):
        raise failure
    ctx.state.skipped.append(step_id)
    ctx.state.save()


def _manual_check(step_id: str, present):
    return lambda ctx: step_id in ctx.state.skipped or present(ctx)


def amneziavpn_step() -> Step:
    def present(ctx: Ctx) -> bool:
        return system_path(ctx, '/opt/AmneziaVPN').exists() or shutil.which('AmneziaVPN') is not None

    def run(ctx: Ctx) -> None:
        _manual(ctx, 'amneziavpn', ctx.t('manual.amnezia', releases=AMNEZIA_RELEASES, site=AMNEZIA_SITE),
                ctx.t('manual.amneziaQuestion'), present, 'AmneziaVPN')

    return Step('amneziavpn', 'step.amneziavpn', 'amnezia.org', _manual_check('amneziavpn', present), run,
                manual=True)

# Форк hyprland-plugins организации Quietline: hyprbars с подсветкой кнопок под указателем.
# У официального репозитория то же имя `hyprland-plugins`, поэтому hyprpm держит только один из них.
HYPRLAND_PLUGINS = 'https://github.com/quietline-desktop/hyprland-plugins'
PLUGINS_AUTHOR = 'quietline-desktop'


def hyprbars_enabled(listing: str) -> bool:
    """Включён ли hyprbars по выводу `hyprpm list`: строка плагина и следующая за ней `enabled`.

    hyprpm раскрашивает вывод escape-последовательностями ANSI; они отбрасываются.
    """
    plain = re.sub(r'\x1b\[[0-9;]*m', '', listing)
    lines = [line.strip(' │└─├→\t') for line in plain.splitlines()]
    for index, line in enumerate(lines):
        if line.lower().endswith('hyprbars'):
            following = ' '.join(lines[index + 1:index + 3]).lower()
            return 'enabled' in following and any(mark in following for mark in ('true', 'yes', '✔'))
    return False


def plugins_author(listing: str) -> str | None:
    """Владелец установленного репозитория `hyprland-plugins` по выводу `hyprpm list`; нет его — `None`.

    hyprpm называет владельцем часть адреса репозитория перед его именем: `(by hyprwm)`.
    """
    plain = re.sub(r'\x1b\[[0-9;]*m', '', listing)
    found = re.search(r'Repository hyprland-plugins \(by ([^)]+)\)', plain)
    return found.group(1) if found else None


def hyprbars_step() -> Step:
    """Заголовки окон: hyprpm собирает hyprbars из форка hyprland-plugins под установленный Hyprland.

    `hyprpm update` скачивает заголовки Hyprland и пересобирает плагины, sudo он спрашивает
    сам. Официальный `hyprland-plugins` убирается командой `hyprpm remove`, которая сама
    спрашивает подтверждение, и на его место ставится форк. Шаг требует запущенного сеанса
    Hyprland; без него hyprpm падает, и шаг повторяют из сеанса: `./install.sh --from hyprbars`.
    """
    def listing(ctx: Ctx) -> str:
        return ctx.system.run(['hyprpm', 'list'], check=False)

    def check(ctx: Ctx) -> bool:
        current = listing(ctx)
        return hyprbars_enabled(current) and plugins_author(current) == PLUGINS_AUTHOR

    def run(ctx: Ctx) -> None:
        ctx.system.run(['hyprpm', 'update'], interactive=True)
        author = plugins_author(listing(ctx))
        if author is not None and author != PLUGINS_AUTHOR:
            ctx.system.run(['hyprpm', 'remove', 'hyprland-plugins'], interactive=True)
        if author != PLUGINS_AUTHOR:
            ctx.system.run(['hyprpm', 'add', HYPRLAND_PLUGINS], interactive=True)
        ctx.system.run(['hyprpm', 'enable', 'hyprbars'], interactive=True)

    return Step('hyprbars', 'step.hyprbars', 'github.com/quietline-desktop/hyprland-plugins', check, run)
