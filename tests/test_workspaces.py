"""Тесты локальных пространств мониторов: ключи, ID, выбор фокуса и состояние сеанса."""

import json
import os
import stat
from pathlib import Path

import pytest

from quietline_engine.types import (
    CompositorSnapshot,
    Monitor,
    MoveWorkspaceToMonitor,
    Window,
    Workspace,
)
from quietline_engine.workspaces import (
    WorkspaceError,
    WorkspaceRegistry,
    focused_monitor,
    monitor_keys,
)


def monitor(id, name, x, active, *, make="Dell Inc.", model="U2723QE", serial="", width=1920, height=1080, scale=1.0):
    """Монитор с рабочей областью без отступов."""
    return Monitor(
        id=id,
        name=name,
        make=make,
        model=model,
        serial=serial,
        x=x,
        y=0,
        width=width,
        height=height,
        scale=scale,
        reserved=(0, 0, 0, 0),
        active_workspace_id=active,
        focused=id == 0,
    )


def workspace(id, monitor_obj):
    """Пространство на мониторе."""
    return Workspace(
        id=id, name=str(id), monitor=monitor_obj.name, monitor_id=monitor_obj.id, windows=0, tiled_layout="scrolling"
    )


def window(address, workspace_id, monitor_id):
    """Окно на пространстве."""
    return Window(
        address=address,
        workspace_id=workspace_id,
        monitor_id=monitor_id,
        at=(0, 0),
        size=(800, 600),
        floating=True,
        fullscreen=0,
        class_name="kitty",
        title="t",
        pid=1,
        mapped=True,
        hidden=False,
    )


def snapshot(monitors, *, windows=(), active=None, cursor=(0, 0)):
    """Снимок, где на каждом мониторе есть его активное пространство."""
    return CompositorSnapshot(
        monitors=tuple(monitors),
        workspaces=tuple(workspace(m.active_workspace_id, m) for m in monitors),
        windows=tuple(windows),
        active_window=active,
        cursor_position=cursor,
    )


@pytest.fixture
def state_path(tmp_path: Path) -> Path:
    return tmp_path / "runtime" / "quietline" / "state.json"


def test_two_monitors_have_independent_local_one(state_path):
    left = monitor(0, "DP-1", 0, 1, serial="AAA")
    right = monitor(1, "HDMI-A-1", 1920, 2, make="LG", model="27UK850", serial="BBB")
    snap = snapshot([left, right])
    keys = monitor_keys(snap)
    registry = WorkspaceRegistry(state_path, "sig-1")

    one_left = registry.resolve(1, keys["DP-1"], snap)
    one_right = registry.resolve(1, keys["HDMI-A-1"], snap)
    two_left = registry.resolve(2, keys["DP-1"], snap)
    two_right = registry.resolve(2, keys["HDMI-A-1"], snap)

    assert keys["DP-1"] != keys["HDMI-A-1"]
    # Активные пространства приняты как локальные 1, новые ID идут с 1001 без пересечений.
    assert (one_left.workspace_id, one_right.workspace_id) == (1, 2)
    assert (two_left.workspace_id, two_right.workspace_id) == (1001, 1002)
    assert one_left.monitor_key == keys["DP-1"]
    assert one_left.display_monitor_key == keys["DP-1"]
    assert one_left.number == 1
    assert one_left.mode == "windows"
    # Повторный вызов возвращает то же назначение.
    assert registry.resolve(2, keys["DP-1"], snap) == two_left


def test_new_workspace_id_avoids_visible_ids(state_path):
    left = monitor(0, "DP-1", 0, 1001, serial="AAA")
    snap = snapshot([left], windows=[window("0xa", 1002, 0)])
    key = monitor_keys(snap)["DP-1"]
    registry = WorkspaceRegistry(state_path, "sig-1")

    assert registry.resolve(1, key, snap).workspace_id == 1001
    assert registry.resolve(2, key, snap).workspace_id == 1003


