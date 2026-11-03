"""Установщик Quietline: `python -m quietline_install [run|status|check|rollback|update] [--dry-run] [--from ID]`.

`run` (по умолчанию): незавершённая установка — экран «Продолжить / Откатить / Выйти»; иначе экраны
по порядку: язык установщика → проверки → язык системы → программы → сводка. После согласия —
снимок корня (Btrfs), затем шаги. Состояние и журнал — в `~/.local/state/quietline/`.
"""

import argparse
import curses
import os
import shutil
import subprocess
import sys
import threading
from contextlib import contextmanager, nullcontext
from pathlib import Path

from quietline_install import screens as screen_module
from quietline_install import snapshot
from quietline_install.catalog import Catalog, Plan, load_catalog
from quietline_install.runner import Ctx, Runner, State, StepFailed, System, read_system_file
from quietline_install.screens import CheckResult, Checklist, GoBack, Item, Quit
from quietline_install.steps import build_steps, session
from quietline_install.steps.aur import aur_install, aur_outdated
from quietline_install.steps.checks import readiness, run_checks
from quietline_install.steps.packages import quietline_package_step

REPO = Path(__file__).resolve().parents[2]


class CursesScreens:
    """Каждый экран — отдельный сеанс curses: между экранами терминал обычный, шаги печатают в него."""

    @staticmethod
    def _show(function, *args):
        return curses.wrapper(lambda stdscr: function(stdscr, *args))

    def ask_language(self):
        return self._show(screen_module.ask_language)

    def show_checks(self, ctx, results):
        return self._show(screen_module.show_checks, ctx, results)

    def ask_system_language(self, ctx, current):
        return self._show(screen_module.ask_system_language, ctx, current)

    def choose_programs(self, ctx, checklist):
        return self._show(screen_module.choose_programs, ctx, checklist)

    def choose_options(self, ctx, checklist, intro):
        return self._show(screen_module.choose_options, ctx, checklist, intro)

    def confirm_summary(self, ctx, lines):
        return self._show(screen_module.confirm_summary, ctx, lines)

    def show_final(self, ctx, lines):
        return self._show(screen_module.show_final, ctx, lines)

    def ask_resume(self, ctx, failed_step, reason=''):
        return self._show(screen_module.ask_resume, ctx, failed_step, reason)

    def review_package(self, ctx, name, lines):
        return self._show(screen_module.review_package, ctx, name, lines)


def preflight(ctx: Ctx, info: snapshot.RootInfo) -> list[CheckResult]:
    """Arch, не root, сеть, sudo, не загруженный снимок — обязательны; Btrfs — предупреждение с причиной."""
    release = read_system_file(ctx, '/etc/os-release') or ''
    kind, reason = snapshot.snapshot_plan(info)
    return [
        CheckResult('arch', 'ID=arch' in release.splitlines()),
        CheckResult('not-root', os.geteuid() != 0),
        CheckResult('network', ctx.system.ok(['curl', '-fsI', '--max-time', '5', 'https://archlinux.org'])),
        CheckResult('sudo', shutil.which('sudo') is not None),
        CheckResult('booted-snapshot', not info.overlay),
        CheckResult('btrfs', kind != 'none', blocking=False, detail='' if kind != 'none' else ctx.t(reason)),
    ]


def checklist(ctx: Ctx, catalog: Catalog, previous: set[str]) -> Checklist:
    """Разделы каталога; установленное раньше отмечено и неактивно, «Расширенные» — под основным вариантом."""
    def item(entry, children=()):
        installed = entry.id in previous
        return Item(entry.id, entry.name, checked=entry.recommended or installed, locked=installed,
                    children=list(children))

    groups = []
    for section in catalog.sections:
        basic = section.basic_items
        advanced = [item(entry) for entry in section.advanced_items]
        children = [item(entry, advanced if index == 0 else ()) for index, entry in enumerate(basic)]
        groups.append(Item(section.id, ctx.t(section.title_key), group=True, expanded=True, children=children))
    return Checklist(groups, catalog.recommended())


# Пункты экрана «Параметры»: id шага, ключ подписи, отмечен ли по умолчанию.
OPTIONS = {'default-shell': ('options.shell', True), 'docker-group': ('options.docker', False)}


