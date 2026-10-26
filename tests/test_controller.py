"""Тесты контроллера: последовательное переключение режима, проверка результата и откат."""

import asyncio
import json
import threading

import pytest
from fakes import FakeAdapter, monitor, snapshot, window, workspace

from quietline_engine.controller import PublicState, WindowController
from quietline_engine.types import FocusWindow, MoveWindow, ResizeWindow, SetFloating
from quietline_engine.workspaces import WorkspaceRegistry

KEY = "Dell Inc.|U2723QE|SN1"
SECOND_KEY = "Dell Inc.|U2723QE|SN2"


@pytest.fixture
def registry(tmp_path):
    return WorkspaceRegistry(tmp_path / "quietline" / "state.json", "sig")


def run(coroutine):
    return asyncio.run(coroutine)


def floating_snapshot():
    """Пространство 1 в режиме «Окна»: два плавающих окна и диалог."""
    mon = monitor(reserved=(0, 40, 0, 0))
    return snapshot(
        [mon],
        [workspace(1, mon)],
        [
            window("0xa", at=(100, 140), size=(800, 600), floating=True),
            window("0xb", at=(1000, 300), size=(900, 700), floating=True),
            window("0xd", at=(700, 400), size=(400, 200), floating=True),
        ],
        active="0xb",
    )


def tiled_snapshot(*addresses):
    """Те же окна после перехода в «Тайлы»; диалог остаётся плавающим."""
    mon = monitor(reserved=(0, 40, 0, 0))
    columns = {"0xa": (0, 40), "0xb": (1280, 40)}
    windows = [window(a, at=columns[a], size=(1280, 1400)) for a in addresses]
    windows.append(window("0xd", at=(700, 400), size=(400, 200), floating=True))
    # Снимок не атомарный: активное окно может уже отсутствовать среди окон.
    active = window("0xb", at=columns["0xb"], size=(1280, 1400))
    return snapshot([mon], [workspace(1, mon)], windows, active=active)


def prepare(registry, snap, managed=("0xa", "0xb")):
    """Регистрирует пространство 1 и помечает окна управляемыми, а `0xd` — диалогом."""
    ref = registry.resolve(1, registry.focused_monitor(snap), snap)
    return registry.update(ref, extra={"managed": list(managed), "dialogs": ["0xd"]})


def test_toggle_confirms_mode_and_persists_snapshots(registry, tmp_path):
    first = floating_snapshot()
    prepare(registry, first)
    adapter = FakeAdapter([first, tiled_snapshot("0xa", "0xb")])
    controller = WindowController(adapter, registry)

    state = run(controller.toggle())

    assert adapter.calls == ["snapshot", "apply", "snapshot"]
    assert adapter.applied == [[SetFloating("0xa", False), SetFloating("0xb", False), FocusWindow("0xb")]]
    assert isinstance(state, PublicState)
    assert state.revision == 1 and state.error is None
    data = state.to_json()
    assert json.loads(json.dumps(data)) == data
    assert data["revision"] == 1 and data["error"] is None
    assert data["monitors"] == [
        {
            "key": KEY,
            "name": "DP-1",
            "focused": True,
            "active_workspace_id": 1,
            "active_number": 1,
            "mode": "tiles",
        }
    ]
    assert data["workspaces"] == [
        {"monitor_key": KEY, "display_monitor_key": KEY, "number": 1, "workspace_id": 1, "mode": "tiles"}
    ]

    # Перезапуск сервиса: новый реестр читает режим и снимки из того же файла.
    restored = WorkspaceRegistry(tmp_path / "quietline" / "state.json", "sig").get(KEY, 1)
    assert restored.mode == "tiles"
    assert restored.extra["geometry"] == {
        "0xa": {"at": [100, 140], "size": [800, 600]},
        "0xb": {"at": [1000, 300], "size": [900, 700]},
    }
    assert restored.extra["dialogs"] == ["0xd"]


