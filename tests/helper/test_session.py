"""Тесты `quietline-shell lock` и `session`: один экран блокировки, выход только без оставшихся окон."""

import io
import json
import subprocess
from pathlib import Path

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


def test_forced_session_end_acts_without_closing_windows(monkeypatch, clock):
    fake = FakeHyprland(CLIENTS, stubborn={"0xb2"})
    monkeypatch.setattr(subprocess, "run", fake)
    assert session.end_session("poweroff", force=True) == {"action": "poweroff", "done": True}
    assert not any("close" in args[2] for args in fake.commands if args[:2] == ["hyprctl", "dispatch"])
    assert fake.commands[-1] == ["systemctl", "poweroff"]
    assert clock[0] == 0


def test_session_without_windows_acts_at_once(monkeypatch, clock):
    fake = FakeHyprland([])
    monkeypatch.setattr(subprocess, "run", fake)
    assert session.end_session("reboot")["done"] is True
    assert fake.commands[-1] == ["systemctl", "reboot"]
    assert clock[0] == 0


def test_window_opened_while_waiting_stops_logout(monkeypatch, clock):
    fake = FakeHyprland(CLIENTS)
    original = fake.__call__

    def with_late_dialog(args, **kwargs):
        reply = original(args, **kwargs)
        if args[:2] == ["hyprctl", "dispatch"] and "0xb2" in args[2]:
            fake.clients.append({"address": "0xe9", "class": "code", "title": "Save changes?", "pid": 20})
            fake.stubborn.add("0xe9")
        return reply

    monkeypatch.setattr(subprocess, "run", with_late_dialog)
    result = session.end_session("logout", timeout=2)
    assert result["done"] is False and result["remaining"] == [{"app": "code", "title": "Save changes?"}]
    assert ["hyprctl", "dispatch", "hl.dsp.exit()"] not in fake.commands


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
def lock_env(tmp_path, monkeypatch, clock):
    """Экран блокировки: `behaviour` — `lock` (создаёт метку), `exit` (падает) или `hang` (висит)."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    screen = tmp_path / "config" / "quickshell" / "quietline" / "LockScreen.qml"
    screen.parent.mkdir(parents=True)
    screen.write_text("ShellRoot {}\n")

    class Started(list):
        commands: list
        behaviour = "lock"
        terminated: list

    started = Started()
    started.terminated = []

    class Process:
        def __init__(self, args, **kwargs):
            started.append((list(args), kwargs))
            self.pid = 4242
            if started.behaviour == "lock":
                Path(kwargs["env"]["QUIETLINE_LOCK_MARKER"]).touch()

        def poll(self):
            return 1 if started.behaviour == "exit" else None

        def terminate(self):
            started.terminated.append(self.pid)

    monkeypatch.setattr(subprocess, "Popen", Process)
    commands = []
    monkeypatch.setattr(subprocess, "run", lambda args, **kwargs: commands.append(list(args)) or subprocess.CompletedProcess(args, 0, b"", b""))
    started.commands = commands
    return tmp_path, screen, started


def test_lock_waits_for_the_lock_then_wipes_the_clipboard(lock_env, monkeypatch):
    tmp_path, screen, started = lock_env
    assert session.lock() == {"locked": True}
    args, kwargs = started[0]
    assert args == ["qs", "-p", str(screen)] and kwargs["start_new_session"] is True
    assert kwargs["env"]["QUIETLINE_LOCK_MARKER"] == str(tmp_path / "run" / "quietline" / "lock.secure")
    assert (tmp_path / "run" / "quietline" / "lock.pid").read_text() == "4242\n"
    assert started.commands[-1][0] == "cliphist" and started.commands[-1][-1] == "wipe"


def test_lock_captures_each_monitor_for_the_backdrop(lock_env, monkeypatch):
    tmp_path, _screen, started = lock_env
    state = tmp_path / "run" / "quietline"
    state.mkdir(parents=True)
    (state / "lock-old.png").write_bytes(b"stale")
    commands = []

    def run(args, **kwargs):
        commands.append(list(args))
        reply = b'[{"name": "eDP-1"}, {"name": "../x"}, {"name": "DP-1"}]' if args[:2] == ["hyprctl", "-j"] else b""
        return subprocess.CompletedProcess(args, 0, reply, b"")

    monkeypatch.setattr(subprocess, "run", run)
    assert session.lock() == {"locked": True}
    grims = [command for command in commands if command[0] == "grim"]
    assert grims == [["grim", "-o", "eDP-1", str(state / "lock-eDP-1.png")], ["grim", "-o", "DP-1", str(state / "lock-DP-1.png")]]
    assert not (state / "lock-old.png").exists()
    assert started[0][1]["env"]["QUIETLINE_LOCK_BACKDROPS"] == str(state)


def test_lock_without_monitor_list_still_locks(lock_env, monkeypatch):
    _tmp_path, _screen, started = lock_env
    monkeypatch.setattr(subprocess, "run", lambda args, **kwargs: subprocess.CompletedProcess(args, 0, b"not json", b""))
    assert session.lock() == {"locked": True}
    assert started[0][0][0] == "qs"


def test_running_confirmed_lock_is_not_started_twice(lock_env, monkeypatch):
    _tmp_path, _screen, started = lock_env
    session.lock()
    monkeypatch.setattr(session, "_lock_running", lambda pidfile: 4242)
    assert session.lock() == {"locked": True}
    assert len(started) == 1


def test_unconfirmed_running_lock_is_replaced(lock_env, monkeypatch):
    _tmp_path, _screen, started = lock_env
    killed = []
    monkeypatch.setattr(session, "_lock_running", lambda pidfile: 777)
    monkeypatch.setattr(session.os, "kill", lambda pid, sig: killed.append((pid, sig)))
    session.lock()
    assert killed == [(777, session.signal.SIGTERM)] and len(started) == 1


@pytest.mark.parametrize(("behaviour", "message"), [("exit", "exited before locking"), ("hang", "did not lock in time")])
def test_lock_that_never_locks_is_an_error(lock_env, behaviour, message):
    _tmp_path, _screen, started = lock_env
    started.behaviour = behaviour
    with pytest.raises(RuntimeError, match=message):
        session.lock()
    assert any(args[0] == "notify-send" for args in started.commands)
    assert not any(args[0] == "cliphist" for args in started.commands)
    assert started.terminated == ([4242] if behaviour == "hang" else [])


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


class FakeApps(FakeHyprland):
    """Окна и активное окно Hyprland для `app quit`."""

    def __init__(self, clients, active, stubborn=()):
        super().__init__(clients, stubborn)
        self.active = active

    def __call__(self, args, **kwargs):
        if args[:3] == ["hyprctl", "activewindow", "-j"]:
            self.commands.append(list(args))
            return subprocess.CompletedProcess(args, 0, json.dumps(self.active), "")
        return super().__call__(args, **kwargs)


APP_WINDOWS = [
    {"address": "0xc1", "class": "code", "title": "notes.md — Code", "pid": 30},
    {"address": "0xc2", "class": "code", "title": "todo.md — Code", "pid": 30},
    {"address": "0xd1", "class": "org.telegram.desktop", "title": "Telegram", "pid": 40},
]


@pytest.fixture
def process(monkeypatch):
    """Процесс приложения: жив ли он и в какой группе systemd живёт."""
    state = {"alive": True, "scope": None, "scopes": None, "killed": []}
    monkeypatch.setattr(session, "process_alive", lambda pid: state["alive"])
    monkeypatch.setattr(session, "quietline_scope", lambda pid: state["scopes"].get(pid) if state["scopes"] is not None else (state["scope"] if pid == 30 else None))
    monkeypatch.setattr(session, "is_shell_process", lambda pid: False)
    monkeypatch.setattr(session.os, "kill", lambda pid, sig: state["killed"].append((pid, sig)))
    return state


def test_quit_closes_only_the_active_process_windows(monkeypatch, clock, process):
    fake = FakeApps(APP_WINDOWS, APP_WINDOWS[0])
    monkeypatch.setattr(subprocess, "run", fake)
    process["alive"] = False
    assert session.quit_app() == {"closed": 2, "remaining": [], "background": False}
    closed = [args[2] for args in fake.commands if args[:2] == ["hyprctl", "dispatch"]]
    assert closed == ['hl.dsp.window.close({window = "address:0xc1"})', 'hl.dsp.window.close({window = "address:0xc2"})']


def test_save_dialog_keeps_the_process_safe(monkeypatch, clock, process):
    fake = FakeApps(APP_WINDOWS, APP_WINDOWS[0], stubborn={"0xc2"})
    monkeypatch.setattr(subprocess, "run", fake)
    process["scope"] = "app-quietline-code-1a2b3c.scope"
    result = session.quit_app(timeout=2)
    assert result == {"closed": 1, "remaining": [{"app": "code", "title": "todo.md — Code"}], "background": False}
    assert not any(args[0] == "systemctl" for args in fake.commands)
    assert process["killed"] == []


def test_quietline_process_without_windows_gets_sigterm(monkeypatch, clock, process):
    fake = FakeApps(APP_WINDOWS, APP_WINDOWS[0])
    monkeypatch.setattr(subprocess, "run", fake)
    process["scope"] = "app-quietline-code-1a2b3c.scope"
    assert session.quit_app()["background"] is False
    assert process["killed"] == [(30, session.signal.SIGTERM)]
    assert not any(args[0] == "systemctl" for args in fake.commands)


def test_window_of_another_process_in_the_scope_blocks_sigterm(monkeypatch, clock, process):
    editor = {"address": "0xf1", "class": "org.kde.kate", "title": "notes.txt — Kate", "pid": 31}
    fake = FakeApps([APP_WINDOWS[0], editor], APP_WINDOWS[0], stubborn={"0xf1"})
    monkeypatch.setattr(subprocess, "run", fake)
    process["scopes"] = {30: "app-quietline-ghostty-1a2b3c.scope", 31: "app-quietline-ghostty-1a2b3c.scope"}
    result = session.quit_app(timeout=2)
    assert result["remaining"] == [{"app": "org.kde.kate", "title": "notes.txt — Kate"}]
    assert process["killed"] == []
    closes = [args[2] for args in fake.commands if args[:2] == ["hyprctl", "dispatch"]]
    assert closes == ['hl.dsp.window.close({window = "address:0xc1"})']


def test_dialog_opened_after_closing_blocks_sigterm(monkeypatch, clock, process):
    fake = FakeApps(APP_WINDOWS[:1], APP_WINDOWS[0])
    original = fake.__call__

    def with_late_dialog(args, **kwargs):
        reply = original(args, **kwargs)
        if args[:2] == ["hyprctl", "dispatch"]:
            fake.clients.append({"address": "0xe9", "class": "code", "title": "Save changes?", "pid": 30})
            fake.stubborn.add("0xe9")
        return reply

    monkeypatch.setattr(subprocess, "run", with_late_dialog)
    process["scope"] = "app-quietline-code-1a2b3c.scope"
    result = session.quit_app(timeout=2)
    assert result["remaining"] == [{"app": "code", "title": "Save changes?"}]
    assert process["killed"] == []


def test_foreign_process_is_left_alone_and_reported(monkeypatch, clock, process, capsys):
    fake = FakeApps(APP_WINDOWS, APP_WINDOWS[2])
    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert main(["app", "quit", "--notify"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "closed": 1, "remaining": [], "background": True, "app": "org.telegram.desktop",
    }
    assert not any(args[0] == "systemctl" for args in fake.commands)
    assert process["killed"] == []
    notice = fake.commands[-1]
    assert notice[0] == "notify-send" and "продолжает работать в фоне" in notice[3]


def test_known_quit_command_replaces_window_closing(monkeypatch, clock, process):
    fake = FakeApps(APP_WINDOWS, APP_WINDOWS[2])
    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setitem(session.KNOWN_QUIT, "org.telegram.desktop", ["telegram-desktop", "-quit"])
    fake.stubborn = {"0xd1"}
    session.quit_app(timeout=1)
    assert ["telegram-desktop", "-quit"] in fake.commands
    assert not any(args[:2] == ["hyprctl", "dispatch"] for args in fake.commands)


def test_quit_by_pid_uses_that_process(monkeypatch, clock, process):
    fake = FakeApps(APP_WINDOWS, APP_WINDOWS[0])
    monkeypatch.setattr(subprocess, "run", fake)
    process["alive"] = False
    assert session.quit_app(pid=40)["closed"] == 1
    assert not any(args[:3] == ["hyprctl", "activewindow", "-j"] for args in fake.commands)


def test_quit_without_active_window_is_an_error(monkeypatch, process):
    monkeypatch.setattr(subprocess, "run", FakeApps([], {}))
    with pytest.raises(RuntimeError, match="no active window"):
        session.quit_app()


def test_kill_signals_only_the_process(monkeypatch, process):
    fake = FakeApps([], {})
    monkeypatch.setattr(subprocess, "run", fake)
    process["scope"] = "app-quietline-code-1a2b3c.scope"
    assert session.kill_app(30) == {"killed": 30}
    assert process["killed"] == [(30, session.signal.SIGKILL)]
    assert not any(args[0] == "systemctl" for args in fake.commands)
    for pid in (0, 1, -5):
        with pytest.raises(ValueError):
            session.kill_app(pid)


def test_shell_windows_are_not_quit_or_killed(monkeypatch, process):
    monkeypatch.setattr(subprocess, "run", FakeApps(APP_WINDOWS, APP_WINDOWS[0]))
    monkeypatch.setattr(session, "is_shell_process", lambda pid: pid == 30)
    with pytest.raises(RuntimeError, match="Quietline shell"):
        session.quit_app()
    with pytest.raises(RuntimeError, match="Quietline shell"):
        session.kill_app(30)
    assert process["killed"] == []


def test_quietline_scope_is_read_from_the_cgroup(tmp_path, monkeypatch):
    lines = {
        "ours": "0::/user.slice/user-1000.slice/user@1000.service/app.slice/app-quietline-code-1a2b3c.scope\n",
        "foreign": "0::/user.slice/user-1000.slice/user@1000.service/app.slice/app-org.kde.dolphin@x.service\n",
    }
    real = session.Path

    def fake_path(path):
        name = str(path)
        for key, text in lines.items():
            if name == f"/proc/{key}/cgroup":
                target = tmp_path / key
                target.write_text(text)
                return target
        return real(path)

    monkeypatch.setattr(session, "Path", fake_path)
    assert session.quietline_scope("ours") == "app-quietline-code-1a2b3c.scope"
    assert session.quietline_scope("foreign") is None
    assert session.quietline_scope("missing") is None


def test_copy_returns_while_wl_copy_keeps_serving_in_the_background(tmp_path, monkeypatch):
    fake = tmp_path / "wl-copy"
    fake.write_text("#!/bin/sh\ncat > \"$0.data\"\n(sleep 30) &\nexit 0\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:{session.os.environ['PATH']}")
    started = session.time.monotonic()
    session.copy_to_clipboard(b"PNG", "image/png")
    assert session.time.monotonic() - started < 5
    assert (tmp_path / "wl-copy.data").read_bytes() == b"PNG"


def test_copy_failure_reports_wl_copy_errors(tmp_path, monkeypatch):
    fake = tmp_path / "wl-copy"
    fake.write_text("#!/bin/sh\necho 'Failed to connect to a Wayland server' >&2\nexit 1\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:{session.os.environ['PATH']}")
    with pytest.raises(RuntimeError, match="Failed to connect to a Wayland server"):
        session.copy_to_clipboard(b"x")


def power_supplies(root, **supplies):
    """Поддельный `/sys/class/power_supply`: имя → поля (`type`, `online`, `scope`)."""
    for name, fields in supplies.items():
        (root / name).mkdir(parents=True)
        for key, value in fields.items():
            (root / name / key).write_text(f"{value}\n")
    return root


class FakeSystemctl:
    def __init__(self, code=0):
        self.code = code
        self.commands = []

    def __call__(self, args, **kwargs):
        self.commands.append(list(args))
        return subprocess.CompletedProcess(args, self.code, "", "Failed to suspend system")


def test_idle_suspend_on_battery_suspends(tmp_path, monkeypatch):
    systemctl = FakeSystemctl()
    monkeypatch.setattr(subprocess, "run", systemctl)
    root = power_supplies(tmp_path, BAT0={"type": "Battery"}, AC={"type": "Mains", "online": 0})
    assert session.idle_suspend(root) == {"suspended": True}
    assert systemctl.commands == [["systemctl", "suspend"]]


def test_idle_suspend_on_mains_stays_awake(tmp_path, monkeypatch):
    systemctl = FakeSystemctl()
    monkeypatch.setattr(subprocess, "run", systemctl)
    root = power_supplies(tmp_path, BAT0={"type": "Battery"}, AC={"type": "Mains", "online": 1})
    assert session.idle_suspend(root) == {"suspended": False, "reason": "ac"}
    assert systemctl.commands == []


def test_idle_suspend_on_usb_charger_stays_awake(tmp_path, monkeypatch):
    systemctl = FakeSystemctl()
    monkeypatch.setattr(subprocess, "run", systemctl)
    root = power_supplies(tmp_path, **{"BAT0": {"type": "Battery"},
                                       "ucsi-source-psy-USBC000:001": {"type": "USB", "online": 1}})
    assert session.idle_suspend(root) == {"suspended": False, "reason": "ac"}
    assert systemctl.commands == []


def test_idle_suspend_ignores_peripheral_batteries(tmp_path, monkeypatch):
    systemctl = FakeSystemctl()
    monkeypatch.setattr(subprocess, "run", systemctl)
    root = power_supplies(tmp_path, hidpp_battery_0={"type": "Battery", "scope": "Device"})
    assert session.idle_suspend(root) == {"suspended": False, "reason": "no-battery"}
    assert systemctl.commands == []


def test_cli_idle_suspend_reports_systemctl_failure(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(subprocess, "run", FakeSystemctl(code=1))
    root = power_supplies(tmp_path, BAT0={"type": "Battery"})
    monkeypatch.setattr(session, "POWER_SUPPLIES", root)
    assert main(["idle", "suspend"]) == 1
    output = capsys.readouterr().out
    assert output.count("\n") == 1
    assert "systemctl suspend failed" in json.loads(output)["error"]
