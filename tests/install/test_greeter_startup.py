"""Команды реального Lua-конфига запускают экран входа и завершают его композитор."""

import os
from pathlib import Path
import shutil
import subprocess

import pytest


LUA = shutil.which('lua')
pytestmark = pytest.mark.skipif(LUA is None, reason='Lua is required to execute the greeter config')
CONFIG = Path(__file__).resolve().parents[2] / 'config/greeter/hyprland.lua'
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
        'qs': 'printf started > "$QS_LOG"\nexit "$QS_CODE"',
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
               EXIT_LOG=str(exit_log), QS_LOG=str(qs_log))
    command = commands[0 if mode == 'startup' else 1]
    result = subprocess.run(['sh', '-c', command], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert qs_log.exists() == (mode == 'startup')
    assert marker.exists() == failed
    assert exit_log.read_text().strip() == 'dispatch hl.dsp.exit()'
