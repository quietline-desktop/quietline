"""Установщик Quietline: `python -m quietline_install [run|status|check|rollback|update] [--dry-run] [--from ID]`.

`run` (по умолчанию): незавершённая установка — экран «Продолжить / Откатить / Выйти»; иначе экраны
по порядку: язык установщика → проверки → язык системы → программы → сводка. После согласия —
снимок корня (Btrfs), затем шаги. Состояние и журнал — в `~/.local/state/quietline/`.
"""

import argparse
import curses
import os
import shutil
import sys
from pathlib import Path

from quietline_install import screens as screen_module
from quietline_install import snapshot
from quietline_install.catalog import Catalog, Plan, load_catalog
from quietline_install.runner import Ctx, Runner, State, StepFailed, System, read_system_file
from quietline_install.screens import CheckResult, Checklist, GoBack, Item, Quit
from quietline_install.steps import build_steps
from quietline_install.steps.aur import aur_install, aur_outdated
from quietline_install.steps.checks import run_checks

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

    def confirm_summary(self, ctx, lines):
        return self._show(screen_module.confirm_summary, ctx, lines)

    def show_final(self, ctx, lines):
        return self._show(screen_module.show_final, ctx, lines)

    def ask_resume(self, ctx, failed_step):
        return self._show(screen_module.ask_resume, ctx, failed_step)


