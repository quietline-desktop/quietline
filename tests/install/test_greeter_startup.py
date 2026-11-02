"""Команды реального Lua-конфига запускают экран входа и завершают его композитор."""

import os
from pathlib import Path
import shutil
import subprocess

import pytest


LUA = shutil.which('lua')
ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'config/greeter/hyprland.lua'
HARNESS = '''
hl = {
    config = function() end,
    monitor = function() end,
    on = function(_, callback) callback() end,
    exec_cmd = function(command) print(command) end,
    dsp = { exec_cmd = function(command) return command end },
    bind = function(_, command) print(command) end,
}
dofile(arg[1])
'''


@pytest.fixture
def commands():
    if LUA is None:
        pytest.skip('Lua is required to execute the greeter config')
    result = subprocess.run([LUA, '-', str(CONFIG)], input=HARNESS, text=True,
                            capture_output=True, check=True)
    startup, fallback = result.stdout.splitlines()
    return startup, fallback


@pytest.mark.parametrize('mode, qs_code, failed', [
    ('startup', '0', False),
    ('startup', '255', True),
    ('fallback', '0', True),
])
def test_greeter_command_runs_and_exits_compositor(commands, tmp_path, mode, qs_code, failed):
    for name, body in {
        'qs': 'printf started > "$QS_LOG"\n[ "$QS_CODE" = 0 ] && touch "$QUIETLINE_GREETER_READY"\nexit "$QS_CODE"',
        'hyprctl': 'printf "%s\\n" "$*" > "$EXIT_LOG"',
    }.items():
        script = tmp_path / name
        script.write_text('#!/bin/sh\n' + body + '\n')
        script.chmod(0o755)
    marker = tmp_path / 'greeter failed'
    exit_log = tmp_path / 'exit.log'
    qs_log = tmp_path / 'qs.log'
    env = dict(os.environ, PATH=f'{tmp_path}:{os.environ["PATH"]}',
               QUIETLINE_GREETER_FAILED=str(marker), QS_CODE=qs_code,
               QUIETLINE_GREETER_READY=str(tmp_path / 'ready'),
               EXIT_LOG=str(exit_log), QS_LOG=str(qs_log))
    command = commands[0 if mode == 'startup' else 1]
    command = command.replace('/usr/share/quietline/greeter/run-ui', 'sh ' + str(ROOT / 'config/greeter/run-ui'))
    result = subprocess.run(['sh', '-c', command], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert qs_log.exists() == (mode == 'startup')
    assert marker.exists() == failed
    assert exit_log.read_text().strip() == 'dispatch hl.dsp.exit()'


@pytest.mark.parametrize('scenario, fallback', [('broken', True), ('hung', True), ('ready', False)])
def test_launcher_falls_back_without_leaving_ui_process(tmp_path, scenario, fallback):
    import sys
    qs = tmp_path / 'qs'
    qs.write_text(f'''#!{sys.executable}
import os, signal, time
from pathlib import Path
Path(os.environ['UI_PID']).write_text(str(os.getpid()))
mode = os.environ['SCENARIO']
if mode == 'broken':
    raise SystemExit(255)
if mode == 'ready':
    Path(os.environ['QUIETLINE_GREETER_READY']).touch()
    time.sleep(2)
else:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    time.sleep(60)
''')
    qs.chmod(0o755)
    for name, body in {
        'start-hyprland': 'exec sh "$RUN_UI"',
        'hyprctl': 'printf "%s\\n" "$*" > "$EXIT_LOG"',
        'tuigreet': 'touch "$FALLBACK_LOG"',
    }.items():
        script = tmp_path / name
        script.write_text('#!/bin/sh\n' + body + '\n')
        script.chmod(0o755)
    env = dict(os.environ, PATH=f'{tmp_path}:{os.environ["PATH"]}', XDG_RUNTIME_DIR=str(tmp_path),
               SCENARIO=scenario, RUN_UI=str(ROOT / 'config/greeter/run-ui'),
               QUIETLINE_GREETER_STARTUP_SECONDS='1', UI_PID=str(tmp_path / 'ui.pid'),
               EXIT_LOG=str(tmp_path / 'exit.log'), FALLBACK_LOG=str(tmp_path / 'fallback'))
    result = subprocess.run(['sh', str(ROOT / 'config/greeter/quietline-greeter')],
                            env=env, text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / 'fallback').exists() == fallback
    assert (tmp_path / 'exit.log').read_text().strip() == 'dispatch hl.dsp.exit()'
    with pytest.raises(ProcessLookupError):
        os.kill(int((tmp_path / 'ui.pid').read_text()), 0)
