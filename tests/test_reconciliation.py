"""Тесты сверки по событиям: новые и перенесённые окна, пустые пространства, мониторы и команды."""

import asyncio

import pytest
from fakes import FakeAdapter, monitor, snapshot, window, workspace

from quietline_engine.controller import PublicState, WindowController
from quietline_engine.types import (
    FocusMonitor,
    FocusWorkspace,
    HyprEvent,
    MoveWindow,
    MoveWindowToWorkspace,
    MoveWorkspaceToMonitor,
    ResizeWindow,
    SetFloating,
)
from quietline_engine.workspaces import WorkspaceRegistry

KEY = "Dell Inc.|U2723QE|SN1"
SECOND_KEY = "Dell Inc.|U2723QE|SN2"
EVENT = HyprEvent("openwindow", "0x1,1,kitty,kitty")


@pytest.fixture
def state_path(tmp_path):
    return tmp_path / "quietline" / "state.json"


@pytest.fixture
def registry(state_path):
    return WorkspaceRegistry(state_path, "sig")


def run(coroutine):
    return asyncio.run(coroutine)


def second(*, x=2560, width=2560, height=1440, active=2):
    """Второй монитор справа от первого."""
    return monitor(1, "HDMI-A-1", x=x, width=width, height=height, active=active, focused=False, serial="SN2")


def workspaces_json(state):
    return {(w["monitor_key"], w["number"]): w for w in state.to_json()["workspaces"]}


def test_new_window_floats_only_on_windows_workspace(registry):
    mon = monitor(reserved=(0, 40, 0, 0))
    base = snapshot([mon], [workspace(1, mon)], [])
    one = registry.resolve(1, KEY, base)
    two = registry.resolve(2, KEY, base)
    registry.update(one, extra={"managed": ["0xa"], "dialogs": []})
    registry.update(two, mode="tiles", extra={"managed": ["0xt"], "dialogs": []})
    opened = snapshot(
        [mon],
        [workspace(1, mon), workspace(two.workspace_id, mon)],
        [
            window("0xa", 1, at=(100, 140), floating=True),
            window("0xn", 1, at=(0, 40), size=(2560, 1400)),
            window("0xd", 1, at=(900, 500), size=(400, 300), floating=True),
            window("0xt", two.workspace_id, at=(0, 40), size=(1280, 1400)),
            window("0xu", two.workspace_id, at=(1280, 40), size=(1280, 1400)),
        ],
    )
    adapter = FakeAdapter([opened])
    controller = WindowController(adapter, registry)

    assert run(controller.reconcile(EVENT)) is None

    # Новое тайловое окно в «Окнах» становится плавающим по центру рабочей области.
    assert adapter.applied == [[SetFloating("0xn", True), MoveWindow("0xn", 512, 320), ResizeWindow("0xn", 1536, 840)]]
    assert registry.get(KEY, 1).extra["managed"] == ["0xa", "0xn"]
    assert registry.get(KEY, 1).extra["dialogs"] == ["0xd"]
    # В «Тайлах» новое окно остаётся в раскладке и становится управляемым.
    assert registry.get(KEY, 2).extra["managed"] == ["0xt", "0xu"]

    # Следующее событие с уже плавающим окном ничего не меняет.
    floated = snapshot(
        [mon],
        opened.workspaces,
        [
            window("0xn", 1, at=(512, 320), size=(1536, 840), floating=True) if w.address == "0xn" else w
            for w in opened.windows
        ],
    )
    adapter.snapshots = [floated]
    assert run(controller.reconcile(EVENT)) is None
    assert len(adapter.applied) == 1