def options_checklist(ctx: Ctx, ids: list[str], answers: dict) -> Checklist:
    """Пункты «Параметров»; прежний ответ сохраняет отметку, иначе — значение по умолчанию."""
    return Checklist([Item(option, ctx.t(OPTIONS[option][0]), checked=answers.get(option, OPTIONS[option][1]))
                      for option in ids], recommended=None)


def options_intro(ctx: Ctx, ids: list[str]) -> str:
    intro = ctx.t('options.intro')
    if 'docker-group' in ids:
        intro += '\n\n' + ctx.t('session.dockerRoot')
    return intro


def summary(ctx: Ctx, catalog: Catalog, selection: set[str], previous: set[str], kind: str,
            options: dict | None = None) -> list[str]:
    chosen = [entry for entry in catalog.items() if entry.id in selection - previous]
    lines = [ctx.t('summary.install')]
    lines += [f'  - {entry.name}' for entry in chosen if entry.source != 'manual']
    manual = [entry for entry in chosen if entry.source == 'manual']
    if manual:
        lines += ['', ctx.t('summary.manual')] + [f'  - {entry.name}' for entry in manual]
    if options:
        lines += ['', ctx.t('options.title') + ':']
        lines += [f'  - {ctx.t(OPTIONS[option][0])}: {ctx.t("ask.yes") if answer else ctx.t("ask.no")}'
                  for option, answer in options.items()]
    lines.append('')
    lines.append(ctx.t('summary.snapshotNone') if kind == 'none' else ctx.t('summary.snapshot', kind=kind))
    return lines


def _plan(catalog: Catalog, state: State) -> Plan:
    ids = set(state.selection.get('ids', [])) | set(state.selection.get('previous', []))
    return catalog.plan(ids)


def _questions(ctx: Ctx, screens) -> tuple[set[str], set[str], dict] | None:
    """Экраны до сводки: выбор, установленное раньше и ответы «Параметров»; None — пользователь вышел.

    Esc возвращает на предыдущий экран; «Параметры» без вопросов пропускаются в обе стороны.
    """
    previous = set(ctx.state.selection.get('ids', [])) | set(ctx.state.selection.get('previous', [])) \
        if ctx.state.finished else set()
    catalog = load_catalog(ctx.repo / 'installer/catalog.toml')
    info = snapshot.inspect_root(ctx)
    kind = snapshot.snapshot_plan(info)[0]
    screen = 0
    selection: set[str] = set()
    # Один список на все заходы: возврат со сводки показывает прежние отметки.
    programs = checklist(ctx, catalog, previous)
    options: dict = {}
    forward = True
    while True:
        try:
            if screen == 0:
                ctx.language = screens.ask_language()
            elif screen == 1:
                if not screens.show_checks(ctx, preflight(ctx, info)):
                    return None
            elif screen == 2:
                current = ctx.state.system_language or ('ru' if os.environ.get('LANG', '').startswith('ru')
                                                        else ctx.language)
                ctx.state.system_language = screens.ask_system_language(ctx, current)
            elif screen == 3:
                chosen = screens.choose_programs(ctx, programs)
                if chosen == 'recommended':
                    programs.apply_recommended(catalog.recommended())
                    selection = catalog.recommended()
                else:
                    selection = set(chosen)
            elif screen == 4:
                ids = session.open_questions(ctx, 'docker' in catalog.plan(selection | previous).repo)
                if not ids:
                    options = {}
                    screen = 5 if forward else 3
                    continue
                marked = screens.choose_options(ctx, options_checklist(ctx, ids, options), options_intro(ctx, ids))
                options = {option: option in marked for option in ids}
            else:
                if screens.confirm_summary(ctx, summary(ctx, catalog, selection | previous, previous, kind,
                                                        options)):
                    return selection, previous, options
                screen, forward = 4, False
                continue
            screen += 1
            forward = True
        except GoBack:
            screen = max(0, screen - 1)
            forward = False
        except Quit:
            return None


def _snapshot(ctx: Ctx) -> None:
    """Снимок корня перед шагами; без `grub-btrfs` или хука снимок всё равно делается, только для записи."""
    kind = snapshot.snapshot_plan(snapshot.inspect_root(ctx))[0]
    if kind in ('btrfs-ro', 'btrfs-rw'):
        try:
            snapshot.prepare(ctx)
        except StepFailed as exc:
            ctx.log(f'snapshot preparation failed, taking a writable snapshot: {exc}')
            kind = 'btrfs-rw'
    if kind == 'none':
        ctx.state.snapshot = {'kind': 'none', 'name': None}
        ctx.state.save()
    else:
        snapshot.take(ctx, kind)


