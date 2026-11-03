"""Тесты расчёта переходов «Окна ↔ Тайлы» без Hyprland."""

import pytest
from fakes import monitor, snapshot, window, workspace

from quietline_engine.layout import LayoutError, LayoutPlanner
from quietline_engine.types import FocusWindow, MoveWindow, ResizeColumn, ResizeWindow, SetFloating
from quietline_engine.workspaces import WorkspaceRef

KEY = "Dell Inc.|U2723QE|SN1"


def ref(mode="windows", **extra):
    """Запись пространства 1 монитора `KEY` с дополнительными данными."""
    return WorkspaceRef(KEY, KEY, 1, 1, mode, extra)


def test_windows_to_tiles_preserves_floating_geometry():
    mon = monitor(reserved=(0, 40, 0, 0))
    snap = snapshot(
        [mon],
        [workspace(1, mon)],
        [
            window("0xb", at=(1000, 300), size=(900, 700), floating=True),
            window("0xa", at=(100, 140), size=(800, 600), floating=True),
        ],
        active="0xb",
    )

    plan = LayoutPlanner().to_tiles(ref(managed=["0xa", "0xb"]), snap)

    assert plan.mode == "tiles"
    assert plan.extra["geometry"] == {
        "0xa": {"at": [100, 140], "size": [800, 600]},
        "0xb": {"at": [1000, 300], "size": [900, 700]},
    }
    # Без снимка колонок окна встают слева направо по текущему положению.
    assert plan.actions == (
        SetFloating("0xa", False),
        SetFloating("0xb", False),
        FocusWindow("0xb"),
    )
    assert plan.reverse == (
        SetFloating("0xa", True),
        ResizeWindow("0xa", 800, 600),
        MoveWindow("0xa", 100, 140),
        SetFloating("0xb", True),
        ResizeWindow("0xb", 900, 700),
        MoveWindow("0xb", 1000, 300),
        FocusWindow("0xb"),
    )
    assert plan.expected_floating == {"0xa": False, "0xb": False}


def test_tiles_to_windows_restores_geometry_clamped_to_work_area():
    # Второй монитор: 2400×1350 при масштабе 1.25 — логически 1920×1080, панель 40 сверху.
    mon = monitor(1, "HDMI-A-1", x=2560, width=2400, height=1350, scale=1.25, reserved=(0, 40, 0, 0))
    snap = snapshot(
        [mon],
        [workspace(1, mon)],
        [
            window("0xc", monitor_id=1, at=(3520, 600), size=(960, 520)),
            window("0xa", monitor_id=1, at=(2560, 40), size=(960, 1040)),
            window("0xb", monitor_id=1, at=(3520, 40), size=(960, 520)),
        ],
        active="0xa",
    )
    saved = {
        # Не помещается по положению: сдвигается внутрь рабочей области.
        "0xa": {"at": [4560, 900], "size": [800, 600]},
        # Больше рабочей области: прижимается к её началу и ограничивается её размером.
        "0xb": {"at": [100, 100], "size": [3000, 2000]},
    }

    plan = LayoutPlanner().to_windows(ref("tiles", managed=["0xa", "0xb", "0xc"], geometry=saved), snap)

    assert plan.mode == "windows"
    assert plan.actions == (
        SetFloating("0xa", True),
        ResizeWindow("0xa", 800, 600),
        MoveWindow("0xa", 3680, 480),
        SetFloating("0xb", True),
        ResizeWindow("0xb", 1920, 1040),
        MoveWindow("0xb", 2560, 40),
        # Без сохранённой геометрии — 60% рабочей области по центру.
        SetFloating("0xc", True),
        ResizeWindow("0xc", 1152, 624),
        MoveWindow("0xc", 2944, 248),
        FocusWindow("0xa"),
    )
    assert plan.extra["columns"] == [
        {"addresses": ["0xa"], "width": 0.5},
        {"addresses": ["0xb", "0xc"], "width": 0.5},
    ]
    # Сохранённая геометрия не заменяется ограниченной.
    assert plan.extra["geometry"] == saved
    assert plan.expected_floating == {"0xa": True, "0xb": True, "0xc": True}
    assert plan.reverse == (
        SetFloating("0xa", False),
        SetFloating("0xb", False),
        SetFloating("0xc", False),
        FocusWindow("0xa"),
        ResizeColumn(0.5),
        FocusWindow("0xb"),
        ResizeColumn(0.5),
        FocusWindow("0xc"),
        ResizeColumn(0.5),
        FocusWindow("0xa"),
    )


