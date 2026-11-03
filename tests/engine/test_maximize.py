"""Тесты разворачивания окна размером: команда планировщика и перевод `maximized` Hyprland в сверке."""

import pytest
from fakes import monitor, snapshot, window, workspace

from quietline_engine.layout import LayoutError, LayoutPlanner
from quietline_engine.types import FrameExtents, MoveWindow, ResizeWindow, SetFloating, SetMaximized
from quietline_engine.workspaces import WorkspaceRef

KEY = "Dell Inc.|U2723QE|SN1"
# Панель 30 px сверху: рабочая область (0, 30, 2560, 1410); рамка окна 2 px, заголовок 32 px.
MON = monitor(reserved=(0, 30, 0, 0))
FRAME_EXTENTS = FrameExtents(border=2, title=32)
FRAME_AT, FRAME_SIZE = (2, 64), (2556, 1374)


def ref(mode="windows", **extra):
    return WorkspaceRef(KEY, KEY, 1, 1, mode, extra)


def snap(*windows, active=None):
    return snapshot([MON], [workspace(1, MON)], windows, active=active, frame=FRAME_EXTENTS)


def test_floating_window_fills_frame_and_remembers_geometry():
    plan = LayoutPlanner().maximize(ref(managed=["0xa"]), snap(window("0xa", at=(100, 200), size=(800, 600), floating=True)), "0xa")

    assert plan.actions == (MoveWindow("0xa", *FRAME_AT), ResizeWindow("0xa", *FRAME_SIZE))
    assert plan.extra["maximized"] == {"0xa": {"at": [100, 200], "size": [800, 600]}}
    assert plan.extra["managed"] == ["0xa"]


def test_maximized_window_returns_to_remembered_geometry():
    workspace_ref = ref(managed=["0xa"], maximized={"0xa": {"at": [100, 200], "size": [800, 600]}})
    # Допуск 2 px: окно, сдвинутое Hyprland на пиксель, всё ещё развёрнуто.
    current = window("0xa", at=(3, 64), size=(2555, 1374), floating=True)

    plan = LayoutPlanner().maximize(workspace_ref, snap(current), "0xa")

    assert plan.actions == (MoveWindow("0xa", 100, 200), ResizeWindow("0xa", 800, 600))
    assert "maximized" not in plan.extra


def test_window_moved_after_maximizing_is_maximized_again():
    workspace_ref = ref(maximized={"0xa": {"at": [100, 200], "size": [800, 600]}})
    moved = window("0xa", at=(500, 500), size=(1200, 900), floating=True)

    plan = LayoutPlanner().maximize(workspace_ref, snap(moved), "0xa")

    assert plan.actions == (MoveWindow("0xa", *FRAME_AT), ResizeWindow("0xa", *FRAME_SIZE))
    assert plan.extra["maximized"] == {"0xa": {"at": [500, 500], "size": [1200, 900]}}


def test_restored_geometry_is_clamped_to_work_area():
    workspace_ref = ref(maximized={"0xa": {"at": [2400, 1300], "size": [800, 600]}})

    plan = LayoutPlanner().maximize(workspace_ref, snap(window("0xa", at=FRAME_AT, size=FRAME_SIZE, floating=True)), "0xa")

    assert plan.actions == (MoveWindow("0xa", 1760, 840), ResizeWindow("0xa", 800, 600))


def test_tiled_window_toggles_hyprland_maximized():
    planner = LayoutPlanner()
    assert planner.maximize(ref("tiles"), snap(window("0xa")), "0xa").actions == (SetMaximized("0xa", True),)
    assert planner.maximize(ref("tiles"), snap(window("0xa", fullscreen=1)), "0xa").actions == (SetMaximized("0xa", False),)