def rollback(ctx: Ctx, confirm: bool = True) -> int:
    """Откат к снимку или по журналу; `confirm` — спросить пользователя (команда `rollback`)."""
    state = ctx.state
    if ctx.dry_run:
        ctx.out(ctx.t('rollback.dryRun'))
        return 1
    if state.rolled_back:
        ctx.out(ctx.t('rollback.already'))
        return 1
    if not state.selection and not state.changes:
        ctx.out(ctx.t('rollback.nothing'))
        return 1
    kind = (state.snapshot or {}).get('kind', 'none')
    if confirm:
        question = (ctx.t('rollback.confirmSnapshot', name=state.snapshot['name'])
                    if kind in ('btrfs-ro', 'btrfs-rw') else ctx.t('rollback.confirm'))
        if not ctx.ask(question, default=False):
            ctx.out(ctx.t('rollback.declined'))
            return 1
    try:
        if kind in ('btrfs-ro', 'btrfs-rw'):
            broken = snapshot.rollback_btrfs(ctx, state.snapshot['name'])
            ctx.out(ctx.t('rollback.broken', name=broken))
            ctx.out(ctx.t('rollback.reboot'))
        else:
            snapshot.rollback_journal(ctx)
    except StepFailed as exc:
        ctx.out(f'{exc} {exc.action}')
        return 1
    state.rolled_back = True
    state.save()
    ctx.out(ctx.t('rollback.done'))
    return 0


def _missing_packages(ctx: Ctx, plan: Plan) -> list[str]:
    return [name for name in plan.repo if not ctx.system.ok(['pacman', '-Si', name])]


# Как часто продлевается отметка sudo, пока идут шаги: заметно меньше пяти минут sudo по умолчанию.
SUDO_REFRESH = 60


