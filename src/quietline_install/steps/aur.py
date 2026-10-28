"""Пакеты AUR: собираются только после того, как пользователь прочитал инструкции сборки.

Перед вопросом печатаются `PKGBUILD`, все `*.install` и список остальных файлов клона.
`git` обрывает зависшую загрузку по `GIT_TIMEOUT`; `makepkg` запускается в терминале пользователя
без `--noconfirm`, чтобы pacman показал свои вопросы.
"""

import json
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from quietline_install.runner import Ctx, Step, StepFailed

ONEPASSWORD_KEY = 'https://downloads.1password.com/linux/keys/1password.asc'
# Передача медленнее 1 КБ/с дольше 30 секунд прерывается.
GIT_TIMEOUT = {'GIT_HTTP_LOW_SPEED_LIMIT': '1000', 'GIT_HTTP_LOW_SPEED_TIME': '30'}
# Строк инструкций на одной странице консоли.
PAGE = 20


def _clone(ctx: Ctx, name: str) -> Path:
    directory = ctx.home / '.cache/quietline/aur' / name
    try:
        if (directory / 'PKGBUILD').exists():
            ctx.system.run(['git', '-C', str(directory), 'pull', '--ff-only'], env=GIT_TIMEOUT)
        else:
            directory.parent.mkdir(parents=True, exist_ok=True)
            ctx.system.run(['git', 'clone', f'https://aur.archlinux.org/{name}.git', str(directory)],
                           env=GIT_TIMEOUT)
    except subprocess.CalledProcessError as exc:
        raise StepFailed(f'could not download {name} from the AUR', 'Check the network connection.') from exc
    return directory


def _show(ctx: Ctx, name: str, directory: Path) -> None:
    """Инструкции по страницам `PAGE` строк: в консоли без прокрутки длинный текст иначе не прочитать."""
    shown = [directory / 'PKGBUILD', *sorted(directory.glob('*.install'))]
    lines = []
    for path in shown:
        if path.exists():
            lines.append(f'---- {name}/{path.name} ----')
            lines += path.read_text(encoding='utf-8', errors='replace').splitlines()
    printed = 0
    for line in lines:
        if line.startswith('---- ') or printed < PAGE:
            ctx.out(line)
            printed += 0 if line.startswith('---- ') else 1
            continue
        if not ctx.ask(ctx.t('aur.more', name=name)):
            break
        ctx.out(line)
        printed = 1
    others = sorted(str(path.relative_to(directory)) for path in directory.rglob('*')
                    if path.is_file() and path not in shown and '.git' not in path.relative_to(directory).parts)
    if others:
        ctx.out(ctx.t('aur.files', name=name, files=', '.join(others)))


def aur_install(ctx: Ctx, name: str) -> None:
    directory = _clone(ctx, name)
    _show(ctx, name, directory)
    if not ctx.ask(ctx.t('aur.confirm', name=name)):
        raise StepFailed(f'building {name} was declined',
                         f'Review the package at https://aur.archlinux.org/packages/{name}.')
    try:
        if name == '1password':
            # 1Password подписывает выпуски; PKGBUILD проверяет подпись этим ключом.
            key = ctx.system.run(['curl', '-fsS', ONEPASSWORD_KEY])
            ctx.system.run(['gpg', '--import'], input=key)
        ctx.system.run(['makepkg', '-si', '--cleanbuild'], cwd=directory, interactive=True)
    except subprocess.CalledProcessError as exc:
        raise StepFailed(f'makepkg did not build {name}', 'See the makepkg output above.') from exc
    ctx.record({'kind': 'package', 'name': name})


def aur_step(name: str) -> Step:
    return Step(f'aur-{name}', 'step.aur', f'AUR: {name}',
                lambda ctx: ctx.system.ok(['pacman', '-Q', name]), lambda ctx: aur_install(ctx, name))


def fetch_versions(names: list[str]) -> dict:
    query = urllib.parse.urlencode([('arg[]', name) for name in names])
    with urllib.request.urlopen(f'https://aur.archlinux.org/rpc/v5/info?{query}', timeout=15) as response:
        data = json.load(response)
    return {item['Name']: item['Version'] for item in data.get('results', [])}


def aur_outdated(ctx: Ctx, names: list[str], fetch=fetch_versions) -> list[str]:
    """Установленные пакеты AUR, у которых в AUR версия новее; без сети — пустой список и строка в журнале."""
    output = ctx.system.run(['pacman', '-Q', *names], check=False)
    local = dict(line.split() for line in output.splitlines() if len(line.split()) == 2)
    try:
        remote = fetch([name for name in names if name in local])
    except (urllib.error.URLError, OSError, ValueError) as exc:
        ctx.log(f'AUR version check failed: {exc}')
        return []
    return [name for name in names if name in local and name in remote
            and ctx.system.run(['vercmp', remote[name], local[name]]).strip() == '1']