def test_reenter_tiles_restores_column_order_and_widths():
    mon = monitor()
    snap = snapshot(
        [mon],
        [workspace(1, mon)],
        [
            window("0xa", at=(500, 100), floating=True),
            window("0xb", at=(900, 100), floating=True),
            window("0xc", at=(1300, 100), floating=True),
            window("0xd", at=(10, 100), floating=True),
        ],
        active="0xb",
    )
    columns = [
        {"addresses": ["0xc"], "width": 0.3},
        # Колонка из двух окон восстанавливается двумя колонками в порядке её окон.
        {"addresses": ["0xa", "0xb"], "width": 0.7},
    ]

    plan = LayoutPlanner().to_tiles(ref(managed=["0xa", "0xb", "0xc", "0xd"], columns=columns), snap)

    assert plan.actions == (
        SetFloating("0xc", False),
        SetFloating("0xa", False),
        SetFloating("0xb", False),
        # Окно, которого не было в снимке колонок, встаёт последним без ширины.
        SetFloating("0xd", False),
        FocusWindow("0xc"),
        ResizeColumn(0.3),
        FocusWindow("0xa"),
        ResizeColumn(0.7),
        FocusWindow("0xb"),
        ResizeColumn(0.7),
        FocusWindow("0xb"),
    )
    assert plan.extra["columns"] == columns


def test_dialog_and_fullscreen_not_rearranged():
    mon = monitor()
    windows = [
        window("0xa", at=(100, 100), floating=True),
        window("0xf", at=(0, 0), size=(2560, 1440), floating=True, fullscreen=2),
        window("0xp", at=(2000, 50), floating=True, pinned=True),
        window("0xh", at=(300, 300), floating=True, hidden=True),
        # Впервые увиденное плавающее окно — диалог; тайловое — управляемое.
        window("0xd", at=(700, 400), size=(400, 200), floating=True),
        window("0xe", at=(0, 0), size=(1280, 1440)),
    ]
    snap = snapshot([mon], [workspace(1, mon)], windows, active="0xd")

    to_tiles = LayoutPlanner().to_tiles(ref(managed=["0xa", "0xf", "0xp", "0xh"]), snap)

    assert to_tiles.actions == (SetFloating("0xa", False), FocusWindow("0xd"))
    assert to_tiles.expected_floating == {"0xa": False}
    assert to_tiles.extra["managed"] == ["0xa", "0xf", "0xp", "0xh", "0xe"]
    assert to_tiles.extra["dialogs"] == ["0xd"]

    tiled = [
        window("0xa", at=(0, 0), size=(1280, 1440)),
        window("0xf", at=(0, 0), size=(2560, 1440), fullscreen=2),
        window("0xp", at=(2000, 50), floating=True, pinned=True),
        window("0xd", at=(700, 400), size=(400, 200), floating=True),
        window("0xe", at=(1280, 0), size=(1280, 1440)),
    ]
    snap = snapshot([mon], [workspace(1, mon)], tiled, active="0xd")

    to_windows = LayoutPlanner().to_windows(ref("tiles", **to_tiles.extra), snap)

    touched = {getattr(action, "address", None) for action in to_windows.actions}
    assert touched == {"0xa", "0xe", "0xd"}
    assert to_windows.actions[-1] == FocusWindow("0xd")
    assert to_windows.expected_floating == {"0xa": True, "0xe": True}
    assert to_windows.extra["dialogs"] == ["0xd"]
    # Закрытое окно уходит из списка управляемых.
    assert to_windows.extra["managed"] == ["0xa", "0xf", "0xp", "0xe"]


def test_dialog_tags_classify_only_unknown_windows():
    mon = monitor()
    windows = [
        # Управляемое окно с тегом остаётся управляемым.
        window("0xa", at=(100, 100), floating=True, tags=("quietline-native-float", "quietline-modal*")),
        window("0xb", at=(900, 100), floating=True),
        # Впервые увиденное тайловое окно с тегом — диалог, а не управляемое.
        window("0xt", at=(0, 0), size=(1280, 1440), tags=("quietline-native-float",)),
    ]
    snap = snapshot([mon], [workspace(1, mon)], windows, active="0xb")

    to_tiles = LayoutPlanner().to_tiles(ref(managed=["0xa", "0xb"]), snap)

    assert to_tiles.actions == (SetFloating("0xa", False), SetFloating("0xb", False), FocusWindow("0xb"))
    assert to_tiles.extra["managed"] == ["0xa", "0xb"]
    assert to_tiles.extra["dialogs"] == ["0xt"]


def test_active_window_missing_from_windows_is_not_refocused():
    mon = monitor()
    ghost = window("0xdead", floating=True)
    snap = snapshot([mon], [workspace(1, mon)], [window("0xa", floating=True)], active=ghost)

    plan = LayoutPlanner().to_tiles(ref(managed=["0xa"]), snap)

    assert plan.actions == (SetFloating("0xa", False),)


def test_malformed_saved_data_is_ignored():
    mon = monitor()
    snap = snapshot([mon], [workspace(1, mon)], [window("0xa", at=(10, 20), floating=True)])

    plan = LayoutPlanner().to_tiles(
        ref(managed=["0xa", 5], columns=[{"addresses": "0xa"}, {"addresses": ["0xa"], "width": "wide"}]), snap
    )

    assert plan.actions == (SetFloating("0xa", False),)
    assert plan.extra["managed"] == ["0xa"]


def test_unknown_workspace_monitor_is_a_layout_error():
    mon = monitor()
    snap = snapshot([mon], [], [window("0xa")])

    with pytest.raises(LayoutError):
        LayoutPlanner().to_windows(ref("tiles", managed=["0xa"]), snap)