def test_moved_window_obeys_destination_mode(registry):
    mon = monitor()
    base = snapshot([mon], [workspace(1, mon)], [])
    one = registry.resolve(1, KEY, base)
    two = registry.resolve(2, KEY, base)
    registry.update(one, extra={"managed": ["0xa"], "dialogs": []})
    registry.update(
        two,
        mode="tiles",
        extra={"managed": ["0xb"], "dialogs": [], "geometry": {"0xb": {"at": [300, 200], "size": [1000, 700]}}},
    )
    # 0xa перенесено из «Окон» в «Тайлы», 0xb — из «Тайлов» в «Окна».
    moved = snapshot(
        [mon],
        [workspace(1, mon), workspace(two.workspace_id, mon)],
        [
            window("0xa", two.workspace_id, at=(100, 140), size=(800, 600), floating=True),
            window("0xb", 1, at=(0, 0), size=(2560, 1440)),
        ],
    )
    adapter = FakeAdapter([moved])
    controller = WindowController(adapter, registry)

    run(controller.reconcile(HyprEvent("movewindow", "0xa,1001")))

    assert adapter.applied == [
        [SetFloating("0xb", True), MoveWindow("0xb", 300, 200), ResizeWindow("0xb", 1000, 700)],
        [SetFloating("0xa", False)],
    ]
    assert registry.get(KEY, 1).extra["managed"] == ["0xb"]
    assert registry.get(KEY, 2).extra["managed"] == ["0xa"]
    # Геометрия окна, ушедшего в «Тайлы», восстановится при возврате в «Окна».
    assert registry.get(KEY, 2).extra["geometry"] == {"0xa": {"at": [100, 140], "size": [800, 600]}}


def test_move_sends_active_window_and_applies_destination_mode(registry):
    mon = monitor()
    base = snapshot([mon], [workspace(1, mon)], [])
    one = registry.resolve(1, KEY, base)
    registry.update(one, extra={"managed": ["0xa"], "dialogs": []})
    two = registry.resolve(2, KEY, base)
    registry.update(two, mode="tiles")
    before = snapshot(
        [mon],
        [workspace(1, mon), workspace(two.workspace_id, mon)],
        [window("0xa", 1, at=(100, 140), floating=True)],
        active="0xa",
    )
    after = snapshot(
        [monitor(active=two.workspace_id)],
        [workspace(two.workspace_id, mon)],
        [window("0xa", two.workspace_id, at=(100, 140), floating=True)],
        active="0xa",
    )
    adapter = FakeAdapter([before, after])
    controller = WindowController(adapter, registry)

    state = run(controller.move(2))

    assert state.error is None
    assert adapter.applied == [
        [MoveWindowToWorkspace("0xa", two.workspace_id, follow=True)],
        [SetFloating("0xa", False)],
    ]
    assert registry.get(KEY, 2).extra["managed"] == ["0xa"]
    # Пространство 1 стало пустым и неактивным — запись удалена.
    assert registry.get(KEY, 1) is None
    assert state.to_json()["monitors"][0]["active_number"] == 2


def test_move_without_active_window_is_an_error(registry):
    mon = monitor()
    adapter = FakeAdapter([snapshot([mon], [workspace(1, mon)], [])])
    controller = WindowController(adapter, registry)

    state = run(controller.move(2))

    assert state.error == "no active window to move"
    assert adapter.applied == []
    assert registry.get(KEY, 2) is None


@pytest.mark.parametrize("command", ["switch", "move"])
@pytest.mark.parametrize("number", [0, 11, "1", True])
def test_invalid_number_is_rejected_without_hyprland(registry, command, number):
    adapter = FakeAdapter([snapshot([monitor()], [], [])])
    controller = WindowController(adapter, registry)

    state = run(getattr(controller, command)(number))

    assert state.error is not None and "from 1 to 10" in state.error
    assert adapter.calls == []
    assert state.revision == 0


def test_empty_inactive_workspace_is_removed(registry):
    mon = monitor()
    base = snapshot([mon], [workspace(1, mon)], [])
    registry.resolve(1, KEY, base)
    two = registry.resolve(2, KEY, base)
    registry.update(two, mode="tiles", extra={"managed": ["0xt"], "geometry": {"0xt": {"at": [0, 0], "size": [9, 9]}}})
    shown = snapshot([mon], [workspace(1, mon), workspace(two.workspace_id, mon)], [])
    closed = snapshot([mon], [workspace(1, mon)], [])
    adapter = FakeAdapter([shown])
    controller = WindowController(adapter, registry)
    assert run(controller.reconcile(EVENT)) is None

    adapter.snapshots = [closed]
    state = run(controller.reconcile(HyprEvent("destroyworkspace", str(two.workspace_id))))

    assert isinstance(state, PublicState)
    assert state.revision == 1 and state.error is None
    assert registry.get(KEY, 2) is None
    assert (KEY, 2) not in workspaces_json(state)
    assert adapter.applied == []

    # Пространство создаётся заново в режиме «Окна» без сохранённых снимков.
    reopened = snapshot([monitor(active=1001)], [workspace(1, mon), workspace(1001, mon)], [])
    adapter.snapshots = [closed, reopened]
    state = run(controller.switch(2))

    assert state.error is None and state.revision == 2
    assert adapter.applied == [[FocusMonitor("DP-1"), FocusWorkspace(1001)]]
    ref = registry.get(KEY, 2)
    assert ref.mode == "windows" and ref.extra == {}
    assert state.to_json()["monitors"][0]["active_number"] == 2