def test_toggle_back_restores_saved_geometry(registry):
    first = floating_snapshot()
    prepare(registry, first)
    tiled = tiled_snapshot("0xa", "0xb")
    adapter = FakeAdapter([first, tiled, tiled, first])
    controller = WindowController(adapter, registry)

    async def scenario():
        await controller.toggle()
        return await controller.toggle()

    state = run(scenario())

    assert state.revision == 2 and state.error is None
    assert adapter.applied[1] == [
        SetFloating("0xa", True),
        MoveWindow("0xa", 100, 140),
        ResizeWindow("0xa", 800, 600),
        SetFloating("0xb", True),
        MoveWindow("0xb", 1000, 300),
        ResizeWindow("0xb", 900, 700),
        FocusWindow("0xb"),
    ]
    ref = registry.get(KEY, 1)
    assert ref.mode == "windows"
    assert ref.extra["columns"] == [
        {"addresses": ["0xa"], "width": 0.5},
        {"addresses": ["0xb"], "width": 0.5},
    ]


@pytest.mark.parametrize("failure", ["rejected", "window_closed", "ignored"])
def test_failed_or_interrupted_transition_keeps_old_mode(registry, failure):
    first = floating_snapshot()
    prepare(registry, first)
    if failure == "rejected":
        # Hyprland отклоняет переход; повторное чтение показывает исходные окна.
        adapter = FakeAdapter([first, first], fail_on=[0])
    elif failure == "window_closed":
        # Окно 0xb закрылось посреди перехода: проверка снимка не проходит.
        adapter = FakeAdapter([first, tiled_snapshot("0xa"), tiled_snapshot("0xa")])
    else:
        # Hyprland ответил `ok`, но окна остались плавающими.
        adapter = FakeAdapter([first, first])
    controller = WindowController(adapter, registry)

    state = run(controller.toggle())

    assert state.revision == 0
    assert state.error is not None and "mode switch failed" in state.error
    if failure == "window_closed":
        assert "0xb" in state.error
    if failure == "ignored":
        assert "did not become tiled" in state.error
    assert state.to_json()["workspaces"][0]["mode"] == "windows"
    assert state.to_json()["monitors"][0]["mode"] == "windows"
    assert registry.get(KEY, 1).mode == "windows"
    assert "geometry" not in registry.get(KEY, 1).extra
    # Обратный план применяется по одному действию, чтобы закрытое окно не мешало остальным.
    assert adapter.applied[1:] == [
        [SetFloating("0xa", True)],
        [MoveWindow("0xa", 100, 140)],
        [ResizeWindow("0xa", 800, 600)],
        [SetFloating("0xb", True)],
        [MoveWindow("0xb", 1000, 300)],
        [ResizeWindow("0xb", 900, 700)],
        [FocusWindow("0xb")],
    ]
    assert adapter.calls[-1] == "snapshot"

    # Следующая команда не зависает и выполняется.
    adapter.snapshots = [first, tiled_snapshot("0xa", "0xb")]
    adapter.fail_on = set()
    state = run(asyncio.wait_for(controller.toggle(), timeout=2))
    assert state.error is None and state.revision == 1
    assert registry.get(KEY, 1).mode == "tiles"


def test_rollback_failures_are_tolerated(registry):
    first = floating_snapshot()
    prepare(registry, first)
    adapter = FakeAdapter([first, first], fail_on=range(100))
    controller = WindowController(adapter, registry)

    state = run(controller.toggle())

    assert state.revision == 0 and state.error is not None
    assert state.error.endswith("; rollback incomplete")
    assert adapter.calls[-1] == "snapshot"


def test_snapshot_failure_returns_error_without_actions(registry):
    class Broken(FakeAdapter):
        def snapshot(self):
            raise OSError("hyprctl not found")

    controller = WindowController(Broken([floating_snapshot()]), registry)

    state = run(controller.toggle())

    assert state.revision == 0
    assert state.error is not None and "hyprctl not found" in state.error
    assert state.monitors == ()


def test_toggle_targets_given_monitor(registry):
    left = monitor(active=1, focused=True)
    right = monitor(1, "HDMI-A-1", x=2560, active=1001, focused=False, serial="SN2")
    windows = [
        window("0xa", 1, at=(100, 100), floating=True),
        window("0xr", 1001, monitor_id=1, at=(2560, 0), size=(2560, 1440)),
    ]
    snap = snapshot([left, right], [workspace(1, left), workspace(1001, right)], windows, active="0xa")
    registry.resolve(1, KEY, snap)
    adapter = FakeAdapter([snap])
    controller = WindowController(adapter, registry)

    state = run(controller.toggle(SECOND_KEY))

    assert state.error is None
    # Окно 0xr уже в раскладке и впервые увидено тайловым: переход в «Тайлы» его не трогает.
    assert adapter.applied == []
    assert registry.get(SECOND_KEY, 1).mode == "tiles"
    assert registry.get(SECOND_KEY, 1).extra["managed"] == ["0xr"]
    assert registry.get(KEY, 1).mode == "windows"
    modes = {m["key"]: m["mode"] for m in state.to_json()["monitors"]}
    assert modes == {KEY: "windows", SECOND_KEY: "tiles"}


