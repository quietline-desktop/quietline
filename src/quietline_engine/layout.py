"""Расчёт переходов пространства между режимами «Окна» и «Тайлы» и сверки его окон.

Планировщик чистый: по записи пространства и снимку Hyprland он возвращает действия,
обратный план и новые данные записи, ничего не выполняя. Данные записи (`WorkspaceRef.extra`):

- `managed` — адреса окон, которыми управляет движок: окно становится управляемым, если
  при первой встрече на пространстве оно было в раскладке (не плавающим);
- `dialogs` — адреса окон, которые при первой встрече уже были плавающими (диалоги и
  служебные окна); они не меняются массово ни в одном режиме;
- `geometry` — `{адрес: {"at": [x, y], "size": [w, h]}}`, геометрия плавающих окон
  на момент последнего перехода в «Тайлы»;
- `columns` — `[{"addresses": [...], "width": доля}]`, колонки на момент последнего
  перехода в «Окна»;
- `work_area` — `[x, y, ширина, высота]`, рабочая область монитора показа на момент
  последней сверки окон;
- `pending` — `{адрес: {"floating": bool | None, "at": [x, y] | None, "size": [w, h] | None}}`,
  целевое состояние окон, действия сверки для которых Hyprland отклонил; каждая сверка
  повторяет их, пока окно не придёт в это состояние или не исчезнет с пространства.

Переход меняет только управляемые окна, которые видимы, не закреплены и не в
полноэкранном режиме.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from quietline_engine.types import (
    Column,
    CompositorSnapshot,
    FocusWindow,
    HyprAction,
    Monitor,
    MoveWindow,
    ResizeColumn,
    ResizeWindow,
    SetFloating,
    Window,
)
from quietline_engine.workspaces import Mode, WorkspaceRef

MANAGED = "managed"
DIALOGS = "dialogs"
GEOMETRY = "geometry"
COLUMNS = "columns"
WORK_AREA = "work_area"
PENDING = "pending"
# Доля рабочей области по каждой оси для окна без сохранённой геометрии.
DEFAULT_SIZE_FRACTION = 0.6


class LayoutError(Exception):
    """Снимок не позволяет рассчитать переход (нет пространства, монитора или рабочей области)."""


@dataclass(frozen=True, slots=True)
class Geometry:
    """Положение и размер окна в глобальных логических координатах."""

    at: tuple[int, int]
    size: tuple[int, int]

    def to_json(self) -> dict[str, list[int]]:
        return {"at": list(self.at), "size": list(self.size)}


@dataclass(frozen=True, slots=True)
class TransitionPlan:
    """Переход пространства в режим `mode`.

    `actions` выполняются по порядку; `reverse` возвращает окна, которые меняет переход,
    в состояние снимка до перехода. `expected_floating` — какое состояние `floating`
    должно быть у этих окон после перехода. `extra` — данные записи пространства,
    которые сохраняются только после подтверждённого перехода.
    """

    mode: Mode
    actions: tuple[HyprAction, ...]
    reverse: tuple[HyprAction, ...]
    expected_floating: dict[str, bool]
    extra: dict[str, Any]


@dataclass(frozen=True, slots=True)
class WindowTarget:
    """Целевое состояние окна после сверки; `None` — это свойство не меняется."""

    floating: bool | None
    geometry: Geometry | None

    def to_json(self) -> dict[str, Any]:
        geometry = self.geometry
        return {
            "floating": self.floating,
            "at": None if geometry is None else list(geometry.at),
            "size": None if geometry is None else list(geometry.size),
        }


@dataclass(frozen=True, slots=True)
class WindowChange:
    """Действия, приводящие окно `address` к `target`."""

    address: str
    actions: tuple[HyprAction, ...]
    target: WindowTarget


@dataclass(frozen=True, slots=True)
class WorkspaceUpdate:
    """Сверка окон пространства: изменения окон и данные записи без отклонённых действий.

    В `extra` поле `pending` содержит только окна, отложенные и не затронутые этой сверкой.
    """

    workspace: WorkspaceRef
    changes: tuple[WindowChange, ...]
    extra: dict[str, Any]

    def extra_after(self, rejected: Iterable[str]) -> dict[str, Any]:
        """Данные записи после применения: цели отклонённых окон `rejected` уходят в `pending`."""
        rejected = set(rejected)
        pending = {**self.extra.get(PENDING, {})}
        pending.update({c.address: c.target.to_json() for c in self.changes if c.address in rejected})
        extra = {k: v for k, v in self.extra.items() if k != PENDING}
        if pending:
            extra[PENDING] = pending
        return extra


class LayoutPlanner:
    """Планы переходов «Окна ↔ Тайлы» и сверки окон пространств."""

    def reconcile(
        self,
        workspaces: Sequence[WorkspaceRef],
        snapshot: CompositorSnapshot,
        removed: Sequence[WorkspaceRef] = (),
    ) -> tuple[WorkspaceUpdate, ...]:
        """Сверка окон назначенных пространств, которые есть в снимке.

        `removed` — записи, удалённые из реестра этой же сверкой: их управляемые окна и
        диалоги по-прежнему считаются перенесёнными, а не новыми. Возвращает только
        пространства, где нужны действия или меняются данные записи. Пространство,
        монитор которого не найден в снимке, пропускается.
        """
        owners: dict[str, tuple[WorkspaceRef, str]] = {}
        for ref in (*workspaces, *removed):
            for role in (MANAGED, DIALOGS):
                for address in _addresses(ref.extra.get(role)):
                    owners.setdefault(address, (ref, role))
        present = {w.id for w in snapshot.workspaces}
        updates = []
        for ref in workspaces:
            if ref.workspace_id not in present:
                continue
            try:
                update = _reconcile_workspace(ref, snapshot, owners)
            except LayoutError:
                continue
            if update.changes or update.extra != ref.extra:
                updates.append(update)
        return tuple(updates)

    def to_tiles(self, workspace: WorkspaceRef, snapshot: CompositorSnapshot) -> TransitionPlan:
        """Переход в «Тайлы»: управляемые плавающие окна возвращаются в раскладку.

        Перед этим запоминается их геометрия; отложенные действия сверки (`pending`)
        отбрасываются. Если есть снимок колонок, окна встают в его
        порядке, затем каждому через фокус и `ResizeColumn` возвращается ширина его колонки;
        окна вне снимка встают следом, слева направо и сверху вниз по текущему положению.
        Известное ограничение: колонка из нескольких окон восстанавливается отдельными
        колонками в порядке её окон — действия объединения окон в колонку у движка нет.
        В конце фокус возвращается активному окну.
        """
        windows, managed, dialogs = _classify(workspace, snapshot)
        geometry = {a: g for a, g in _saved_geometry(workspace.extra).items() if a in managed}
        targets = [w for w in _movable(windows, managed) if w.floating]
        for window in targets:
            geometry[window.address] = Geometry(window.at, window.size)

        saved_columns = _saved_columns(workspace.extra)
        widths = {address: column.width for column in saved_columns for address in column.addresses}
        by_address = {w.address: w for w in targets}
        order = [a for column in saved_columns for a in column.addresses if a in by_address]
        order = list(dict.fromkeys(order))
        rest = sorted((w for w in targets if w.address not in order), key=lambda w: (w.at[0], w.at[1]))
        order.extend(w.address for w in rest)

        active = _active_address(snapshot)
        extra = {
            **workspace.extra,
            MANAGED: managed,
            DIALOGS: dialogs,
            GEOMETRY: {a: g.to_json() for a, g in geometry.items()},
        }
        extra.pop(PENDING, None)
        return TransitionPlan(
            mode="tiles",
            actions=_retile(order, widths, active),
            reverse=_refloat([by_address[a] for a in order], active),
            expected_floating={a: False for a in order},
            extra=extra,
        )

    def to_windows(self, workspace: WorkspaceRef, snapshot: CompositorSnapshot) -> TransitionPlan:
        """Переход в «Окна»: управляемые окна раскладки становятся плавающими.

        Перед этим запоминаются порядок и ширины их колонок; отложенные действия сверки
        (`pending`) отбрасываются. Окно получает сохранённую
        геометрию, ограниченную рабочей областью монитора пространства; без сохранённой —
        `DEFAULT_SIZE_FRACTION` рабочей области по центру. В конце фокус возвращается
        активному окну.
        """
        windows, managed, dialogs = _classify(workspace, snapshot)
        geometry = {a: g for a, g in _saved_geometry(workspace.extra).items() if a in managed}
        targets = [w for w in _movable(windows, managed) if not w.floating]
        by_address = {w.address: w for w in targets}

        columns: list[Column] = []
        actions: list[HyprAction] = []
        if targets:
            monitor = _workspace_monitor(snapshot, workspace.workspace_id)
            try:
                current = snapshot.columns(workspace.workspace_id)
            except ValueError as error:
                raise LayoutError(str(error)) from error
            for column in current:
                addresses = tuple(a for a in column.addresses if a in by_address)
                if addresses:
                    columns.append(Column(addresses, column.width))
            order = [a for column in columns for a in column.addresses]
            order.extend(w.address for w in targets if w.address not in order)
            for address in order:
                saved = geometry.get(address)
                placed = _clamp(saved, monitor) if saved is not None else _centered(monitor)
                actions += [
                    SetFloating(address, True),
                    MoveWindow(address, *placed.at),
                    ResizeWindow(address, *placed.size),
                ]
        else:
            order = []

        active = _active_address(snapshot)
        if actions and active is not None:
            actions.append(FocusWindow(active))
        widths = {address: column.width for column in columns for address in column.addresses}
        extra = {
            **workspace.extra,
            MANAGED: managed,
            DIALOGS: dialogs,
            GEOMETRY: {a: g.to_json() for a, g in geometry.items()},
            COLUMNS: [{"addresses": list(c.addresses), "width": c.width} for c in columns],
        }
        extra.pop(PENDING, None)
        return TransitionPlan(
            mode="windows",
            actions=tuple(actions),
            reverse=_retile(order, widths, active),
            expected_floating={a: True for a in order},
            extra=extra,
        )


def _classify(workspace: WorkspaceRef, snapshot: CompositorSnapshot) -> tuple[dict[str, Window], list[str], list[str]]:
    """Окна пространства и списки управляемых окон и диалогов без закрытых окон.

    Окно, которого нет ни в одном списке, впервые увидено сейчас: плавающее — диалог,
    иначе управляемое.
    """
    windows = {w.address: w for w in snapshot.windows if w.workspace_id == workspace.workspace_id}
    managed = [a for a in _addresses(workspace.extra.get(MANAGED)) if a in windows]
    dialogs = [a for a in _addresses(workspace.extra.get(DIALOGS)) if a in windows and a not in managed]
    for address, window in windows.items():
        if address not in managed and address not in dialogs:
            (dialogs if window.floating else managed).append(address)
    return windows, managed, dialogs


def _movable(windows: Mapping[str, Window], managed: Iterable[str]) -> list[Window]:
    """Управляемые окна, которые переход может менять: видимые, не закреплённые, не полноэкранные."""
    result = []
    for address in managed:
        window = windows[address]
        if window.mapped and not window.hidden and not window.pinned and window.fullscreen == 0:
            result.append(window)
    return result


def _addresses(value: object) -> list[str]:
    """Уникальные адреса из сохранённого списка; остальное отбрасывается."""
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(a for a in value if isinstance(a, str)))


def _pair(value: object) -> tuple[int, int] | None:
    if isinstance(value, list) and len(value) == 2 and all(type(v) is int for v in value):
        return (value[0], value[1])
    return None


def _saved_geometry(extra: Mapping[str, Any]) -> dict[str, Geometry]:
    """Сохранённая геометрия окон; повреждённые записи пропускаются."""
    value = extra.get(GEOMETRY)
    if not isinstance(value, dict):
        return {}
    result = {}
    for address, item in value.items():
        if not isinstance(address, str) or not isinstance(item, dict):
            continue
        at, size = _pair(item.get("at")), _pair(item.get("size"))
        if at is not None and size is not None and size[0] > 0 and size[1] > 0:
            result[address] = Geometry(at, size)
    return result


def _saved_columns(extra: Mapping[str, Any]) -> list[Column]:
    """Сохранённые колонки; ширина приводится к `(0, 1]`, повреждённые записи пропускаются."""
    value = extra.get(COLUMNS)
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if not isinstance(item, dict):
            continue
        width = item.get("width")
        addresses = _addresses(item.get("addresses"))
        if type(width) not in (int, float) or not 0 < width or not addresses:
            continue
        result.append(Column(tuple(addresses), min(float(width), 1.0)))
    return result


def _active_address(snapshot: CompositorSnapshot) -> str | None:
    """Адрес активного окна, если оно есть среди окон снимка."""
    active = snapshot.active_window
    if active is None or all(w.address != active.address for w in snapshot.windows):
        return None
    return active.address


def _retile(order: list[str], widths: Mapping[str, float], active: str | None) -> tuple[HyprAction, ...]:
    """Вернуть окна в раскладку по порядку, затем задать ширины колонок и вернуть фокус."""
    actions: list[HyprAction] = [SetFloating(address, False) for address in order]
    for address in order:
        if address in widths:
            actions += [FocusWindow(address), ResizeColumn(float(widths[address]))]
    if actions and active is not None:
        actions.append(FocusWindow(active))
    return tuple(actions)


def _refloat(windows: list[Window], active: str | None) -> tuple[HyprAction, ...]:
    """Сделать окна плавающими в прежней геометрии и вернуть фокус."""
    actions: list[HyprAction] = []
    for window in windows:
        actions += [
            SetFloating(window.address, True),
            MoveWindow(window.address, *window.at),
            ResizeWindow(window.address, *window.size),
        ]
    if actions and active is not None:
        actions.append(FocusWindow(active))
    return tuple(actions)


def _reconcile_workspace(
    ref: WorkspaceRef, snapshot: CompositorSnapshot, owners: Mapping[str, tuple[WorkspaceRef, str]]
) -> WorkspaceUpdate:
    """Сверка окон одного пространства.

    Окно, которого нет в списках пространства, распределяется, когда оно видимо и не в
    полноэкранном режиме. Управляемое окно другого пространства остаётся управляемым,
    получает свою сохранённую геометрию, сдвинутую в рабочую область этого и ограниченную
    ею, и подчиняется режиму этого пространства: в «Окнах» тайловое становится плавающим
    в этой геометрии или по центру, плавающее ограничивается рабочей областью; в «Тайлах»
    плавающее возвращается в раскладку, а его геометрия сохраняется. Диалог другого
    пространства остаётся диалогом. Новое плавающее окно — диалог; новое тайловое —
    управляемое и подчиняется режиму так же.

    Если рабочая область монитора показа отличается от `work_area`, сохранённая геометрия
    и цели `pending` сдвигаются на разницу начал областей и ограничиваются новой
    областью; в «Окнах» так же ставятся плавающие управляемые окна (окно, уже стоящее
    вне прежней области, только ограничивается).

    Окно из `pending` приводится к своей цели. Остальные управляемые окна не меняются:
    ручное переключение плавающего состояния сохраняется. Действия получают только окна,
    которые можно менять (см. `_movable`). Окна, которых больше нет на пространстве,
    убираются из данных записи.
    """
    monitor = _workspace_monitor(snapshot, ref.workspace_id)
    area = _work_area(monitor)
    windows = {w.address: w for w in snapshot.windows if w.workspace_id == ref.workspace_id}
    managed = [a for a in _addresses(ref.extra.get(MANAGED)) if a in windows]
    dialogs = [a for a in _addresses(ref.extra.get(DIALOGS)) if a in windows and a not in managed]
    geometry = {a: g for a, g in _saved_geometry(ref.extra).items() if a in managed}
    pending = {a: t for a, t in _saved_targets(ref.extra).items() if a in managed}

    previous = _saved_area(ref.extra)
    area_changed = previous is not None and previous != area
    if area_changed:
        geometry = {a: _clamp(_translate(g, previous, area), monitor) for a, g in geometry.items()}
        pending = {
            a: t if t.geometry is None else WindowTarget(t.floating, _clamp(_translate(t.geometry, previous, area), monitor))
            for a, t in pending.items()
        }

    arrived: list[str] = []
    for address, window in windows.items():
        if address in managed or address in dialogs:
            continue
        if not window.mapped or window.hidden or window.fullscreen != 0:
            continue
        owner = owners.get(address)
        if (owner is not None and owner[1] == DIALOGS) or (owner is None and window.floating):
            dialogs.append(address)
            continue
        managed.append(address)
        arrived.append(address)
        source = _saved_geometry(owner[0].extra).get(address) if owner is not None else None
        if source is not None:
            source_area = _saved_area(owner[0].extra)
            if source_area is not None:
                source = _translate(source, source_area, area)
            geometry[address] = _clamp(source, monitor)

    changes: list[WindowChange] = []
    for window in _movable(windows, managed):
        address = window.address
        current = Geometry(window.at, window.size)
        target = pending.pop(address, None)
        if target is None and address in arrived:
            if ref.mode == "windows":
                saved = geometry.get(address)
                placed = saved if saved is not None else _centered(monitor)
                target = WindowTarget(True, _clamp(current, monitor) if window.floating else placed)
            else:
                if window.floating:
                    geometry[address] = current
                target = WindowTarget(False, None)
        elif target is None and area_changed and ref.mode == "windows" and window.floating:
            moved = _translate(current, previous, area) if _inside(window.at, previous) else current
            target = WindowTarget(None, _clamp(moved, monitor))
        if target is None:
            continue
        actions = _target_actions(address, target, window)
        if actions:
            changes.append(WindowChange(address, actions, target))

    extra = {
        **ref.extra,
        MANAGED: managed,
        DIALOGS: dialogs,
        GEOMETRY: {a: g.to_json() for a, g in geometry.items()},
        WORK_AREA: list(area),
    }
    extra.pop(PENDING, None)
    if pending:
        extra[PENDING] = {a: t.to_json() for a, t in pending.items()}
    if COLUMNS in ref.extra:
        extra[COLUMNS] = [
            {"addresses": kept, "width": c.width}
            for c in _saved_columns(ref.extra)
            if (kept := [a for a in c.addresses if a in managed])
        ]
    return WorkspaceUpdate(ref, tuple(changes), extra)


def _target_actions(address: str, target: WindowTarget, window: Window) -> tuple[HyprAction, ...]:
    """Действия, которых не хватает окну до цели; пусто, если окно уже в ней."""
    actions: list[HyprAction] = []
    if target.floating is not None and window.floating != target.floating:
        actions.append(SetFloating(address, target.floating))
    if target.geometry is not None and target.floating is not False:
        if actions or Geometry(window.at, window.size) != target.geometry:
            actions += _place(address, target.geometry)
    return tuple(actions)


def _saved_targets(extra: Mapping[str, Any]) -> dict[str, WindowTarget]:
    """Цели `pending`; повреждённые записи пропускаются."""
    value = extra.get(PENDING)
    if not isinstance(value, dict):
        return {}
    result = {}
    for address, item in value.items():
        if not isinstance(address, str) or not isinstance(item, dict):
            continue
        floating = item.get("floating")
        if floating is not None and type(floating) is not bool:
            continue
        at, size = _pair(item.get("at")), _pair(item.get("size"))
        geometry = Geometry(at, size) if at is not None and size is not None and size[0] > 0 and size[1] > 0 else None
        if floating is None and geometry is None:
            continue
        result[address] = WindowTarget(floating, geometry)
    return result


def _saved_area(extra: Mapping[str, Any]) -> tuple[int, int, int, int] | None:
    """Сохранённая рабочая область; повреждённая запись — `None`."""
    value = extra.get(WORK_AREA)
    if isinstance(value, list) and len(value) == 4 and all(type(v) is int for v in value):
        x, y, width, height = value
        if width > 0 and height > 0:
            return (x, y, width, height)
    return None


def _inside(point: tuple[int, int], area: tuple[int, int, int, int]) -> bool:
    x0, y0, width, height = area
    return x0 <= point[0] < x0 + width and y0 <= point[1] < y0 + height


def _translate(geometry: Geometry, source: tuple[int, int, int, int], target: tuple[int, int, int, int]) -> Geometry:
    """Геометрия, сдвинутая на разницу начал рабочих областей `source` → `target`."""
    dx, dy = target[0] - source[0], target[1] - source[1]
    return Geometry((geometry.at[0] + dx, geometry.at[1] + dy), geometry.size)


def _place(address: str, geometry: Geometry) -> tuple[HyprAction, ...]:
    return (MoveWindow(address, *geometry.at), ResizeWindow(address, *geometry.size))


def _workspace_monitor(snapshot: CompositorSnapshot, workspace_id: int) -> Monitor:
    workspace = next((w for w in snapshot.workspaces if w.id == workspace_id), None)
    if workspace is None:
        raise LayoutError(f"workspace {workspace_id} is missing from the compositor snapshot")
    monitor = next((m for m in snapshot.monitors if m.id == workspace.monitor_id), None)
    if monitor is None:
        raise LayoutError(f"monitor of workspace {workspace_id} is missing from the compositor snapshot")
    return monitor


def _work_area(monitor: Monitor) -> tuple[int, int, int, int]:
    """Рабочая область монитора в логических координатах: x, y, ширина, высота."""
    try:
        width, height = int(monitor.work_area_width), int(monitor.work_area_height)
    except ValueError as error:
        raise LayoutError(str(error)) from error
    return monitor.x + monitor.reserved[0], monitor.y + monitor.reserved[1], width, height


def _clamp(geometry: Geometry, monitor: Monitor) -> Geometry:
    """Геометрия внутри рабочей области.

    Окно, которое помещается, сдвигается внутрь целиком; размер больше области
    ограничивается ею, и окно встаёт в её начало по этой оси.
    """
    x0, y0, width, height = _work_area(monitor)
    w, h = min(geometry.size[0], width), min(geometry.size[1], height)
    x = min(max(geometry.at[0], x0), x0 + width - w)
    y = min(max(geometry.at[1], y0), y0 + height - h)
    return Geometry((x, y), (w, h))


def _centered(monitor: Monitor) -> Geometry:
    """`DEFAULT_SIZE_FRACTION` рабочей области по центру."""
    x0, y0, width, height = _work_area(monitor)
    w, h = round(width * DEFAULT_SIZE_FRACTION), round(height * DEFAULT_SIZE_FRACTION)
    return Geometry((x0 + (width - w) // 2, y0 + (height - h) // 2), (w, h))