def test_floating_window_leaves_hyprland_maximized():
    workspace_ref = ref(maximizing=["0xa"])

    plan = LayoutPlanner().maximize(workspace_ref, snap(window("0xa", floating=True, fullscreen=1)), "0xa")

    assert plan.actions == (SetMaximized("0xa", False),)
    assert "maximizing" not in plan.extra and "maximized" not in plan.extra


@pytest.mark.parametrize(
    ("windows", "message"),
    [
        ((window("0xa", floating=True, fullscreen=2),), "full screen"),
        ((window("0xa", workspace_id=2, floating=True),), "not on workspace 1"),
        ((), "not on workspace 1"),
    ],
)
def test_maximize_rejects_fullscreen_and_foreign_windows(windows, message):
    with pytest.raises(LayoutError, match=message):
        LayoutPlanner().maximize(ref(), snap(*windows), "0xa")


def reconcile(workspace_ref, *windows):
    updates = LayoutPlanner().reconcile([workspace_ref], snap(*windows))
    return updates[0] if updates else None


def test_application_maximize_request_becomes_frame_geometry():
    workspace_ref = ref(managed=["0xa"])

    first = reconcile(workspace_ref, window("0xa", at=FRAME_AT, size=FRAME_SIZE, floating=True, fullscreen=1))
    assert [c.actions for c in first.changes] == [(SetMaximized("0xa", False),)]
    assert first.extra["maximizing"] == ["0xa"]

    # Hyprland вернул окну прежнюю геометрию: она запоминается, окно встаёт в рамку.
    second = reconcile(WorkspaceRef(KEY, KEY, 1, 1, "windows", first.extra),
                       window("0xa", at=(100, 200), size=(800, 600), floating=True))
    assert [c.actions for c in second.changes] == [(MoveWindow("0xa", *FRAME_AT), ResizeWindow("0xa", *FRAME_SIZE))]
    assert second.extra["maximized"] == {"0xa": {"at": [100, 200], "size": [800, 600]}}
    assert "maximizing" not in second.extra


def test_application_maximize_request_on_maximized_window_restores_it():
    workspace_ref = ref(managed=["0xa"], maximized={"0xa": {"at": [100, 200], "size": [800, 600]}})

    update = reconcile(workspace_ref, window("0xa", at=FRAME_AT, size=FRAME_SIZE, floating=True, fullscreen=1))

    assert [c.actions for c in update.changes] == [
        (SetMaximized("0xa", False), MoveWindow("0xa", 100, 200), ResizeWindow("0xa", 800, 600))
    ]
    assert "maximized" not in update.extra


def test_window_opened_maximized_is_floated_into_frame():
    first = reconcile(ref(), window("0xn", at=(0, 30), size=(2560, 1410), fullscreen=1))
    assert [c.actions for c in first.changes] == [(SetMaximized("0xn", False),)]

    # Окно впервые классифицируется: управляемое, плавающее, прежняя геометрия — по центру.
    second = reconcile(WorkspaceRef(KEY, KEY, 1, 1, "windows", first.extra), window("0xn", at=(0, 30), size=(1280, 720)))
    assert [c.actions for c in second.changes] == [
        (SetFloating("0xn", True), MoveWindow("0xn", *FRAME_AT), ResizeWindow("0xn", *FRAME_SIZE))
    ]
    assert second.extra["managed"] == ["0xn"]
    assert second.extra["maximized"] == {"0xn": {"at": [512, 312], "size": [1536, 846]}}


def test_tiles_workspace_keeps_hyprland_maximized():
    update = reconcile(ref("tiles", managed=["0xa"]), window("0xa", fullscreen=1))
    assert update.changes == () and "maximizing" not in update.extra


def test_closed_window_drops_its_maximize_record():
    workspace_ref = ref(managed=["0xb"], maximized={"0xa": {"at": [1, 2], "size": [3, 4]}}, maximizing=["0xc"])

    update = reconcile(workspace_ref, window("0xb", at=(100, 200), size=(800, 600), floating=True))

    assert "maximized" not in update.extra and "maximizing" not in update.extra