def test_disconnected_workspace_is_accessible_and_returns(registry):
    left, right = monitor(), second()
    windows = [
        window("0xa", 1, at=(100, 100), floating=True),
        window("0xb", 2, monitor_id=1, at=(2700, 100), floating=True),
        window("0xc", 1001, monitor_id=1, at=(2560, 0), size=(2560, 1440)),
    ]
    bare = snapshot([left, right], [workspace(1, left), workspace(2, right)], [])
    registry.resolve(1, SECOND_KEY, bare)
    tiles = registry.resolve(2, SECOND_KEY, bare)
    assert tiles.workspace_id == 1001
    registry.update(registry.get(SECOND_KEY, 1), extra={"managed": ["0xb"], "dialogs": []})
    registry.update(tiles, mode="tiles")
    connected = snapshot([left, right], [workspace(1, left), workspace(2, right), workspace(1001, right)], windows)
    adapter = FakeAdapter([connected])
    controller = WindowController(adapter, registry)
    run(controller.reconcile(EVENT))
    adapter.applied.clear()

    # Правый монитор отключён: Hyprland показывает его пространства на левом.
    alone = snapshot(
        [left],
        [workspace(1, left), workspace(2, left), workspace(1001, left)],
        [
            windows[0],
            window("0xb", 2, at=(2700, 100), floating=True),
            window("0xc", 1001, at=(0, 0), size=(2560, 1440)),
        ],
    )
    adapter.snapshots = [alone]
    state = run(controller.reconcile(HyprEvent("monitorremoved", "HDMI-A-1")))

    assert state.error is None and state.revision >= 1
    refs = workspaces_json(state)
    assert refs[(SECOND_KEY, 1)]["display_monitor_key"] == KEY
    assert refs[(SECOND_KEY, 1)]["workspace_id"] == 2
    assert refs[(SECOND_KEY, 2)]["display_monitor_key"] == KEY
    assert refs[(SECOND_KEY, 2)]["workspace_id"] == 1001
    assert [m["key"] for m in state.to_json()["monitors"]] == [KEY]
    # Плавающее окно перенесено в рабочую область оставшегося монитора.
    assert adapter.applied == [[MoveWindow("0xb", 140, 100), ResizeWindow("0xb", 800, 600)]]
    adapter.applied.clear()

    # Панель открывает пространство отключённого монитора на мониторе фокуса.
    opened = snapshot([monitor(active=1001)], alone.workspaces, alone.windows)
    adapter.snapshots = [alone, opened]
    state = run(controller.switch(2, SECOND_KEY))
    assert state.error is None
    assert adapter.applied == [[FocusWorkspace(1001)]]
    assert state.to_json()["monitors"][0]["active_workspace_id"] == 1001
    adapter.applied.clear()

    # Цифры без монитора адресуют собственные пространства монитора фокуса.
    own = snapshot([monitor(active=1002)], (*alone.workspaces, workspace(1002, left)), alone.windows)
    adapter.snapshots = [opened, own]
    state = run(controller.switch(2))
    assert state.error is None
    assert adapter.applied == [[FocusMonitor("DP-1"), FocusWorkspace(1002)]]
    assert registry.get(KEY, 2).workspace_id == 1002
    assert registry.get(SECOND_KEY, 2).workspace_id == 1001
    adapter.applied.clear()

    # Монитор вернулся: Hyprland дал ему новое пространство, движок возвращает его собственные.
    returned = snapshot([monitor(active=1002), second(active=3)], (*own.workspaces, workspace(3, right)), own.windows)
    settled = snapshot(
        [monitor(active=1002), second(active=2)],
        [workspace(1, left), workspace(1002, left), workspace(2, right), workspace(1001, right)],
        [
            windows[0],
            window("0xb", 2, monitor_id=1, at=(140, 100), floating=True),
            window("0xc", 1001, monitor_id=1, at=(2560, 0), size=(2560, 1440)),
        ],
    )
    adapter.snapshots = [returned, settled]
    state = run(controller.reconcile(HyprEvent("monitoradded", "HDMI-A-1")))

    assert state.error is None
    assert adapter.applied == [
        [MoveWorkspaceToMonitor(2, "HDMI-A-1"), MoveWorkspaceToMonitor(1001, "HDMI-A-1")],
        [MoveWindow("0xb", 2700, 100), ResizeWindow("0xb", 800, 600)],
    ]
    refs = workspaces_json(state)
    assert set(refs) == {(KEY, 1), (KEY, 2), (SECOND_KEY, 1), (SECOND_KEY, 2)}
    assert refs[(SECOND_KEY, 1)] == {
        "monitor_key": SECOND_KEY,
        "display_monitor_key": SECOND_KEY,
        "number": 1,
        "workspace_id": 2,
        "mode": "windows",
    }
    assert refs[(SECOND_KEY, 2)]["display_monitor_key"] == SECOND_KEY
    assert refs[(SECOND_KEY, 2)]["mode"] == "tiles"
    assert refs[(KEY, 2)]["workspace_id"] == 1002


