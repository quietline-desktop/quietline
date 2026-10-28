"""Тесты `quietline-shell lock` и `session`: один экран блокировки, выход только без оставшихся окон."""

import io
import json
import subprocess

import pytest

from quietline_shell import session
from quietline_shell.__main__ import main


class FakeHyprland:
    """Окна Hyprland: `close` закрывает окно, если его адрес не в `stubborn`; команды записываются."""

    def __init__(self, clients, stubborn=()):
        self.clients = list(clients)
        self.stubborn = set(stubborn)
        self.commands = []

    def __call__(self, args, **kwargs):
        self.commands.append(list(args))
        if args[:3] == ["hyprctl", "clients", "-j"]:
            return subprocess.CompletedProcess(args, 0, json.dumps(self.clients), "")
        if args[:2] == ["hyprctl", "dispatch"] and "window.close" in args[2]:
            address = args[2].split("address:")[1].split('"')[0]
            if address not in self.stubborn:
                self.clients = [item for item in self.clients if item["address"] != address]
        return subprocess.CompletedProcess(args, 0, "", "")


CLIENTS = [
    {"address": "0xa1", "class": "org.telegram.desktop", "title": "Telegram", "pid": 10},
    {"address": "0xb2", "class": "code", "title": "notes.md — Code", "pid": 20},
]


@pytest.fixture
def clock(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(session.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(session.time, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))
    return now


@pytest.mark.parametrize(("action", "command"), [
    ("reboot", ["systemctl", "reboot"]),
    ("poweroff", ["systemctl", "poweroff"]),
    ("logout", ["hyprctl", "dispatch", "hl.dsp.exit()"]),
])
def test_session_ends_after_every_window_closed(monkeypatch, clock, action, command):
    fake = FakeHyprland(CLIENTS)
    monkeypatch.setattr(subprocess, "run", fake)
    assert session.end_session(action) == {"action": action, "done": True}
    closes = [args[2] for args in fake.commands if args[:2] == ["hyprctl", "dispatch"] and "close" in args[2]]
    assert closes == ['hl.dsp.window.close({window = "address:0xa1"})', 'hl.dsp.window.close({window = "address:0xb2"})']
    assert fake.commands[-1] == command


def test_window_with_unsaved_document_stops_poweroff(monkeypatch, clock):
    fake = FakeHyprland(CLIENTS, stubborn={"0xb2"})
    monkeypatch.setattr(subprocess, "run", fake)
    result = session.end_session("poweroff", timeout=3)
    assert result == {"action": "poweroff", "done": False, "remaining": [{"app": "code", "title": "notes.md — Code"}]}
    assert ["systemctl", "poweroff"] not in fake.commands
    assert clock[0] >= 3


def test_session_without_windows_acts_at_once(monkeypatch, clock):
    fake = FakeHyprland([])
    monkeypatch.setattr(subprocess, "run", fake)
    assert session.end_session("reboot")["done"] is True
    assert fake.commands == [["hyprctl", "clients", "-j"], ["systemctl", "reboot"]]


def test_unknown_action_and_bad_address_are_rejected(monkeypatch):
    monkeypatch.setattr(subprocess, "run", FakeHyprland([]))
    with pytest.raises(ValueError):
        session.end_session("suspend")
    with pytest.raises(ValueError):
        session.close_window('0xa1"}) hl.dsp.exit() --')


def test_windows_skip_entries_without_a_valid_address(monkeypatch):
    clients = [*CLIENTS, {"address": "bad", "class": "x"}, "junk"]
    monkeypatch.setattr(subprocess, "run", FakeHyprland(clients))
    assert [window["address"] for window in session.windows()] == ["0xa1", "0xb2"]


@pytest.fixture
def lock_env(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    screen = tmp_path / "config" / "quickshell" / "quietline" / "lock" / "LockScreen.qml"
    screen.parent.mkdir(parents=True)
    screen.write_text("ShellRoot {}\n")
    started = []

    class Process:
        def __init__(self, args, **kwargs):
            started.append((list(args), kwargs))
            self.pid = 4242

    monkeypatch.setattr(subprocess, "Popen", Process)
    return tmp_path, screen, started


def test_lock_starts_one_detached_lock_screen(lock_env, monkeypatch):
    tmp_path, screen, started = lock_env
    assert session.lock() == {"locked": True}
    args, kwargs = started[0]
    assert args == ["qs", "-p", str(screen)] and kwargs["start_new_session"] is True
    assert (tmp_path / "run" / "quietline" / "lock.pid").read_text() == "4242\n"
    monkeypatch.setattr(session, "_process_alive", lambda pid: pid == 4242)
    assert session.lock() == {"locked": True}
    assert len(started) == 1


def test_stale_pid_file_does_not_block_locking(lock_env, monkeypatch):
    tmp_path, _screen, started = lock_env
    pidfile = tmp_path / "run" / "quietline" / "lock.pid"
    pidfile.parent.mkdir(parents=True)
    pidfile.write_text("99999\n")
    monkeypatch.setattr(session, "_process_alive", lambda pid: False)
    session.lock()
    assert len(started) == 1


def test_missing_lock_screen_is_reported(lock_env):
    _tmp_path, screen, started = lock_env
    screen.unlink()
    with pytest.raises(RuntimeError, match="lock screen not found"):
        session.lock()
    assert started == []


def test_cli_session_reports_remaining_windows(monkeypatch, capsys, clock):
    monkeypatch.setattr(subprocess, "run", FakeHyprland(CLIENTS[:1], stubborn={"0xa1"}))
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert main(["session", "logout", "--timeout", "1"]) == 0
    output = capsys.readouterr().out
    assert output.count("\n") == 1
    assert json.loads(output) == {
        "action": "logout", "done": False, "remaining": [{"app": "org.telegram.desktop", "title": "Telegram"}],
    }


def test_cli_lock_without_runtime_dir_is_an_error(monkeypatch, capsys):
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    assert main(["lock"]) == 1
    assert json.loads(capsys.readouterr().out) == {"error": "XDG_RUNTIME_DIR is not set"}
