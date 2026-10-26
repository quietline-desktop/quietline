"""Тесты адаптера Hyprland: поддельный запуск hyprctl с записанными JSON-ответами."""

import asyncio
import json
import os
import subprocess
import tempfile
from collections.abc import Sequence

import pytest

from quietline_engine import hyprland
from quietline_engine.hyprland import Hyprland, HyprlandError, parse_event
from quietline_engine.types import (
    FocusMonitor,
    FocusWindow,
    FocusWorkspace,
    MoveWindow,
    MoveWindowToWorkspace,
    MoveWorkspaceToMonitor,
    ResizeColumn,
    ResizeWindow,
    SetFloating,
    SwapColumn,
)

MONITORS = [
    {
        "id": 0,
        "name": "DP-1",
        "make": "Dell Inc.",
        "model": "U2723QE",
        "serial": "ABC123",
        "x": 0,
        "y": 0,
        "width": 2560,
        "height": 1440,
        "scale": 1.0,
        "reserved": [10, 36, 20, 0],
        "activeWorkspace": {"id": 1, "name": "1"},
        "focused": True,
    },
    {
        "id": 1,
        "name": "HDMI-A-1",
        "make": "LG",
        "model": "27UK850",
        "serial": "",
        "x": 2560,
        "y": 0,
        "width": 1920,
        "height": 1080,
        "scale": 1.0,
        "reserved": [0, 36, 0, 0],
        "activeWorkspace": {"id": 1001, "name": "1001"},
        "focused": False,
    },
]

WORKSPACES = [
    {"id": 1, "name": "1", "monitor": "DP-1", "monitorID": 0, "windows": 3, "tiledLayout": "scrolling"},
    {"id": 1001, "name": "1001", "monitor": "HDMI-A-1", "monitorID": 1, "windows": 1, "tiledLayout": "scrolling"},
]


def client(address, workspace, monitor, at, size, floating=False, title="t"):
    """Запись `hyprctl -j clients` с полями из карты команд."""
    return {
        "address": address,
        "workspace": {"id": workspace, "name": str(workspace)},
        "monitor": monitor,
        "at": list(at),
        "size": list(size),
        "floating": floating,
        "fullscreen": 0,
        "class": "kitty",
        "title": title,
        "pid": 4242,
        "mapped": True,
        "hidden": False,
    }


CLIENTS = [
    # Вторая колонка стоит правее первой, но стоит в списке раньше.
    client("0xb2", 1, 0, (1290, 36), (1240, 700)),
    client("0xa1", 1, 0, (10, 36), (1240, 1404)),
    client("0xb3", 1, 0, (1290, 736), (1240, 704)),
    client("0xc4", 1001, 1, (2560, 36), (1920, 1044)),
    client("0xd5", 1, 0, (300, 300), (400, 300), floating=True),
]


class FakeRunner:
    """Подменяет запуск hyprctl: фиксирует вызовы, отвечает по заготовке."""

    def __init__(self, replies=None):
        self.calls: list[list[str]] = []
        self.replies = replies or {
            ("hyprctl", "-j", "monitors"): json.dumps(MONITORS),
            ("hyprctl", "-j", "workspaces"): json.dumps(WORKSPACES),
            ("hyprctl", "-j", "clients"): json.dumps(CLIENTS),
            ("hyprctl", "-j", "activewindow"): json.dumps(CLIENTS[1]),
            ("hyprctl", "-j", "cursorpos"): json.dumps({"x": 2700, "y": 500}),
        }

    def __call__(self, argv: Sequence[str]) -> str:
        self.calls.append(list(argv))
        reply = self.replies[tuple(argv)] if tuple(argv) in self.replies else "ok"
        if isinstance(reply, Exception):
            raise reply
        return reply


def test_snapshot_parses_two_monitors_and_clients():
    runner = FakeRunner()
    snap = Hyprland(runner=runner).snapshot()

    assert [m.name for m in snap.monitors] == ["DP-1", "HDMI-A-1"]
    first, second = snap.monitors
    assert (first.id, first.make, first.model, first.serial) == (0, "Dell Inc.", "U2723QE", "ABC123")
    assert (first.width, first.height, first.scale) == (2560, 1440, 1.0)
    assert first.reserved == (10, 36, 20, 0)
    assert first.active_workspace_id == 1 and first.focused is True
    assert second.serial == "" and second.x == 2560 and second.focused is False

    assert [(w.id, w.monitor, w.monitor_id) for w in snap.workspaces] == [
        (1, "DP-1", 0),
        (1001, "HDMI-A-1", 1),
    ]
    assert snap.workspaces[0].tiled_layout == "scrolling"

    assert len(snap.windows) == 5
    win = snap.windows[1]
    assert win.address == "0xa1"
    assert (win.workspace_id, win.monitor_id) == (1, 0)
    assert win.at == (10, 36) and win.size == (1240, 1404)
    assert win.floating is False and win.class_name == "kitty" and win.pid == 4242
    assert snap.windows[4].floating is True

    assert snap.active_window is not None and snap.active_window.address == "0xa1"
    assert snap.cursor_position == (2700, 500)

    assert runner.calls == [
        ["hyprctl", "-j", "monitors"],
        ["hyprctl", "-j", "workspaces"],
        ["hyprctl", "-j", "clients"],
        ["hyprctl", "-j", "activewindow"],
        ["hyprctl", "-j", "cursorpos"],
    ]