def test_toggle_unknown_monitor_returns_error_without_actions(registry):
    snap = floating_snapshot()
    prepare(registry, snap)
    adapter = FakeAdapter([snap])
    controller = WindowController(adapter, registry)

    state = run(controller.toggle("missing"))

    assert state.error is not None and "missing" in state.error
    assert adapter.applied == []
    assert state.revision == 0


def test_commands_are_serialised(registry):
    first = floating_snapshot()
    prepare(registry, first)
    tiled = tiled_snapshot("0xa", "0xb")
    adapter = FakeAdapter([first, tiled, tiled, first])
    controller = WindowController(adapter, registry)

    async def scenario():
        return await asyncio.gather(controller.toggle(), controller.toggle())

    states = run(scenario())

    assert adapter.calls == ["snapshot", "apply", "snapshot", "snapshot", "apply", "snapshot"]
    assert [s.revision for s in states] == [1, 2]
    assert registry.get(KEY, 1).mode == "windows"


class BlockingAdapter(FakeAdapter):
    """Первый `apply` ждёт `release`; отмечает, если два `apply` выполняются одновременно."""

    def __init__(self, snapshots):
        super().__init__(snapshots)
        self.started = threading.Event()
        self.release = threading.Event()
        self.overlap = False
        self._running = 0
        self._guard = threading.Lock()

    def apply(self, actions):
        with self._guard:
            self._running += 1
            self.overlap |= self._running > 1
        try:
            if not self.started.is_set():
                self.started.set()
                assert self.release.wait(5)
            super().apply(actions)
        finally:
            with self._guard:
                self._running -= 1


def test_cancelled_toggle_finishes_transition_under_lock(registry):
    first = floating_snapshot()
    prepare(registry, first)
    tiled = tiled_snapshot("0xa", "0xb")
    adapter = BlockingAdapter([first, tiled, tiled, first])
    controller = WindowController(adapter, registry)

    async def scenario():
        cancelled = asyncio.create_task(controller.toggle())
        await asyncio.to_thread(adapter.started.wait, 5)
        cancelled.cancel()
        following = asyncio.create_task(controller.toggle())
        await asyncio.sleep(0.05)
        # Отменённый переход ещё держит блокировку: следующая команда не читала снимок.
        assert adapter.calls == ["snapshot"]
        adapter.release.set()
        with pytest.raises(asyncio.CancelledError):
            await cancelled
        # Переход подтверждён и сохранён, хотя вызывающий отменён.
        assert registry.get(KEY, 1).mode == "tiles"
        return await asyncio.wait_for(following, timeout=5)

    state = run(scenario())

    assert not adapter.overlap
    assert adapter.calls == ["snapshot", "apply", "snapshot", "snapshot", "apply", "snapshot"]
    assert state.error is None and state.revision == 2
    assert registry.get(KEY, 1).mode == "windows"


def test_unexpected_failure_after_apply_rolls_back(registry, monkeypatch):
    first = floating_snapshot()
    prepare(registry, first)
    adapter = FakeAdapter([first, tiled_snapshot("0xa", "0xb"), first])
    controller = WindowController(adapter, registry)

    def broken_update(*args, **kwargs):
        raise RuntimeError("state store is broken")

    monkeypatch.setattr(registry, "update", broken_update)

    state = run(controller.toggle())

    assert state.revision == 0
    assert state.error == "mode switch failed: cannot save workspace state: state store is broken"
    assert adapter.applied[1:] == [
        [SetFloating("0xa", True)],
        [MoveWindow("0xa", 100, 140)],
        [ResizeWindow("0xa", 800, 600)],
        [SetFloating("0xb", True)],
        [MoveWindow("0xb", 1000, 300)],
        [ResizeWindow("0xb", 900, 700)],
        [FocusWindow("0xb")],
    ]
    assert adapter.calls[-1] == "snapshot"
    assert state.to_json()["workspaces"][0]["mode"] == "windows"
