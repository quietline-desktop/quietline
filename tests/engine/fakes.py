"""Построители снимков Hyprland и поддельный адаптер для тестов раскладки и контроллера."""

from collections.abc import Iterable, Sequence

from quietline_engine.hyprland import HyprlandError
from quietline_engine.types import CompositorSnapshot, HyprAction, Monitor, Window, Workspace


def monitor(
    id=0,
    name="DP-1",
    *,
    x=0,
    y=0,
    width=2560,
    height=1440,
    scale=1.0,
    reserved=(0, 0, 0, 0),
    active=1,
    focused=True,
    serial="SN1",
):
    """Монитор с серийным номером; по умолчанию 2560×1440 без отступов."""
    return Monitor(
        id=id,
        name=name,
        make="Dell Inc.",
        model="U2723QE",
        serial=serial,
        x=x,
        y=y,
        width=width,
        height=height,
        scale=scale,
        reserved=reserved,
        active_workspace_id=active,
        focused=focused,
    )


def workspace(id, mon):
    """Пространство на мониторе."""
    return Workspace(id=id, name=str(id), monitor=mon.name, monitor_id=mon.id, windows=0, tiled_layout="scrolling")


def window(
    address,
    workspace_id=1,
    *,
    monitor_id=0,
    at=(0, 0),
    size=(800, 600),
    floating=False,
    fullscreen=0,
    pinned=False,
    mapped=True,
    hidden=False,
    tags=(),
):
    """Окно пространства; по умолчанию видимое, тайловое и без тегов."""
    return Window(
        address=address,
        workspace_id=workspace_id,
        monitor_id=monitor_id,
        at=at,
        size=size,
        floating=floating,
        fullscreen=fullscreen,
        class_name="kitty",
        title=address,
        pid=4242,
        mapped=mapped,
        hidden=hidden,
        pinned=pinned,
        tags=tuple(tags),
    )


def snapshot(monitors, workspaces, windows, *, active=None, cursor=(10, 10)):
    """Снимок; `active` — адрес активного окна или готовое окно (может отсутствовать в `windows`)."""
    windows = tuple(windows)
    if isinstance(active, str):
        active = next(w for w in windows if w.address == active)
    return CompositorSnapshot(
        monitors=tuple(monitors),
        workspaces=tuple(workspaces),
        windows=windows,
        active_window=active,
        cursor_position=cursor,
    )


class FakeAdapter:
    """Отдаёт заготовленные снимки по очереди (последний повторяется) и записывает действия.

    `fail_on` — номера вызовов `apply` (с нуля), которые завершаются `HyprlandError`.
    `calls` — порядок обращений: `"snapshot"` и `"apply"`.
    """

    def __init__(self, snapshots: Sequence[CompositorSnapshot], *, fail_on: Iterable[int] = ()) -> None:
        self.snapshots = list(snapshots)
        self.fail_on = set(fail_on)
        self.applied: list[list[HyprAction]] = []
        self.calls: list[str] = []

    def snapshot(self) -> CompositorSnapshot:
        self.calls.append("snapshot")
        if len(self.snapshots) > 1:
            return self.snapshots.pop(0)
        return self.snapshots[0]

    def apply(self, actions: Sequence[HyprAction]) -> None:
        self.calls.append("apply")
        index = len(self.applied)
        self.applied.append(list(actions))
        if index in self.fail_on:
            raise HyprlandError("hyprctl eval failed: error: no such window")
