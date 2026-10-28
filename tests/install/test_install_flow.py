"""Порядок экранов и шагов установщика, продолжение, откат, проверки install.sh."""

import os
import subprocess
from pathlib import Path

import pytest

import quietline_install.__main__ as main_module
from quietline_install.runner import State, Step, StepFailed
from quietline_install.screens import Quit
from quietline_install.snapshot import RootInfo

REPO = Path(__file__).resolve().parents[2]
BTRFS = RootInfo(fstype='btrfs', device='/dev/nvme0n1p8', subvol='/@', boot_inside=True, systemd_hook=False,
                 overlay=False, swapfile_in_root=False)
EXT4 = RootInfo(fstype='ext4', device='/dev/sda2', subvol=None, boot_inside=True, systemd_hook=False,
                overlay=False, swapfile_in_root=False)


class FakeScreens:
    """Отвечает за экраны по сценарию и записывает их порядок."""

    def __init__(self, programs='recommended', summary=True, checks=True, resume='continue', final=False):
        self.calls = []
        self.programs, self.summary, self.checks = programs, summary, checks
        self.resume, self.final = resume, final

    def ask_language(self):
        self.calls.append('language')
        return 'en'

    def show_checks(self, ctx, results):
        self.calls.append('checks')
        self.results = results
        return self.checks

    def ask_system_language(self, ctx, current):
        self.calls.append('system-language')
        return 'ru'

    def choose_programs(self, ctx, checklist):
        self.calls.append('programs')
        self.checklist = checklist
        if isinstance(self.programs, Exception):
            raise self.programs
        return self.programs

    def confirm_summary(self, ctx, lines):
        self.calls.append('summary')
        self.summary_lines = lines
        return self.summary

    def show_final(self, ctx, lines):
        self.calls.append('final')
        return self.final

    def ask_resume(self, ctx, failed_step):
        self.calls.append(f'resume:{failed_step}')
        return self.resume


@pytest.fixture
def env(tmp_path, system, monkeypatch):
    home = tmp_path / 'home'
    home.mkdir()
    events = []
    monkeypatch.setattr(main_module.snapshot, 'inspect_root', lambda ctx: BTRFS)
    monkeypatch.setattr(main_module.snapshot, 'prepare', lambda ctx: events.append('prepare'))

    def take(ctx, kind):
        events.append(f'take:{kind}')
        ctx.state.snapshot = {'kind': kind, 'name': 'quietline-pre-20261028-120000'}
        ctx.state.save()
        return 'quietline-pre-20261028-120000'

    monkeypatch.setattr(main_module.snapshot, 'take', take)
    monkeypatch.setattr(main_module, 'preflight', lambda ctx, info: [])
    monkeypatch.setattr(main_module, 'run_checks', lambda ctx, plan: (['all — ready'], True))

    def steps(plan):
        def run(name):
            return lambda ctx: events.append(f'step:{name}')
        return [Step('one', 'step.repo-packages', 'test', lambda ctx: f'step:one' in events, run('one')),
                Step('two', 'step.greetd', 'test', lambda ctx: f'step:two' in events, run('two'))]

    monkeypatch.setattr(main_module, 'build_steps', steps)

    def call(argv, screens):
        return main_module.main(argv, screens=screens, system=system, home=home, root=tmp_path / 'root',
                                ask=lambda question: True, out=lambda line: None)

    return {'home': home, 'events': events, 'call': call,
            'state': home / '.local/state/quietline/install.json'}


def test_first_run_walks_screens_in_spec_order(env):
    screens = FakeScreens()
    assert env['call']([], screens) == 0
    assert screens.calls == ['language', 'checks', 'system-language', 'programs', 'summary', 'final']
    state = State.load(env['state'])
    assert state.installer_language == 'en' and state.system_language == 'ru' and state.finished


def test_quit_before_summary_changes_nothing(env, system):
    screens = FakeScreens(programs=Quit())
    assert env['call']([], screens) != 0
    assert not any(call['sudo'] for call in system.calls)
    assert env['events'] == []
    assert not env['state'].exists()


def test_declined_summary_returns_to_programs(env):
    answers = iter([False, True])
    screens = FakeScreens()
    screens.confirm_summary = lambda ctx, lines: (screens.calls.append('summary'), next(answers))[1]
    assert env['call']([], screens) == 0
    assert screens.calls[:6] == ['language', 'checks', 'system-language', 'programs', 'summary', 'programs']


def test_snapshot_is_taken_before_first_changing_step(env):
    env['call']([], FakeScreens())
    assert env['events'] == ['prepare', 'take:btrfs-ro', 'step:one', 'step:two']


