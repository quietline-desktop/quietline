import json
import os
import subprocess

import pytest

from quietline_install.runner import Runner, State, Step, StepFailed, redact
from quietline_install.runner import System


def make_step(step_id, done, calls, fail_times=0):
    state = {'done': done, 'fails': fail_times}

    def run(ctx):
        calls.append(step_id)
        if state['fails']:
            state['fails'] -= 1
            raise StepFailed('network is down', 'Check the connection.')
        state['done'] = True

    return Step(step_id, f'title.{step_id}', 'Arch repositories', lambda ctx: state['done'], run)


def runner(ctx, steps, tmp_path):
    return Runner(steps, ctx, tmp_path / 'install.log')


def state_file(ctx):
    return json.loads(ctx.state.path.read_text())


def test_done_steps_are_not_repeated(ctx, tmp_path):
    calls = []
    steps = [make_step('A', True, calls), make_step('B', True, calls), make_step('C', False, calls)]
    assert runner(ctx, steps, tmp_path).run() is True
    assert calls == ['C']
    assert 'C' in state_file(ctx)['done'] and state_file(ctx)['finished'] is True


def test_resume_starts_at_failed_step(ctx, tmp_path):
    calls = []
    steps = [make_step('A', False, calls), make_step('B', False, calls, fail_times=1), make_step('C', False, calls)]
    assert runner(ctx, steps, tmp_path).run() is False
    state = state_file(ctx)
    assert state['failed'] == 'B' and 'network is down' in state['error'] and state['finished'] is False
    assert calls == ['A', 'B']
    assert any('Check the connection.' in line and './install.sh' in line for line in ctx.lines)
    assert runner(ctx, steps, tmp_path).run() is True
    assert calls == ['A', 'B', 'B', 'C']
    assert state_file(ctx)['failed'] is None


def test_start_skips_earlier_steps(ctx, tmp_path):
    calls = []
    steps = [make_step('A', False, calls), make_step('B', False, calls)]
    assert runner(ctx, steps, tmp_path).run('B') is True
    assert calls == ['B']


def test_dry_run_changes_nothing(ctx, tmp_path):
    calls = []
    ctx.dry_run = True
    steps = [make_step('A', False, calls), make_step('B', True, calls)]
    assert runner(ctx, steps, tmp_path).run() is True
    assert calls == []
    assert not ctx.state.path.exists()
    log = (tmp_path / 'install.log').read_text()
    assert 'A [Arch repositories]: will run' in log and 'B [Arch repositories]: skipped (already done)' in log


def test_log_redacts_secrets():
    token = 'ghp_' + 'A1b2C3d4' * 5
    text = ('password=hunter2\nAuthorization: Bearer abc.def\n' + token +
            '\n-----BEGIN OPENSSH PRIVATE KEY-----\nAAAAsecret\n-----END OPENSSH PRIVATE KEY-----\nok')
    clean = redact(text)
    for secret in ('hunter2', 'abc.def', token, 'AAAAsecret'):
        assert secret not in clean
    assert clean.endswith('ok')


@pytest.mark.parametrize('line, secret', [
    ('access_token=abc123', 'abc123'),
    ('GITHUB_TOKEN=xyz789', 'xyz789'),
    ('db_secret: s3cr3t', 's3cr3t'),
    ('{"password": "hunter2"}', 'hunter2'),
    ('{"password":"hunter2","user":"kiryl"}', 'hunter2'),
    ('nmcli con add --password hunter2 ssid', 'hunter2'),
    ('nmcli con modify x wifi-sec.psk hunter2', 'hunter2'),
    ('Authorization: Basic dXNlcjpwYXNz', 'dXNlcjpwYXNz'),
    ('Authorization: Bearer abc.def', 'abc.def'),
    ('password="two words"', 'words'),
    ("password='two words'", 'words'),
    ('PASSWORD=Hunter2', 'Hunter2'),
])
def test_redact_hides_common_secret_shapes(line, secret):
    assert secret not in redact(line)


def test_redact_keeps_ordinary_text():
    assert redact('installing token-free package, user kiryl') == 'installing token-free package, user kiryl'


def test_step_output_shows_source_and_result(ctx, tmp_path):
    calls = []
    steps = [make_step('A', True, calls), make_step('B', False, calls), make_step('C', False, calls, fail_times=1)]
    runner(ctx, steps, tmp_path).run()
    out = '\n'.join(ctx.lines)
    log = (tmp_path / 'install.log').read_text()
    for text in (out, log):
        assert 'A [Arch repositories]: skipped (already done)' in text
        assert 'B [Arch repositories]: running' in text and 'B [Arch repositories]: done' in text
        assert 'C [Arch repositories]: failed: network is down' in text


def test_log_lines_have_timestamp_and_are_redacted(ctx, tmp_path):
    runner(ctx, [], tmp_path).log('token=abc123')
    line = (tmp_path / 'install.log').read_text().strip()
    assert 'abc123' not in line and line.endswith('token=***')
    assert len(line.split(' ', 2)[0]) == 10 and line.split(' ', 2)[1].count(':') == 2