def test_reconnected_smaller_monitor_clamps_geometry(registry):
    left, right = monitor(), second()
    connected = snapshot(
        [left, right],
        [workspace(1, left), workspace(2, right), workspace(1001, right)],
        [
            window("0xw", 2, monitor_id=1, at=(4000, 900), size=(1000, 500), floating=True),
            window("0xt", 1001, monitor_id=1, at=(2560, 0), size=(2560, 1440)),
        ],
    )
    registry.resolve(1, SECOND_KEY, snapshot([left, right], [workspace(1, left), workspace(2, right)], []))
    tiles = registry.resolve(2, SECOND_KEY, snapshot([left, right], [workspace(1, left), workspace(2, right)], []))
    registry.update(registry.get(SECOND_KEY, 1), extra={"managed": ["0xw"], "dialogs": []})
    registry.update(
        tiles,
        mode="tiles",
        extra={"managed": ["0xt"], "dialogs": [], "geometry": {"0xt": {"at": [4200, 800], "size": [1200, 600]}}},
    )
    adapter = FakeAdapter([connected])
    controller = WindowController(adapter, registry)
    run(controller.reconcile(EVENT))
    assert adapter.applied == []

    alone = snapshot(
        [left],
        [workspace(1, left), workspace(2, left), workspace(1001, left)],
        [
            window("0xw", 2, at=(4000, 900), size=(1000, 500), floating=True),
            window("0xt", 1001, at=(0, 0), size=(2560, 1440)),
        ],
    )
    adapter.snapshots = [alone]
    run(controller.reconcile(HyprEvent("monitorremoved", "HDMI-A-1")))
    assert adapter.applied == [[MoveWindow("0xw", 1440, 900), ResizeWindow("0xw", 1000, 500)]]
    assert registry.get(SECOND_KEY, 2).extra["geometry"] == {"0xt": {"at": [1360, 800], "size": [1200, 600]}}
    adapter.applied.clear()

    # Тот же монитор вернулся с меньшим разрешением.
    small = second(width=1920, height=1080, active=4)
    returned = snapshot(
        [left, small],
        [*alone.workspaces, workspace(4, small)],
        [
            window("0xw", 2, at=(1440, 900), size=(1000, 500), floating=True),
            window("0xt", 1001, at=(0, 0), size=(2560, 1440)),
        ],
    )
    small = second(width=1920, height=1080, active=2)
    settled = snapshot(
        [left, small],
        [workspace(1, left), workspace(2, small), workspace(1001, small)],
        [
            window("0xw", 2, monitor_id=1, at=(1440, 900), size=(1000, 500), floating=True),
            window("0xt", 1001, monitor_id=1, at=(2560, 0), size=(1920, 1080)),
        ],
    )
    adapter.snapshots = [returned, settled]
    state = run(controller.reconcile(HyprEvent("monitoradded", "HDMI-A-1")))

    assert state.error is None
    assert adapter.applied == [
        [MoveWorkspaceToMonitor(2, "HDMI-A-1"), MoveWorkspaceToMonitor(1001, "HDMI-A-1")],
        [MoveWindow("0xw", 3480, 580), ResizeWindow("0xw", 1000, 500)],
    ]
    assert registry.get(SECOND_KEY, 2).extra["geometry"] == {"0xt": {"at": [3280, 480], "size": [1200, 600]}}
    assert workspaces_json(state)[(SECOND_KEY, 1)]["display_monitor_key"] == SECOND_KEY
    # Пространство, выданное Hyprland на время подключения, исчезло и удалено из реестра.
    assert registry.get(SECOND_KEY, 3) is None


