"""Типы снимка композитора, действий и событий Hyprland."""

from dataclasses import dataclass
from typing import Literal

# Теги диалогов и служебных окон, которые ставит config/hyprland/quietline.lua.
DIALOG_TAGS = frozenset({"quietline-modal", "quietline-native-float"})


@dataclass(frozen=True, slots=True)
class Monitor:
    """Монитор из `hyprctl -j monitors`; `reserved` — отступы (слева, сверху, справа, снизу)."""

    id: int
    name: str
    make: str
    model: str
    serial: str
    x: int
    y: int
    width: int
    height: int
    scale: float
    reserved: tuple[int, int, int, int]
    active_workspace_id: int
    focused: bool

    @property
    def work_area_width(self) -> float:
        """Логическая ширина рабочей области: `width / scale` без отступов слева и справа.

        `width` — пиксели режима монитора, а `reserved` и координаты окон — логические.
        """
        if self.scale <= 0:
            raise ValueError(f"invalid scale {self.scale} of monitor {self.name}")
        width = self.width / self.scale - self.reserved[0] - self.reserved[2]
        if width <= 0:
            raise ValueError(f"empty work area of monitor {self.name}")
        return width

    @property
    def work_area_height(self) -> float:
        """Логическая высота рабочей области: `height / scale` без отступов сверху и снизу."""
        if self.scale <= 0:
            raise ValueError(f"invalid scale {self.scale} of monitor {self.name}")
        height = self.height / self.scale - self.reserved[1] - self.reserved[3]
        if height <= 0:
            raise ValueError(f"empty work area of monitor {self.name}")
        return height


@dataclass(frozen=True, slots=True)
class Workspace:
    """Пространство из `hyprctl -j workspaces`; `monitor` — имя разъёма."""

    id: int
    name: str
    monitor: str
    monitor_id: int
    windows: int
    tiled_layout: str


@dataclass(frozen=True, slots=True)
class Window:
    """Окно из `hyprctl -j clients`; `at` и `size` — глобальные координаты макета.

    `pinned` — окно закреплено поверх всех пространств монитора. `tags` — теги окна;
    тег, поставленный правилом окна, Hyprland показывает с `*` в конце.
    """

    address: str
    workspace_id: int
    monitor_id: int
    at: tuple[int, int]
    size: tuple[int, int]
    floating: bool
    fullscreen: int
    class_name: str
    title: str
    pid: int
    mapped: bool
    hidden: bool
    pinned: bool = False
    tags: tuple[str, ...] = ()

    @property
    def dialog_tagged(self) -> bool:
        """Окно помечено тегом из `DIALOG_TAGS` (с `*` правила окна или без него)."""
        return any(tag.removesuffix("*") in DIALOG_TAGS for tag in self.tags)


@dataclass(frozen=True, slots=True)
class Column:
    """Колонка раскладки `scrolling`: окна сверху вниз и доля ширины рабочей области."""

    addresses: tuple[str, ...]
    width: float


@dataclass(frozen=True, slots=True)
class CompositorSnapshot:
    """Полное состояние Hyprland на момент чтения."""

    monitors: tuple[Monitor, ...]
    workspaces: tuple[Workspace, ...]
    windows: tuple[Window, ...]
    active_window: Window | None
    cursor_position: tuple[int, int]

    def columns(self, workspace_id: int) -> tuple[Column, ...]:
        """Колонки пространства слева направо.

        Колонка — группа видимых тайловых окон с одинаковым `at[0]`; её ширина —
        `size[0]` окна, делённая на логическую ширину рабочей области монитора пространства.
        """
        workspace = next((w for w in self.workspaces if w.id == workspace_id), None)
        if workspace is None:
            raise ValueError(f"unknown workspace {workspace_id}")
        monitor = next((m for m in self.monitors if m.id == workspace.monitor_id), None)
        if monitor is None:
            raise ValueError(f"unknown monitor {workspace.monitor_id}")

        groups: dict[int, list[Window]] = {}
        for window in self.windows:
            if window.workspace_id == workspace_id and window.mapped and not window.hidden and not window.floating:
                groups.setdefault(window.at[0], []).append(window)
        return tuple(
            Column(
                addresses=tuple(w.address for w in sorted(group, key=lambda w: w.at[1])),
                width=group[0].size[0] / monitor.work_area_width,
            )
            for _, group in sorted(groups.items())
        )


@dataclass(frozen=True, slots=True)
class HyprEvent:
    """Событие из `.socket2.sock`: строка `EVENT>>DATA`."""

    name: str
    data: str


@dataclass(frozen=True, slots=True)
class SetFloating:
    """Сделать окно плавающим или вернуть в раскладку."""

    address: str
    floating: bool


@dataclass(frozen=True, slots=True)
class MoveWindow:
    """Поставить плавающее окно в точку (пиксели)."""

    address: str
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class ResizeWindow:
    """Задать размер плавающего окна (пиксели)."""

    address: str
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class FocusWindow:
    """Сфокусировать окно."""

    address: str


@dataclass(frozen=True, slots=True)
class FocusWorkspace:
    """Открыть или создать пространство на мониторе фокуса."""

    workspace_id: int


@dataclass(frozen=True, slots=True)
class FocusMonitor:
    """Сфокусировать монитор по имени разъёма."""

    monitor: str


@dataclass(frozen=True, slots=True)
class MoveWindowToWorkspace:
    """Перенести окно на пространство; `follow` — перейти за окном."""

    address: str
    workspace_id: int
    follow: bool


@dataclass(frozen=True, slots=True)
class MoveWorkspaceToMonitor:
    """Перенести пространство на монитор."""

    workspace_id: int
    monitor: str


@dataclass(frozen=True, slots=True)
class ResizeColumn:
    """Ширина колонки окна в фокусе: доля рабочей области, 0 < fraction ≤ 1."""

    fraction: float


@dataclass(frozen=True, slots=True)
class SwapColumn:
    """Поменять колонку окна в фокусе с левой или правой соседней."""

    direction: Literal["l", "r"]


type HyprAction = (
    SetFloating
    | MoveWindow
    | ResizeWindow
    | FocusWindow
    | FocusWorkspace
    | FocusMonitor
    | MoveWindowToWorkspace
    | MoveWorkspaceToMonitor
    | ResizeColumn
    | SwapColumn
)
