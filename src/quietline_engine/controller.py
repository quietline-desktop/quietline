"""Контроллер окон: последовательное выполнение команд и публикация подтверждённого состояния."""

import asyncio
from collections.abc import Coroutine, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from quietline_engine.layout import LayoutError, LayoutPlanner, TransitionPlan
from quietline_engine.types import CompositorSnapshot, HyprAction
from quietline_engine.workspaces import Mode, WorkspaceError, WorkspaceRef, WorkspaceRegistry


class Adapter(Protocol):
    """Синхронный доступ к композитору (см. `Hyprland`)."""

    def snapshot(self) -> CompositorSnapshot: ...

    def apply(self, actions: Sequence[HyprAction]) -> None: ...


class CommandError(Exception):
    """Команда не выполнена; сообщение уходит клиенту в `PublicState.error`."""


@dataclass(frozen=True, slots=True)
class MonitorState:
    """Подключённый монитор: активное пространство и его режим (`None`, если пространство не движка)."""

    key: str
    name: str
    focused: bool
    active_workspace_id: int
    active_number: int | None
    mode: Mode | None


@dataclass(frozen=True, slots=True)
class WorkspaceState:
    """Назначенное локальное пространство и его режим."""

    monitor_key: str
    display_monitor_key: str
    number: int
    workspace_id: int
    mode: Mode


@dataclass(frozen=True, slots=True)
class PublicState:
    """Подтверждённое состояние для клиентов.

    `revision` растёт на 1 после каждого подтверждённого изменения; `error` —
    сообщение об ошибке последней команды, при ошибке состояние остаётся прежним.
    """

    revision: int
    monitors: tuple[MonitorState, ...]
    workspaces: tuple[WorkspaceState, ...]
    error: str | None = None

    def to_json(self) -> dict[str, Any]:
        """Простые данные JSON: словари, списки, строки, числа и `None`."""
        return {
            "revision": self.revision,
            "monitors": [
                {
                    "key": m.key,
                    "name": m.name,
                    "focused": m.focused,
                    "active_workspace_id": m.active_workspace_id,
                    "active_number": m.active_number,
                    "mode": m.mode,
                }
                for m in self.monitors
            ],
            "workspaces": [
                {
                    "monitor_key": w.monitor_key,
                    "display_monitor_key": w.display_monitor_key,
                    "number": w.number,
                    "workspace_id": w.workspace_id,
                    "mode": w.mode,
                }
                for w in self.workspaces
            ],
            "error": self.error,
        }