def test_snapshot_without_active_window_and_derived_columns():
    runner = FakeRunner()
    runner.replies[("hyprctl", "-j", "activewindow")] = "{}"
    snap = Hyprland(runner=runner).snapshot()
    assert snap.active_window is None

    # Рабочая область первого монитора: 2560 - 10 - 20 = 2530.
    columns = snap.columns(1)
    assert [c.addresses for c in columns] == [("0xa1",), ("0xb2", "0xb3")]
    assert columns[0].width == pytest.approx(1240 / 2530)
    assert columns[1].width == pytest.approx(1240 / 2530)

    # Плавающие окна в колонки не попадают.
    assert [c.addresses for c in snap.columns(1001)] == [("0xc4",)]
    assert snap.columns(1001)[0].width == pytest.approx(1.0)
    with pytest.raises(ValueError):
        snap.columns(999)


def test_columns_use_logical_work_area_of_scaled_monitor():
    runner = FakeRunner()
    scaled = [dict(MONITORS[0], scale=1.25), MONITORS[1]]
    runner.replies[("hyprctl", "-j", "monitors")] = json.dumps(scaled)
    snap = Hyprland(runner=runner).snapshot()

    # 2560 / 1.25 = 2048 логических пикселей, минус отступы 10 и 20.
    assert snap.monitors[0].work_area_width == pytest.approx(2018)
    assert [c.width for c in snap.columns(1)] == pytest.approx([1240 / 2018, 1240 / 2018])


@pytest.mark.parametrize(
    "patch",
    [{"scale": 0.0}, {"scale": -1.0}, {"reserved": [1280, 0, 1280, 0]}, {"reserved": [2000, 0, 600, 0]}],
)
def test_columns_reject_empty_work_area(patch):
    runner = FakeRunner()
    runner.replies[("hyprctl", "-j", "monitors")] = json.dumps([dict(MONITORS[0], **patch), MONITORS[1]])
    snap = Hyprland(runner=runner).snapshot()
    with pytest.raises(ValueError):
        snap.columns(1)


def test_eval_escapes_only_validated_ids():
    runner = FakeRunner()
    hypr = Hyprland(runner=runner)

    hypr.apply(
        [
            SetFloating("0xa1", True),
            SetFloating("0xb2", False),
            MoveWindow("0xa1", 100, 200),
            ResizeWindow("0xa1", 800, 600),
            FocusWindow("0xa1"),
            FocusWorkspace(1001),
            FocusMonitor("HDMI-A-1"),
            MoveWindowToWorkspace("0xa1", 1002, follow=False),
            MoveWorkspaceToMonitor(1002, "DP-1"),
            ResizeColumn(0.5),
            SwapColumn("l"),
            SwapColumn("r"),
        ]
    )

    (call,) = runner.calls
    assert call[:2] == ["hyprctl", "eval"] and len(call) == 3
    assert call[2].split("\n") == [
        'hl.dispatch(hl.dsp.window.float({ action = "enable", window = "address:0xa1" }))',
        'hl.dispatch(hl.dsp.window.float({ action = "disable", window = "address:0xb2" }))',
        'hl.dispatch(hl.dsp.window.move({ x = 100, y = 200, window = "address:0xa1" }))',
        'hl.dispatch(hl.dsp.window.resize({ x = 800, y = 600, window = "address:0xa1" }))',
        'hl.dispatch(hl.dsp.focus({ window = "address:0xa1" }))',
        'hl.dispatch(hl.dsp.focus({ workspace = "1001", on_current_monitor = true }))',
        'hl.dispatch(hl.dsp.focus({ monitor = "HDMI-A-1" }))',
        'hl.dispatch(hl.dsp.window.move({ workspace = "1002", window = "address:0xa1", follow = false }))',
        'hl.dispatch(hl.dsp.workspace.move({ workspace = "1002", monitor = "DP-1" }))',
        'hl.dispatch(hl.dsp.layout("colresize 0.5"))',
        'hl.dispatch(hl.dsp.layout("swapcol l"))',
        'hl.dispatch(hl.dsp.layout("swapcol r"))',
    ]