@contextmanager
def sudo_kept(ctx: Ctx, interval: float = SUDO_REFRESH):
    """Пароль sudo спрашивается один раз; пока работает блок, отметка sudo продлевается без вопросов."""
    ctx.out(ctx.t('sudo.once'))
    try:
        ctx.system.run(['sudo', '-v'], interactive=True)
    except subprocess.CalledProcessError as exc:
        raise StepFailed('sudo did not accept the password', 'Run ./install.sh again.') from exc
    stop = threading.Event()

    def refresh() -> None:
        while not stop.wait(interval):
            ctx.system.ok(['sudo', '-n', '-v'])

    thread = threading.Thread(target=refresh, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join()


def final_lines(ctx: Ctx, plan: Plan) -> list[str]:
    """Итог: одна строка «всё готово» или только отсутствующее; полный список — `./install.sh check`."""
    items = readiness(ctx, plan)
    missing = [name for name, ok in items if not ok]
    lines = [ctx.t('final.done'), '']
    if not missing:
        return lines + [ctx.t('final.ready', count=len(items))]
    return lines + [ctx.t('final.missing', count=len(missing), total=len(items))] + \
        [f'  - {name}' for name in missing] + ['', ctx.t('final.fullCheck')]


def _install(ctx: Ctx, screens, runner_log: Path, start: str | None) -> int:
    """Снимок (если его ещё нет) и шаги; без снимка или его явного отсутствия шаги не начинаются."""
    catalog = load_catalog(ctx.repo / 'installer/catalog.toml')
    plan = _plan(catalog, ctx.state)
    if not ctx.dry_run and ctx.state.snapshot is None:
        missing = _missing_packages(ctx, plan)
        if missing:
            ctx.out(ctx.t('checks.missingPackages', names=', '.join(missing)))
            return 1
    with nullcontext() if ctx.dry_run else sudo_kept(ctx):
        if not ctx.dry_run and ctx.state.snapshot is None:
            _snapshot(ctx)
        while True:
            runner = Runner(build_steps(plan), ctx, runner_log)
            try:
                finished = runner.run(start)
            except StepFailed as exc:
                ctx.out(f'{exc} {exc.action}')
                return 1
            if finished:
                break
            choice = screens.ask_resume(ctx, ctx.state.failed, ctx.state.error or '')
            if choice == 'rollback':
                return rollback(ctx, confirm=False)
            if choice != 'continue':
                return 1
            start = ctx.state.failed
    if ctx.dry_run:
        return 0
    if screens.show_final(ctx, final_lines(ctx, plan)):
        ctx.system.run(['systemctl', 'reboot'], check=False)
    return 0


def main(argv=None, screens=None, system=None, home: Path | None = None, root: Path = Path('/'),
         ask=None, out=print, review=None) -> int:
    parser = argparse.ArgumentParser(prog='install.sh', description='Install the Quietline desktop on Arch Linux.')
    parser.add_argument('command', nargs='?', default='run', choices=['run', 'status', 'check', 'rollback', 'update'])
    parser.add_argument('--dry-run', action='store_true', help='show the steps without changing anything')
    parser.add_argument('--from', dest='start', metavar='ID', help='start from this step')
    parser.add_argument('--repo', type=Path, default=REPO, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    home = home or Path.home()
    state_dir = home / '.local/state/quietline'
    state = State.load(state_dir / 'install.json')
    ctx = Ctx(system=None, home=home, repo=args.repo, ask=lambda question, default=False: False, out=out,
              dry_run=args.dry_run, root=root, language=state.installer_language or 'en', state=state)
    logger = Runner([], ctx, state_dir / 'install.log')
    ctx.system = system or System(log=lambda line: ctx.log(line))
    ctx.ask = ask or (lambda question, default=False: screen_module.ask_yes_no(ctx, question, default))
    if review is None and screens is None:
        review = lambda name, lines: CursesScreens().review_package(ctx, name, lines)
    ctx.review = review
    screens = screens or CursesScreens()
    catalog_path = args.repo / 'installer/catalog.toml'

    if args.command == 'rollback':
        return rollback(ctx)
    if args.command == 'status':
        for step_id, status in Runner(build_steps(_plan(load_catalog(catalog_path), state)), ctx,
                                      logger.log_path).status():
            out(f'{step_id}: {status}')
        return 0
    if args.command == 'check':
        lines, ok = run_checks(ctx, _plan(load_catalog(catalog_path), state))
        for line in lines:
            out(line)
        return 0 if ok else 1
    if args.command == 'update':
        out(ctx.t('update.hint'))
        code = 0
        # Пакет `quietline` из клона: пересобирается, если его версия отстала от коммита клона.
        package = quietline_package_step()
        try:
            if package.check(ctx):
                out(ctx.t('update.quietlineCurrent'))
            else:
                out(ctx.t('update.quietlineRebuild'))
                package.run(ctx)
        except (subprocess.CalledProcessError, OSError) as error:
            out(ctx.t('update.quietlineFailed', error=str(error)))
            code = 1
        outdated = aur_outdated(ctx, _plan(load_catalog(catalog_path), state).aur)
        for name in outdated:
            aur_install(ctx, name)
        if not outdated:
            out(ctx.t('update.none'))
        # Заголовки окон собраны под прежний Hyprland: hyprpm пересобирает их под установленный.
        ctx.system.run(['hyprpm', 'update'], interactive=True, check=False)
        return code

    try:
        if state.selection and not state.finished and not state.rolled_back:
            failed = state.failed or next((step.id for step in build_steps(_plan(load_catalog(catalog_path), state))
                                           if step.id not in state.done), '')
            choice = screens.ask_resume(ctx, failed, state.error or '')
            if choice == 'rollback':
                return rollback(ctx, confirm=False)
            if choice != 'continue':
                return 1
            if snapshot.inspect_root(ctx).overlay:
                out(ctx.t('resume.bootedSnapshot'))
                return 1
            return _install(ctx, screens, logger.log_path, args.start or state.failed)
        answers = _questions(ctx, screens)
        if answers is None:
            return 1
        selection, previous, options = answers
        system_language = state.system_language
        state = State(path=None if args.dry_run else state.path, installer_language=ctx.language,
                      system_language=system_language,
                      selection={'ids': sorted(selection), 'previous': sorted(previous), 'options': options})
        ctx.state = state
        if not args.dry_run:
            state.save()
        return _install(ctx, screens, logger.log_path, args.start)
    except StepFailed as exc:
        out(f'{exc} {exc.action}')
        return 1
    except KeyboardInterrupt:
        out(ctx.t('error.next'))
        return 130


if __name__ == '__main__':
    sys.exit(main())