def test_duplicate_serial_uses_connector():
    first = monitor(0, "DP-1", 0, 1, serial="SAME")
    second = monitor(1, "DP-2", 1920, 2, serial="SAME")
    unique = monitor(2, "DP-3", 3840, 3, make="LG", model="X", serial="OTHER")
    no_serial_a = monitor(3, "HDMI-A-1", 5760, 4, make="BOE", model="Y", serial="")
    no_serial_b = monitor(4, "HDMI-A-2", 7680, 5, make="BOE", model="Y", serial="")

    keys = monitor_keys(snapshot([first, second, unique, no_serial_a, no_serial_b]))

    assert "DP-1" in keys["DP-1"] and "DP-2" in keys["DP-2"]
    assert "SAME" in keys["DP-1"] and "SAME" in keys["DP-2"]
    assert "DP-3" not in keys["DP-3"]
    assert "OTHER" in keys["DP-3"]
    assert "HDMI-A-1" in keys["HDMI-A-1"] and "HDMI-A-2" in keys["HDMI-A-2"]
    assert len(set(keys.values())) == 5


def test_pointer_selects_monitor_without_active_window():
    left = monitor(0, "DP-1", 0, 1, serial="AAA")
    right = monitor(1, "DP-2", 1920, 2, serial="BBB")
    keys = monitor_keys(snapshot([left, right]))

    assert focused_monitor(snapshot([left, right], cursor=(2500, 300))) == keys["DP-2"]
    assert focused_monitor(snapshot([left, right], cursor=(100, 300))) == keys["DP-1"]
    # Активное окно важнее указателя.
    active = window("0xa", 2, 1)
    assert focused_monitor(snapshot([left, right], active=active, cursor=(100, 300))) == keys["DP-2"]


def test_pointer_uses_logical_geometry_of_scaled_monitor():
    left = monitor(0, "DP-1", 0, 1, serial="AAA", width=3840, height=2160, scale=2.0)
    right = monitor(1, "DP-2", 1920, 2, serial="BBB")
    keys = monitor_keys(snapshot([left, right]))

    # Логическая ширина левого монитора 1920, точка 1900 ещё на нём.
    assert focused_monitor(snapshot([left, right], cursor=(1900, 10))) == keys["DP-1"]
    assert focused_monitor(snapshot([left, right], cursor=(1920, 10))) == keys["DP-2"]


@pytest.mark.parametrize("number", [0, 11, -1, 100])
def test_switch_rejects_zero_and_eleven(state_path, number):
    left = monitor(0, "DP-1", 0, 1, serial="AAA")
    snap = snapshot([left])
    key = monitor_keys(snap)["DP-1"]
    registry = WorkspaceRegistry(state_path, "sig-1")

    with pytest.raises(WorkspaceError, match="1 to 10"):
        registry.resolve(number, key, snap)

    assert registry.get(key, number) is None
    assert not state_path.exists()


@pytest.mark.parametrize("number", [True, 1.0, "1"])
def test_resolve_rejects_non_integer_number(state_path, number):
    snap = snapshot([monitor(0, "DP-1", 0, 1, serial="AAA")])
    registry = WorkspaceRegistry(state_path, "sig-1")

    with pytest.raises(WorkspaceError, match="1 to 10"):
        registry.resolve(number, monitor_keys(snap)["DP-1"], snap)


def test_resolve_rejects_unknown_monitor(state_path):
    snap = snapshot([monitor(0, "DP-1", 0, 1, serial="AAA")])
    registry = WorkspaceRegistry(state_path, "sig-1")

    with pytest.raises(WorkspaceError, match="unknown monitor"):
        registry.resolve(1, "no-such-monitor", snap)


def test_new_hyprland_instance_discards_old_state(state_path):
    left = monitor(0, "DP-1", 0, 1, serial="AAA")
    snap = snapshot([left])
    key = monitor_keys(snap)["DP-1"]

    old = WorkspaceRegistry(state_path, "sig-old")
    old.resolve(2, key, snap)
    assert old.get(key, 2) is not None

    same = WorkspaceRegistry(state_path, "sig-old")
    assert same.get(key, 2).workspace_id == 1001

    fresh = WorkspaceRegistry(state_path, "sig-new")
    assert fresh.get(key, 2) is None
    assert fresh.get(key, 1) is None
    fresh.resolve(3, key, snap)
    saved = json.loads(state_path.read_text())
    assert saved["signature"] == "sig-new"
    assert [(r["number"], r["workspace_id"]) for r in saved["workspaces"]] == [(3, 1001)]