class WindowController:
    """Выполняет команды по одной под общей блокировкой.

    Адаптер синхронный и вызывается через `asyncio.to_thread`. Состояние публикуется
    только после того, как повторно прочитанный снимок Hyprland подтвердил результат.
    """

    def __init__(self, adapter: Adapter, registry: WorkspaceRegistry, planner: LayoutPlanner | None = None) -> None:
        self._adapter = adapter
        self._registry = registry
        self._planner = planner or LayoutPlanner()
        self._lock = asyncio.Lock()
        self._revision = 0
        self._snapshot: CompositorSnapshot | None = None

    async def toggle(self, monitor_key: str | None = None) -> PublicState:
        """Меняет режим активного пространства монитора `monitor_key` (без него — монитора с фокусом).

        Успех: план применён, новый снимок подтверждает состояние `floating` изменённых окон,
        режим и снимки раскладки сохранены, `revision` увеличен. Неудача (Hyprland отклонил
        действие, окно закрылось посреди перехода, снимок не совпал): обратный план
        применяется по одному действию, снимок перечитывается, режим и `revision` остаются
        прежними, `error` содержит причину. Неудачей считается любое исключение после начала
        применения плана; если часть обратных действий отклонена, `error` это сообщает.

        Переход выполняется до конца под блокировкой даже при отмене вызывающего:
        отменённый вызов дожидается подтверждения или отката и только потом получает
        `CancelledError`, поэтому действия разных команд не пересекаются.
        """
        async with self._lock:
            return await _run_to_completion(self._toggle(monitor_key))

    async def _toggle(self, monitor_key: str | None) -> PublicState:
        try:
            snapshot = await self._read()
            ref = self._active_workspace(snapshot, monitor_key)
            plan = self._plan(ref, snapshot)
        except CommandError as error:
            return self._state(str(error))
        try:
            await self._run(ref, plan)
        except Exception as error:
            message = f"mode switch failed: {str(error) or type(error).__name__}"
            if not await self._rollback(plan):
                message += "; rollback incomplete"
            return self._state(message)
        self._revision += 1
        return self._state()

    async def _read(self) -> CompositorSnapshot:
        try:
            snapshot = await asyncio.to_thread(self._adapter.snapshot)
        except Exception as error:
            raise CommandError(f"cannot read compositor state: {error}") from error
        self._snapshot = snapshot
        return snapshot

    def _active_workspace(self, snapshot: CompositorSnapshot, monitor_key: str | None) -> WorkspaceRef:
        """Запись активного пространства выбранного монитора."""
        try:
            keys = self._registry.monitor_keys(snapshot)
            key = self._registry.focused_monitor(snapshot) if monitor_key is None else monitor_key
        except WorkspaceError as error:
            raise CommandError(str(error)) from error
        connector = next((name for name, k in keys.items() if k == key), None)
        monitor = next((m for m in snapshot.monitors if m.name == connector), None)
        if monitor is None:
            raise CommandError(f"unknown monitor {key!r}")
        ref = self._ref_by_id(monitor.active_workspace_id)
        if ref is None:
            raise CommandError(f"active workspace {monitor.active_workspace_id} of monitor {key!r} is not managed")
        return ref

    def _plan(self, ref: WorkspaceRef, snapshot: CompositorSnapshot) -> TransitionPlan:
        try:
            if ref.mode == "windows":
                return self._planner.to_tiles(ref, snapshot)
            return self._planner.to_windows(ref, snapshot)
        except LayoutError as error:
            raise CommandError(f"mode switch failed: {error}") from error

    async def _run(self, ref: WorkspaceRef, plan: TransitionPlan) -> None:
        """Применяет план, проверяет новый снимок и сохраняет режим со снимками раскладки."""
        if plan.actions:
            await asyncio.to_thread(self._adapter.apply, plan.actions)
        snapshot = await self._read()
        windows = {w.address: w for w in snapshot.windows}
        for address, floating in plan.expected_floating.items():
            window = windows.get(address)
            if window is None:
                raise CommandError(f"window {address} closed during the switch")
            if window.floating != floating:
                state = "floating" if floating else "tiled"
                raise CommandError(f"window {address} did not become {state}")
        try:
            self._registry.update(ref, mode=plan.mode, extra=plan.extra)
        except Exception as error:
            raise CommandError(f"cannot save workspace state: {error}") from error

    async def _rollback(self, plan: TransitionPlan) -> bool:
        """Обратный план по одному действию, затем повторное чтение снимка.

        Отказ одного действия не мешает остальным. Возвращает `False`, если хотя бы одно
        действие отклонено.
        """
        complete = True
        for action in plan.reverse:
            try:
                await asyncio.to_thread(self._adapter.apply, [action])
            except Exception:
                complete = False
        try:
            await self._read()
        except CommandError:
            pass
        return complete

    def _ref_by_id(self, workspace_id: int) -> WorkspaceRef | None:
        return next((r for r in self._registry.workspaces() if r.workspace_id == workspace_id), None)

    def _state(self, error: str | None = None) -> PublicState:
        """Состояние по последнему прочитанному снимку и реестру."""
        refs = self._registry.workspaces()
        workspaces = tuple(
            WorkspaceState(r.monitor_key, r.display_monitor_key, r.number, r.workspace_id, r.mode) for r in refs
        )
        monitors: tuple[MonitorState, ...] = ()
        snapshot = self._snapshot
        if snapshot is not None and snapshot.monitors:
            keys = self._registry.monitor_keys(snapshot)
            focused = self._registry.focused_monitor(snapshot)
            by_id = {r.workspace_id: r for r in refs}
            monitors = tuple(
                MonitorState(
                    key=keys[m.name],
                    name=m.name,
                    focused=keys[m.name] == focused,
                    active_workspace_id=m.active_workspace_id,
                    active_number=by_id[m.active_workspace_id].number if m.active_workspace_id in by_id else None,
                    mode=by_id[m.active_workspace_id].mode if m.active_workspace_id in by_id else None,
                )
                for m in snapshot.monitors
            )
        return PublicState(self._revision, monitors, workspaces, error)


async def _run_to_completion[T](coroutine: Coroutine[Any, Any, T]) -> T:
    """Выполняет корутину отдельной задачей до конца.

    Отмена вызывающего не прерывает задачу: вызывающий дожидается её завершения
    и только затем получает `CancelledError`.
    """
    task = asyncio.create_task(coroutine)
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        while not task.done():
            try:
                await asyncio.wait({task})
            except asyncio.CancelledError:
                continue
        if not task.cancelled():
            task.exception()
        raise