def preflight(ctx: Ctx, info: snapshot.RootInfo) -> list[CheckResult]:
    """Arch, не root, сеть, sudo — обязательны; Btrfs — предупреждение с причиной."""
    release = read_system_file(ctx, '/etc/os-release') or ''
    kind, reason = snapshot.snapshot_plan(info)
    return [
        CheckResult('arch', 'ID=arch' in release.splitlines()),
        CheckResult('not-root', os.geteuid() != 0),
        CheckResult('network', ctx.system.ok(['curl', '-fsI', '--max-time', '5', 'https://archlinux.org'])),
        CheckResult('sudo', shutil.which('sudo') is not None),
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
    return Checklist(groups)


def summary(ctx: Ctx, catalog: Catalog, selection: set[str], previous: set[str], kind: str) -> list[str]:
    chosen = [entry for entry in catalog.items() if entry.id in selection - previous]
    lines = [ctx.t('summary.install')]
    lines += [f'  - {entry.name}' for entry in chosen if entry.source != 'manual']
    manual = [entry for entry in chosen if entry.source == 'manual']
    if manual:
        lines += ['', ctx.t('summary.manual')] + [f'  - {entry.name}' for entry in manual]
    lines.append('')
    lines.append(ctx.t('summary.snapshotNone') if kind == 'none' else ctx.t('summary.snapshot', kind=kind))
    return lines


def _plan(catalog: Catalog, state: State) -> Plan:
    ids = set(state.selection.get('ids', [])) | set(state.selection.get('previous', []))
    return catalog.plan(ids)


def _questions(ctx: Ctx, screens) -> tuple[set[str], set[str]] | None:
    """Экраны до сводки; None — пользователь вышел. Esc возвращает на предыдущий экран."""
    previous = set(ctx.state.selection.get('ids', [])) | set(ctx.state.selection.get('previous', [])) \
        if ctx.state.finished else set()
    catalog = load_catalog(ctx.repo / 'installer/catalog.toml')
    info = snapshot.inspect_root(ctx)
    kind = snapshot.snapshot_plan(info)[0]
    screen = 0
    selection: set[str] = set()
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
                chosen = screens.choose_programs(ctx, checklist(ctx, catalog, previous))
                selection = catalog.recommended() if chosen == 'recommended' else set(chosen)
            else:
                if screens.confirm_summary(ctx, summary(ctx, catalog, selection | previous, previous, kind)):
                    return selection, previous
                screen = 3
                continue
            screen += 1
        except GoBack:
            screen = max(0, screen - 1)
        except Quit:
            return None


def _snapshot(ctx: Ctx) -> None:
    kind = snapshot.snapshot_plan(snapshot.inspect_root(ctx))[0]
    if kind == 'btrfs-ro':
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


def rollback(ctx: Ctx) -> int:
    state = ctx.state
    if state.rolled_back:
        ctx.out(ctx.t('rollback.already'))
        return 1
    if not state.selection and not state.changes:
        ctx.out(ctx.t('rollback.nothing'))
        return 1
    try:
        kind = (state.snapshot or {}).get('kind', 'none')
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


def _install(ctx: Ctx, screens, runner_log: Path, start: str | None) -> int:
    catalog = load_catalog(ctx.repo / 'installer/catalog.toml')
    plan = _plan(catalog, ctx.state)
    while True:
        runner = Runner(build_steps(plan), ctx, runner_log)
        try:
            finished = runner.run(start)
        except StepFailed as exc:
            ctx.out(f'{exc} {exc.action}')
            return 1
        if finished:
            break
        choice = screens.ask_resume(ctx, ctx.state.failed)
        if choice == 'rollback':
            return rollback(ctx)
        if choice != 'continue':
            return 1
        start = ctx.state.failed
    if ctx.dry_run:
        return 0
    lines, _ = run_checks(ctx, plan)
    if screens.show_final(ctx, [ctx.t('final.done'), '', ctx.t('final.checks'), *lines]):
        ctx.system.run(['systemctl', 'reboot'], check=False)
    return 0


def _terminal_ask(ctx: Ctx):
    def ask(question: str) -> bool:
        try:
            answer = input(f'{question} {ctx.t("ask.suffix")} ').strip().lower()
        except EOFError:
            return False
        return answer in ('y', 'yes', ctx.t('ask.yes'), 'да')
    return ask


def main(argv=None, screens=None, system=None, home: Path | None = None, root: Path = Path('/'),
         ask=None, out=print) -> int:
    parser = argparse.ArgumentParser(prog='install.sh', description='Install the Quietline desktop on Arch Linux.')
    parser.add_argument('command', nargs='?', default='run', choices=['run', 'status', 'check', 'rollback', 'update'])
    parser.add_argument('--dry-run', action='store_true', help='show the steps without changing anything')
    parser.add_argument('--from', dest='start', metavar='ID', help='start from this step')
    parser.add_argument('--repo', type=Path, default=REPO, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    home = home or Path.home()
    state_dir = home / '.local/state/quietline'
    state = State.load(state_dir / 'install.json')
    ctx = Ctx(system=None, home=home, repo=args.repo, ask=lambda question: False, out=out,
              dry_run=args.dry_run, root=root, language=state.installer_language or 'en', state=state)
    logger = Runner([], ctx, state_dir / 'install.log')
    ctx.system = system or System(log=lambda line: ctx.log(line))
    ctx.ask = ask or _terminal_ask(ctx)
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
        outdated = aur_outdated(ctx, _plan(load_catalog(catalog_path), state).aur)
        for name in outdated:
            aur_install(ctx, name)
        if not outdated:
            out(ctx.t('update.none'))
        return 0

    try:
        if state.selection and not state.finished and not state.rolled_back:
            failed = state.failed or next((step.id for step in build_steps(_plan(load_catalog(catalog_path), state))
                                           if step.id not in state.done), '')
            choice = screens.ask_resume(ctx, failed)
            if choice == 'rollback':
                return rollback(ctx)
            if choice != 'continue':
                return 1
            return _install(ctx, screens, logger.log_path, args.start or state.failed)
        answers = _questions(ctx, screens)
        if answers is None:
            return 1
        selection, previous = answers
        system_language = state.system_language
        state = State(path=None if args.dry_run else state.path, installer_language=ctx.language,
                      system_language=system_language,
                      selection={'ids': sorted(selection), 'previous': sorted(previous)})
        ctx.state = state
        if not args.dry_run:
            state.save()
            _snapshot(ctx)
        return _install(ctx, screens, logger.log_path, args.start)
    except StepFailed as exc:
        out(f'{exc} {exc.action}')
        return 1
    except KeyboardInterrupt:
        out(ctx.t('error.next'))
        return 130


if __name__ == '__main__':
    sys.exit(main())
