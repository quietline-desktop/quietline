"""Контроллер окон: последовательное выполнение команд и публикация подтверждённого состояния."""

import asyncio
from collections.abc import Coroutine, Sequence
from dataclasses import dataclass, replace
from typing import Any, Protocol

from quietline_engine.layout import LayoutError, LayoutPlanner, TransitionPlan
from quietline_engine.types import (
    CompositorSnapshot,
    FocusMonitor,
    FocusWorkspace,
    HyprAction,
    HyprEvent,
    MoveWindowToWorkspace,
    Window,
)
from quietline_engine.workspaces import Mode, WorkspaceError, WorkspaceRef, WorkspaceRegistry, check_number


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

    `revision` растёт на 1, когда мониторы или пространства отличаются от последнего
    опубликованного состояния; `error` — сообщение об ошибке последней команды.
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
    """Выполняет команды и сверки по одной под общей блокировкой.

    Адаптер синхронный и вызывается через `asyncio.to_thread`. Состояние публикуется
    только после того, как повторно прочитанный снимок Hyprland подтвердил результат.
    Перед каждой командой и сверкой реестр сверяется со снимком (см.
    `WorkspaceRegistry.reconcile`): активные пространства мониторов зарегистрированы,
    закрытые пустые удалены. Ошибки возвращаются в `PublicState.error`, а не исключением.
    """

    def __init__(self, adapter: Adapter, registry: WorkspaceRegistry, planner: LayoutPlanner | None = None) -> None:
        self._adapter = adapter
        self._registry = registry
        self._planner = planner or LayoutPlanner()
        self._lock = asyncio.Lock()
        self._revision = 0
        self._snapshot: CompositorSnapshot | None = None
        self._published: tuple[tuple[MonitorState, ...], tuple[WorkspaceState, ...]] | None = None
        self._current: PublicState | None = None

    def state(self) -> PublicState:
        """Последнее опубликованное состояние без `error`; до первого снимка — пустое."""
        return self._current or PublicState(self._revision, (), ())

    async def reconcile(self, event: HyprEvent) -> PublicState | None:
        """Сверяет движок с полным снимком Hyprland после события `event`.

        Событие — только сигнал: его содержимое не используется, поскольку очередь событий
        может пропустить промежуточное изменение. Порядок: сверка реестра; если вернулся
        монитор-владелец — перенос его пространств назад и повторное чтение снимка; сверка
        окон (см. `LayoutPlanner.reconcile`). Возвращает состояние с увеличенным `revision`,
        если мониторы или пространства изменились, иначе `None`; при ошибке — состояние
        с `error`. Выполняется до конца под блокировкой, как `toggle`.
        """
        async with self._lock:
            return await _run_to_completion(self._reconcile())

    async def switch(self, number: int, monitor_key: str | None = None) -> PublicState:
        """Открывает локальное пространство `number` монитора `monitor_key` (без него — монитора с фокусом).

        Номер вне `1`–`10` отвергается без обращения к Hyprland. Подключённый монитор
        получает фокус, затем пространство открывается на нём; новое пространство получает
        ID из `1001+` и режим «Окна». Пространство отключённого монитора открывается на
        мониторе фокуса, а несуществующее не создаётся. Результат подтверждается
        повторным снимком. Выполняется до конца под блокировкой, как `toggle`.
        """
        async with self._lock:
            return await _run_to_completion(self._switch(number, monitor_key))

    async def move(self, number: int) -> PublicState:
        """Переносит активное окно на локальное пространство `number` монитора с фокусом и переходит за ним.

        Номер вне `1`–`10` и отсутствие активного окна — ошибка без действий Hyprland.
        Перенесённое окно подчиняется режиму пространства назначения (см.
        `LayoutPlanner.reconcile`). Выполняется до конца под блокировкой, как `toggle`.
        """
        async with self._lock:
            return await _run_to_completion(self._move(number))

    async def toggle(self, monitor_key: str | None = None) -> PublicState:
        """Меняет режим активного пространства монитора `monitor_key` (без него — монитора с фокусом).

        Успех: план применён, новый снимок подтверждает состояние `floating` изменённых окон,
        режим и снимки раскладки сохранены, `revision` увеличен. Неудача (Hyprland отклонил
        действие, окно закрылось посреди перехода, снимок не совпал): обратный план
        применяется по одному действию, снимок перечитывается, режим остаётся прежним,
        `error` содержит причину. Неудачей считается любое исключение после начала
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
            self._sync(snapshot)
            ref = self._active_workspace(snapshot, monitor_key)
            plan = self._plan(ref, snapshot)
        except CommandError as error:
            return self._publish(str(error))
        try:
            await self._run(ref, plan)
        except Exception as error:
            message = f"mode switch failed: {_reason(error)}"
            if not await self._rollback(plan):
                message += "; rollback incomplete"
            return self._publish(message)
        return self._publish()

    async def _reconcile(self) -> PublicState | None:
        revision = self._revision
        known = self._registry.workspaces()
        try:
            snapshot = await self._read()
            moves = self._sync(snapshot)
            if moves:
                await self._apply(moves, "cannot return workspaces to their monitor")
                snapshot = await self._read()
                self._sync(snapshot)
            await self._converge(snapshot, known)
        except CommandError as error:
            return self._publish(str(error))
        state = self._publish()
        return state if state.revision != revision else None

    async def _switch(self, number: int, monitor_key: str | None) -> PublicState:
        try:
            check_number(number)
            snapshot = await self._read()
            self._sync(snapshot)
            keys = self._registry.monitor_keys(snapshot)
            key = self._registry.focused_monitor(snapshot) if monitor_key is None else monitor_key
            connector = next((name for name, k in keys.items() if k == key), None)
            if connector is None:
                ref = self._registry.get(key, number)
                if ref is None:
                    raise CommandError(f"workspace {number} of monitor {key!r} does not exist")
                actions: list[HyprAction] = [FocusWorkspace(ref.workspace_id)]
            else:
                ref = self._registry.resolve(number, key, snapshot)
                actions = [FocusMonitor(connector), FocusWorkspace(ref.workspace_id)]
        except Exception as error:
            return self._publish(_reason(error))
        try:
            await self._apply(actions, "workspace switch failed")
            snapshot = await self._read()
            self._sync(snapshot)
        except CommandError as error:
            return self._publish(str(error))
        shown = [m for m in snapshot.monitors if connector is None or m.name == connector]
        if all(m.active_workspace_id != ref.workspace_id for m in shown):
            return self._publish(f"workspace {number} did not open")
        return self._publish()

    async def _move(self, number: int) -> PublicState:
        known = self._registry.workspaces()
        try:
            check_number(number)
            snapshot = await self._read()
            self._sync(snapshot)
            window = _active_window(snapshot)
            if window is None:
                raise CommandError("no active window to move")
            ref = self._registry.resolve(number, self._registry.focused_monitor(snapshot), snapshot)
        except Exception as error:
            return self._publish(_reason(error))
        if window.workspace_id == ref.workspace_id:
            return self._publish()
        try:
            await self._apply(
                [MoveWindowToWorkspace(window.address, ref.workspace_id, follow=True)], "window move failed"
            )
            snapshot = await self._read()
            self._sync(snapshot)
            moved = next((w for w in snapshot.windows if w.address == window.address), None)
            if moved is None or moved.workspace_id != ref.workspace_id:
                raise CommandError(f"window {window.address} did not move to workspace {number}")
            await self._converge(snapshot, known)
        except CommandError as error:
            return self._publish(str(error))
        return self._publish()

    async def _read(self) -> CompositorSnapshot:
        """Снимок Hyprland; первый прочитанный снимок задаёт исходное опубликованное состояние."""
        try:
            snapshot = await asyncio.to_thread(self._adapter.snapshot)
        except Exception as error:
            raise CommandError(f"cannot read compositor state: {error}") from error
        self._snapshot = snapshot
        if self._published is None:
            state = self._state()
            self._published = (state.monitors, state.workspaces)
            self._current = state
        return snapshot

    def _sync(self, snapshot: CompositorSnapshot) -> list[HyprAction]:
        """Сверка реестра со снимком; возвращает переносы пространств к вернувшимся мониторам."""
        try:
            return self._registry.reconcile(snapshot)
        except Exception as error:
            raise CommandError(f"cannot update workspaces: {_reason(error)}") from error

    async def _apply(self, actions: Sequence[HyprAction], failure: str) -> None:
        """Применяет действия одним вызовом; при отказе перечитывает снимок и сообщает `failure`."""
        try:
            await asyncio.to_thread(self._adapter.apply, actions)
        except Exception as error:
            try:
                self._sync(await self._read())
            except CommandError:
                pass
            raise CommandError(f"{failure}: {_reason(error)}") from error

    async def _converge(self, snapshot: CompositorSnapshot, known: Sequence[WorkspaceRef]) -> None:
        """Сверка окон по снимку; `known` — записи реестра до сверки.

        Действия каждого окна применяются отдельным вызовом: отказ одного окна не мешает
        остальным и сообщается после всех. Данные записи пространства сохраняются после
        его действий; цель отклонённого окна попадает в `pending` и повторяется следующими
        сверками (см. `LayoutPlanner.reconcile`).
        """
        current = self._registry.workspaces()
        ids = {r.workspace_id for r in current}
        updates = self._planner.reconcile(current, snapshot, [r for r in known if r.workspace_id not in ids])
        failures = []
        for update in updates:
            rejected = []
            for change in update.changes:
                try:
                    await asyncio.to_thread(self._adapter.apply, change.actions)
                except Exception as error:
                    failures.append(_reason(error))
                    rejected.append(change.address)
            extra = update.extra_after(rejected)
            if extra != update.workspace.extra:
                try:
                    self._registry.update(update.workspace, extra=extra)
                except Exception as error:
                    raise CommandError(f"cannot save workspace state: {_reason(error)}") from error
        if failures:
            raise CommandError(f"window update failed: {'; '.join(failures)}")

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

    def _publish(self, error: str | None = None) -> PublicState:
        """Текущее состояние; `revision` растёт, если мониторы или пространства изменились с прошлой публикации."""
        state = self._state(error)
        content = (state.monitors, state.workspaces)
        if self._published is not None and content != self._published:
            self._revision += 1
            state = replace(state, revision=self._revision)
        self._published = content
        self._current = replace(state, error=None)
        return state

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


def _reason(error: BaseException) -> str:
    return str(error) or type(error).__name__


def _active_window(snapshot: CompositorSnapshot) -> Window | None:
    """Активное окно из списка окон снимка; `None`, если его нет."""
    active = snapshot.active_window
    if active is None:
        return None
    return next((w for w in snapshot.windows if w.address == active.address), None)


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