def test_status_reports_each_step(ctx, tmp_path):
    calls = []
    steps = [make_step('A', True, calls), make_step('B', False, calls)]
    assert runner(ctx, steps, tmp_path).status() == [('A', 'done'), ('B', 'pending')]


def test_status_marks_the_failed_step(ctx, tmp_path):
    calls = []
    steps = [make_step('A', True, calls), make_step('B', False, calls, fail_times=1)]
    run = runner(ctx, steps, tmp_path)
    run.run()
    assert run.status() == [('A', 'done'), ('B', 'failed')]


def test_missing_command_is_a_failed_command_not_a_crash():
    assert System().run(['quietline-no-such-command'], check=False) == ''
    with pytest.raises(subprocess.CalledProcessError) as error:
        System().run(['quietline-no-such-command'])
    assert error.value.returncode == 127


def test_system_logs_commands_and_prefixes_sudo(monkeypatch):
    import types
    seen = []

    def fake_run(command, **kwargs):
        seen.append(command)
        return types.SimpleNamespace(returncode=0, stdout='', stderr='')
    monkeypatch.setattr(subprocess, 'run', fake_run)
    lines = []
    System(lines.append).run(['true'])
    System(lines.append).run(['true'], sudo=True, check=False)
    assert seen == [['true'], ['sudo', 'true']]
    assert lines == ['$ true', '$ sudo true']


def test_crashing_check_counts_as_not_done(ctx, tmp_path):
    calls = []

    def broken(ctx):
        raise FileNotFoundError('pacman')
    steps = [Step('A', 'title.A', 'Arch repositories', broken, lambda ctx: calls.append('A'))]
    ctx.dry_run = True
    assert runner(ctx, steps, tmp_path).run() is True
    assert any('A [Arch repositories]: will run' in line for line in ctx.lines)


def test_result_check_failure_stops_the_step(ctx, tmp_path):
    steps = [Step('A', 'title.A', 'Arch repositories', lambda ctx: False, lambda ctx: None)]
    assert runner(ctx, steps, tmp_path).run() is False
    assert state_file(ctx)['failed'] == 'A'


def test_unknown_start_step_is_an_error(ctx, tmp_path):
    steps = [make_step('A', False, [])]
    with pytest.raises(StepFailed):
        runner(ctx, steps, tmp_path).run('nope')


def test_second_runner_is_refused_while_locked(ctx, tmp_path):
    first, second = runner(ctx, [], tmp_path), runner(ctx, [], tmp_path)
    with first.locked():
        with pytest.raises(StepFailed, match='another installer is running'):
            second.run()
    assert second.run() is True


def test_corrupt_state_is_kept_aside_and_starts_empty(tmp_path):
    path = tmp_path / 'state' / 'install.json'
    path.parent.mkdir()
    path.write_text('{not json')
    state = State.load(path)
    assert state.done == {} and state.changes == [] and state.failed is None
    assert not path.exists()
    (kept,) = path.parent.glob('install.json.broken-*')
    assert kept.read_text() == '{not json'


def test_wrongly_shaped_state_counts_as_corrupt(tmp_path):
    path = tmp_path / 'install.json'
    path.write_text(json.dumps({'version': 1, 'done': [], 'changes': {}}))
    assert State.load(path).done == {}
    assert len(list(tmp_path.glob('install.json.broken-*'))) == 1


def test_missing_state_starts_empty_without_files(tmp_path):
    state = State.load(tmp_path / 'install.json')
    assert state.version == 1 and state.snapshot is None and state.finished is False
    assert list(tmp_path.iterdir()) == []


def test_state_roundtrip_uses_documented_keys(tmp_path):
    path = tmp_path / 'install.json'
    state = State.load(path)
    state.installer_language, state.system_language = 'ru', 'en'
    state.selection = {'apps': ['firefox']}
    state.snapshot = {'kind': 'btrfs-ro', 'name': 'quietline-1'}
    state.save()
    raw = json.loads(path.read_text())
    assert raw['installerLanguage'] == 'ru' and raw['systemLanguage'] == 'en'
    assert raw['snapshot'] == {'kind': 'btrfs-ro', 'name': 'quietline-1'}
    again = State.load(path)
    assert again.installer_language == 'ru' and again.selection == {'apps': ['firefox']}


def test_changes_journal_survives_reload(ctx):
    changes = [{'kind': 'file', 'path': '/home/u/.config/hypr/hyprland.lua', 'backup': '/home/u/x.quietline-1'},
               {'kind': 'file', 'path': '/home/u/new', 'backup': None},
               {'kind': 'package', 'name': 'fnm'},
               {'kind': 'flatpak', 'id': 'com.brave.Browser'},
               {'kind': 'service', 'unit': 'bluetooth.service'}]
    for change in changes:
        ctx.record(change)
    assert State.load(ctx.state.path).changes == changes


def test_state_and_log_are_private(ctx, tmp_path):
    runner(ctx, [make_step('A', False, [])], tmp_path).run()
    for path in (ctx.state.path, tmp_path / 'install.log'):
        assert os.stat(path).st_mode & 0o777 == 0o600