def test_failed_prepare_falls_back_to_writable_snapshot(env, monkeypatch):
    def prepare(ctx):
        raise StepFailed('no grub-btrfs')

    monkeypatch.setattr(main_module.snapshot, 'prepare', prepare)
    env['call']([], FakeScreens())
    assert env['events'][0] == 'take:btrfs-rw'


def test_non_btrfs_requires_explicit_consent(env, monkeypatch):
    monkeypatch.setattr(main_module.snapshot, 'inspect_root', lambda ctx: EXT4)
    screens = FakeScreens(checks=False)
    assert env['call']([], screens) != 0
    assert screens.calls == ['language', 'checks']
    assert env['events'] == []

    screens = FakeScreens(checks=True)
    assert env['call']([], screens) == 0
    assert 'prepare' not in env['events'] and not any(e.startswith('take') for e in env['events'])
    assert State.load(env['state']).snapshot == {'kind': 'none', 'name': None}


def test_rerun_offers_continue_or_rollback(env, monkeypatch):
    def failing(ctx):
        raise StepFailed('network is down')

    original = main_module.build_steps
    monkeypatch.setattr(main_module, 'build_steps', lambda plan: [
        original(plan)[0], Step('two', 'step.greetd', 'test', lambda ctx: False, failing)])
    first = FakeScreens(resume='quit')
    assert env['call']([], first) != 0
    assert first.calls[-1] == 'resume:two'
    state = State.load(env['state'])
    assert state.failed == 'two' and not state.finished

    monkeypatch.setattr(main_module, 'build_steps', original)
    again = FakeScreens(resume='continue')
    assert env['call']([], again) == 0
    assert again.calls[0] == 'resume:two'
    assert 'language' not in again.calls and 'programs' not in again.calls
    assert env['events'].count('step:one') == 1


def test_rollback_uses_btrfs_when_snapshot_exists_and_journal_otherwise(env, monkeypatch):
    done = []
    monkeypatch.setattr(main_module.snapshot, 'rollback_btrfs', lambda ctx, name: done.append(('btrfs', name)) or '@broken-x')
    monkeypatch.setattr(main_module.snapshot, 'rollback_journal', lambda ctx: done.append(('journal', None)))
    state = State(path=env['state'], installer_language='en', system_language='en',
                  selection={'ids': [], 'previous': []}, failed='two',
                  snapshot={'kind': 'btrfs-ro', 'name': 'quietline-pre-20261028-120000'})
    state.save()
    assert env['call'](['rollback'], FakeScreens()) == 0
    assert done == [('btrfs', 'quietline-pre-20261028-120000')]
    assert State.load(env['state']).rolled_back is True
    assert env['call'](['rollback'], FakeScreens()) != 0
    assert len(done) == 1

    state = State(path=env['state'], installer_language='en', system_language='en',
                  selection={'ids': [], 'previous': []}, failed='two', snapshot={'kind': 'none', 'name': None})
    state.save()
    assert env['call'](['rollback'], FakeScreens()) == 0
    assert done[-1] == ('journal', None)


def test_finished_install_starts_a_new_run_with_installed_items_locked(env):
    env['call']([], FakeScreens())
    screens = FakeScreens(programs=set())
    env['events'].clear()
    assert env['call']([], screens) == 0
    assert screens.calls[0] == 'language'
    locked = {item.id for group in screens.checklist.items for item in group.children if item.locked}
    assert 'chrome' in locked and 'telegram' in locked


def test_dry_run_takes_no_snapshot_and_runs_nothing(env):
    assert env['call'](['--dry-run'], FakeScreens()) == 0
    assert env['events'] == []


def run_install_sh(tmp_path, uid, os_release):
    fake = tmp_path / 'bin'
    fake.mkdir(parents=True)
    (fake / 'id').write_text(f'#!/bin/sh\necho {uid}\n')
    (fake / 'id').chmod(0o755)
    release = tmp_path / 'os-release'
    release.write_text(os_release)
    env = {**os.environ, 'PATH': f'{fake}:{os.environ["PATH"]}', 'QUIETLINE_OS_RELEASE': str(release),
           'TERM': 'xterm'}
    return subprocess.run(['sh', str(REPO / 'install.sh'), '--help'], capture_output=True, text=True, env=env)


def test_install_sh_refuses_root_and_non_arch(tmp_path):
    root = run_install_sh(tmp_path / 'a', 0, 'ID=arch\n')
    assert root.returncode != 0 and 'root' in root.stderr
    other = run_install_sh(tmp_path / 'b', 1000, 'ID=ubuntu\n')
    assert other.returncode != 0 and 'Arch' in other.stderr


def test_install_sh_never_syncs_databases_alone():
    text = (REPO / 'install.sh').read_text()
    assert 'pacman -S --needed python git' in text
    assert '-Sy ' not in text and '-Sy\n' not in text and '--noconfirm' not in text
    assert 'setfont cyr-sun16' in text