def test_state_file_is_private_and_atomic(state_path):
    snap = snapshot([monitor(0, "DP-1", 0, 1, serial="AAA")])
    registry = WorkspaceRegistry(state_path, "sig-1")
    registry.resolve(2, monitor_keys(snap)["DP-1"], snap)

    assert stat.S_IMODE(state_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(state_path.parent.stat().st_mode) == 0o700
    assert os.listdir(state_path.parent) == ["state.json"]


def test_unknown_record_fields_survive_reload(state_path):
    snap = snapshot([monitor(0, "DP-1", 0, 1, serial="AAA")])
    key = monitor_keys(snap)["DP-1"]
    WorkspaceRegistry(state_path, "sig-1").resolve(2, key, snap)

    saved = json.loads(state_path.read_text())
    saved["workspaces"][0]["floating_snapshot"] = {"0xa": [1, 2, 3, 4]}
    state_path.write_text(json.dumps(saved))

    registry = WorkspaceRegistry(state_path, "sig-1")
    assert registry.get(key, 2).extra == {"floating_snapshot": {"0xa": [1, 2, 3, 4]}}
    registry.resolve(3, key, snap)
    resaved = json.loads(state_path.read_text())
    assert resaved["workspaces"][0]["floating_snapshot"] == {"0xa": [1, 2, 3, 4]}


def test_corrupt_state_file_is_discarded(state_path):
    state_path.parent.mkdir(parents=True)
    state_path.write_text("{not json")
    registry = WorkspaceRegistry(state_path, "sig-1")

    assert registry.get("any", 1) is None


def test_from_environment_uses_runtime_dir(tmp_path):
    env = {"XDG_RUNTIME_DIR": str(tmp_path), "HYPRLAND_INSTANCE_SIGNATURE": "abc"}
    registry = WorkspaceRegistry.from_environment(env)
    snap = snapshot([monitor(0, "DP-1", 0, 1, serial="AAA")])
    registry.resolve(1, monitor_keys(snap)["DP-1"], snap)

    assert (tmp_path / "quietline" / "state.json").is_file()
    with pytest.raises(WorkspaceError, match="HYPRLAND_INSTANCE_SIGNATURE"):
        WorkspaceRegistry.from_environment({"XDG_RUNTIME_DIR": str(tmp_path)})
    with pytest.raises(WorkspaceError, match="XDG_RUNTIME_DIR"):
        WorkspaceRegistry.from_environment({"HYPRLAND_INSTANCE_SIGNATURE": "abc"})


def test_reconcile_adopts_active_workspaces_and_returns_move_for_misplaced(state_path):
    left = monitor(0, "DP-1", 0, 1, serial="AAA")
    right = monitor(1, "DP-2", 1920, 2, serial="BBB")
    snap = snapshot([left, right])
    keys = monitor_keys(snap)
    registry = WorkspaceRegistry(state_path, "sig-1")

    assert registry.reconcile(snap) == []
    assert registry.get(keys["DP-1"], 1).workspace_id == 1
    assert registry.get(keys["DP-2"], 1).workspace_id == 2

    registry.resolve(2, keys["DP-2"], snap)  # 1001 принадлежит правому монитору
    # Hyprland показывает 1001 на левом мониторе (например, после переподключения).
    moved = CompositorSnapshot(
        monitors=snap.monitors,
        workspaces=(*snap.workspaces, workspace(1001, left)),
        windows=(),
        active_window=None,
        cursor_position=(0, 0),
    )
    assert registry.reconcile(moved) == [MoveWorkspaceToMonitor(workspace_id=1001, monitor="DP-2")]


def test_reconcile_skips_workspaces_of_disconnected_monitor(state_path):
    left = monitor(0, "DP-1", 0, 1, serial="AAA")
    right = monitor(1, "DP-2", 1920, 2, serial="BBB")
    both = snapshot([left, right])
    keys = monitor_keys(both)
    registry = WorkspaceRegistry(state_path, "sig-1")
    registry.resolve(2, keys["DP-2"], both)

    alone = CompositorSnapshot(
        monitors=(left,),
        workspaces=(workspace(1, left), workspace(1001, left)),
        windows=(),
        active_window=None,
        cursor_position=(0, 0),
    )
    assert registry.reconcile(alone) == []
    assert registry.get(keys["DP-2"], 2).workspace_id == 1001
