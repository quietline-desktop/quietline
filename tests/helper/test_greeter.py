"""Тесты данных экрана входа `quietline-shell greeter`: пользователи, сеансы, последний выбор."""

import json

import pytest

from quietline_shell import session
from quietline_shell.__main__ import main

PASSWD = """root:x:0:0::/root:/usr/bin/bash
greeter:x:963:963:greetd greeter user:/:/bin/bash
nobody:x:65534:65534:Kernel Overflow User:/:/usr/bin/nologin
kiryl:x:1000:1000:Kiryl Novik,,,:/home/kiryl:/usr/bin/fish
guest:x:1001:1001::/home/guest:/bin/bash
service:x:1002:1002::/srv:/usr/bin/nologin
locked:x:1003:1003::/home/locked:/bin/false
"""


def desktop(folder, name, body):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.desktop").write_text("[Desktop Entry]\n" + body)


@pytest.fixture
def system(tmp_path):
    (tmp_path / "passwd").write_text(PASSWD)
    (tmp_path / "login.defs").write_text("UID_MIN\t\t\t 1000\nUID_MAX\t\t\t60000\n")
    sessions = tmp_path / "sessions"
    desktop(sessions, "hyprland", "Name=Hyprland\nExec=/usr/bin/start-hyprland\nDesktopNames=Hyprland\n")
    desktop(sessions, "hyprland-uwsm", "Name=Hyprland (uwsm-managed)\nName[ru]=Hyprland (через uwsm)\n"
            "Exec=uwsm start -e -D Hyprland hyprland.desktop\nDesktopNames=Hyprland\n")
    desktop(sessions, "hidden", "Name=Hidden\nExec=hidden\nHidden=true\n")
    desktop(sessions, "missing", "Name=Missing\nExec=missing\nTryExec=/nonexistent/binary\n")
    return tmp_path


def data(system, state=None, language="en"):
    return session.greeter_data(state or system / "state/greeter.json", passwd=system / "passwd",
                                login_defs=system / "login.defs", sessions=system / "sessions", language=language)


def test_users_are_login_users_in_uid_order(system):
    assert data(system)["users"] == [{"name": "kiryl", "display": "Kiryl Novik"},
                                     {"name": "guest", "display": "Guest"}]


def test_uid_range_follows_login_defs(system):
    (system / "login.defs").write_text("UID_MIN 1001\nUID_MAX 1001\n")
    assert [user["name"] for user in data(system)["users"]] == ["guest"]


def test_sessions_skip_hidden_and_missing_commands(system):
    sessions = data(system)["sessions"]
    assert [item["id"] for item in sessions] == ["hyprland", "hyprland-uwsm"]
    assert sessions[0] == {"id": "hyprland", "name": "Hyprland", "command": ["/usr/bin/start-hyprland"],
                           "desktopNames": ["Hyprland"]}
    assert sessions[1]["command"] == ["uwsm", "start", "-e", "-D", "Hyprland", "hyprland.desktop"]


def test_session_names_follow_language(system):
    names = [item["name"] for item in data(system, language="ru")["sessions"]]
    assert "Hyprland (через uwsm)" in names


def test_exec_drops_field_codes():
    assert session.session_command('run --file %f --url=%u "two words" 100%%') == [
        "run", "--file", "--url=", "two words", "100%"]


def test_defaults_without_state(system):
    assert data(system)["last"] == {"user": "kiryl", "session": "hyprland"}


def test_remembered_choice_is_used_while_it_exists(system):
    state = system / "state/greeter.json"
    assert session.remember_greeter(state, {"user": "guest", "session": "hyprland-uwsm"}) == {
        "user": "guest", "session": "hyprland-uwsm"}
    assert data(system, state)["last"] == {"user": "guest", "session": "hyprland-uwsm"}
    (system / "sessions/hyprland-uwsm.desktop").unlink()
    assert data(system, state)["last"] == {"user": "guest", "session": "hyprland"}


@pytest.mark.parametrize("content", ["not json", "[1, 2]", '{"user": "root", "session": "nope"}'])
def test_broken_or_stale_state_falls_back(system, content):
    state = system / "state/greeter.json"
    state.parent.mkdir(parents=True)
    state.write_text(content)
    assert data(system, state)["last"] == {"user": "kiryl", "session": "hyprland"}


@pytest.mark.parametrize("change", [
    {"user": "kiryl"},
    {"user": "Kiryl Novik", "session": "hyprland"},
    {"user": "kiryl", "session": "../evil"},
    {"user": "kiryl", "session": "hyprland", "extra": 1},
    ["kiryl", "hyprland"],
])
def test_remember_rejects_bad_input(system, change):
    state = system / "state/greeter.json"
    with pytest.raises(ValueError):
        session.remember_greeter(state, change)
    assert not state.exists()


def test_cli_remember_and_error(tmp_path, capsys):
    state = tmp_path / "greeter.json"
    assert main(["greeter", "--path", str(state), "--remember", '{"user": "kiryl", "session": "hyprland"}']) == 0
    assert json.loads(capsys.readouterr().out) == {"user": "kiryl", "session": "hyprland"}
    assert main(["greeter", "--path", str(state), "--remember", '{"user": "../x", "session": "a"}']) == 1
    assert "error" in json.loads(capsys.readouterr().out)