def test_second_monitor_keeps_local_numbers(registry, state_path):
    left, right = monitor(), second()
    on_right = snapshot([left, right], [workspace(1, left), workspace(2, right)], [], cursor=(3000, 10))
    right_switched = snapshot(
        [left, second(active=1001)],
        [workspace(1, left), workspace(1001, right)],
        [],
        cursor=(3000, 10),
    )
    adapter = FakeAdapter([on_right, right_switched])
    controller = WindowController(adapter, registry)

    state = run(controller.switch(3))

    assert state.error is None
    assert adapter.applied == [[FocusMonitor("HDMI-A-1"), FocusWorkspace(1001)]]
    assert registry.get(SECOND_KEY, 3).workspace_id == 1001
    assert registry.get(KEY, 3) is None
    monitors = {m["key"]: m for m in state.to_json()["monitors"]}
    assert monitors[KEY]["active_workspace_id"] == 1
    assert monitors[SECOND_KEY]["active_number"] == 3

    on_left = snapshot(right_switched.monitors, right_switched.workspaces, [], cursor=(10, 10))
    left_switched = snapshot(
        [monitor(active=1002), second(active=1001)],
        [workspace(1002, left), workspace(1001, right)],
        [],
        cursor=(10, 10),
    )
    adapter.snapshots = [on_left, left_switched]
    state = run(controller.switch(3))

    assert adapter.applied[-1] == [FocusMonitor("DP-1"), FocusWorkspace(1002)]
    assert registry.get(KEY, 3).workspace_id == 1002
    assert registry.get(SECOND_KEY, 3).workspace_id == 1001
    # Перезапуск сервиса сохраняет локальные номера обоих мониторов.
    restored = WorkspaceRegistry(state_path, "sig")
    assert restored.get(SECOND_KEY, 3).workspace_id == 1001
    assert restored.get(KEY, 3).workspace_id == 1002


def test_toggle_adopts_unregistered_active_workspace(registry):
    mon = monitor()
    empty = snapshot([mon], [workspace(1, mon)], [])
    adapter = FakeAdapter([empty])
    controller = WindowController(adapter, registry)

    state = run(controller.toggle())

    assert state.error is None and state.revision == 1
    assert registry.get(KEY, 1).workspace_id == 1
    assert registry.get(KEY, 1).mode == "tiles"

    # Активное пространство, созданное в обход движка, получает свободный локальный номер.
    foreign = snapshot(
        [monitor(active=7)],
        [workspace(1, mon), workspace(7, mon)],
        [window("0xa", 1)],
    )
    adapter.snapshots = [foreign]
    state = run(controller.toggle())

    assert state.error is None
    assert registry.get(KEY, 2).workspace_id == 7
    assert registry.get(KEY, 2).mode == "tiles"
    assert registry.get(KEY, 1).mode == "tiles"


def test_reconcile_read_failure_returns_error(registry):
    class Broken(FakeAdapter):
        def snapshot(self):
            raise OSError("hyprctl not found")

    controller = WindowController(Broken([snapshot([monitor()], [], [])]), registry)

    state = run(controller.reconcile(EVENT))

    assert state is not None and state.error is not None and "hyprctl not found" in state.error
    assert state.revision == 0


def test_rejected_window_update_reports_error_and_keeps_others(registry):
    mon = monitor()
    base = snapshot([mon], [workspace(1, mon)], [])
    registry.resolve(1, KEY, base)
    opened = snapshot([mon], [workspace(1, mon)], [window("0xn", 1), window("0xm", 1, at=(1280, 0))])
    adapter = FakeAdapter([opened], fail_on=[0])
    controller = WindowController(adapter, registry)

    state = run(controller.reconcile(EVENT))

    assert state is not None and state.error is not None and "window update failed" in state.error
    assert [group[0] for group in adapter.applied] == [SetFloating("0xn", True), SetFloating("0xm", True)]
    assert registry.get(KEY, 1).extra["managed"] == ["0xn", "0xm"]