@pytest.mark.parametrize(
    "action",
    [
        SetFloating('0xa1" }))\nos.execute("x', True),
        SetFloating("0xA1", True),
        SetFloating("a1", True),
        SetFloating("0x", True),
        FocusWindow("0xa1 "),
        FocusWindow("0xa1\n"),
        MoveWindow("0xa1", "1", 2),
        MoveWindow("0xa1", 1, 2.5),
        ResizeWindow("0xa1", True, 5),
        FocusWorkspace("1; os.exit()"),
        FocusWorkspace(1.0),
        FocusWorkspace(True),
        MoveWindowToWorkspace("0xa1", "2", follow=True),
        MoveWindowToWorkspace("0xa1", 2, follow="yes"),
        FocusMonitor('DP-1" })'),
        FocusMonitor("DP-1\n"),
        FocusMonitor(""),
        FocusMonitor("eDP 1"),
        MoveWorkspaceToMonitor(1, "DP_1"),
        ResizeColumn(0.0),
        ResizeColumn(float("nan")),
        ResizeColumn(1.5),
        SwapColumn("u"),
    ],
)
def test_eval_rejects_unsafe_values_before_any_subprocess(action):
    runner = FakeRunner()
    # Безопасное действие стоит первым: вызова не должно быть вообще.
    with pytest.raises(HyprlandError):
        Hyprland(runner=runner).apply([FocusWindow("0xa1"), action])
    assert runner.calls == []


def test_apply_without_actions_does_not_call_hyprctl():
    runner = FakeRunner()
    Hyprland(runner=runner).apply([])
    assert runner.calls == []


def test_hyprctl_failure_raises_without_success_state(monkeypatch):
    # Ненулевой код возврата настоящего запуска.
    seen = {}

    def fake_run(argv, **kwargs):
        seen["argv"], seen["kwargs"] = argv, kwargs
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="no socket")

    monkeypatch.setattr(hyprland.subprocess, "run", fake_run)
    hypr = Hyprland()
    with pytest.raises(HyprlandError, match="exit code 1"):
        hypr.snapshot()
    with pytest.raises(HyprlandError, match="exit code 1"):
        hypr.apply([FocusWindow("0xa1")])
    assert isinstance(seen["argv"], list) and seen["argv"][0] == "hyprctl"
    assert seen["kwargs"]["timeout"] > 0
    assert not seen["kwargs"].get("shell", False)

    # Таймаут и отсутствие hyprctl.
    def timeout_run(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, kwargs["timeout"])

    monkeypatch.setattr(hyprland.subprocess, "run", timeout_run)
    with pytest.raises(HyprlandError, match="timed out"):
        hypr.snapshot()

    def missing_run(argv, **kwargs):
        raise FileNotFoundError(argv[0])

    monkeypatch.setattr(hyprland.subprocess, "run", missing_run)
    with pytest.raises(HyprlandError, match="not found"):
        hypr.snapshot()


@pytest.mark.parametrize("reply", ["error: no such window", "", "okay", "ok ok"])
def test_eval_reply_other_than_ok_is_an_error(reply):
    runner = FakeRunner()
    runner.replies[("hyprctl", "eval", 'hl.dispatch(hl.dsp.focus({ window = "address:0xa1" }))')] = reply
    with pytest.raises(HyprlandError, match="hyprctl eval"):
        Hyprland(runner=runner).apply([FocusWindow("0xa1")])


def test_malformed_snapshot_raises():
    runner = FakeRunner()
    runner.replies[("hyprctl", "-j", "monitors")] = "not json"
    with pytest.raises(HyprlandError):
        Hyprland(runner=runner).snapshot()

    runner = FakeRunner()
    runner.replies[("hyprctl", "-j", "clients")] = json.dumps([{"address": "0x1"}])
    with pytest.raises(HyprlandError):
        Hyprland(runner=runner).snapshot()


def test_parse_event_splits_on_first_separator():
    event = parse_event("openwindow>>0xa1,1,kitty,a>>b")
    assert (event.name, event.data) == ("openwindow", "0xa1,1,kitty,a>>b")
    assert parse_event("submap>>").data == ""
    assert parse_event("noseparator").name == "noseparator"


def test_events_reads_lines_from_socket2():
    async def scenario():
        with tempfile.TemporaryDirectory() as runtime:
            signature = "sig"
            sock_dir = os.path.join(runtime, "hypr", signature)
            os.makedirs(sock_dir)

            async def serve(reader, writer):
                writer.write(b"workspace>>2\nmonitoradded>>DP-1\n")
                await writer.drain()
                writer.close()

            server = await asyncio.start_unix_server(serve, os.path.join(sock_dir, ".socket2.sock"))
            env = {"XDG_RUNTIME_DIR": runtime, "HYPRLAND_INSTANCE_SIGNATURE": signature}
            async with server:
                return [(e.name, e.data) async for e in Hyprland(env=env).events()]

    assert asyncio.run(scenario()) == [("workspace", "2"), ("monitoradded", "DP-1")]


@pytest.mark.parametrize(
    ("env", "missing"),
    [
        ({}, "XDG_RUNTIME_DIR"),
        ({"XDG_RUNTIME_DIR": "/run/user/1000"}, "HYPRLAND_INSTANCE_SIGNATURE"),
    ],
)
def test_events_requires_session_environment(env, missing):
    async def scenario():
        async for _ in Hyprland(env=env).events():
            pass

    with pytest.raises(HyprlandError, match=missing):
        asyncio.run(scenario())
