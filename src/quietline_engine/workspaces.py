"""Локальные пространства мониторов: ключи мониторов, выделение ID и состояние сеанса."""

import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from quietline_engine.types import CompositorSnapshot, HyprAction, Monitor, MoveWorkspaceToMonitor

type Mode = Literal["windows", "tiles"]

MIN_NUMBER = 1
MAX_NUMBER = 10
# Первый ID, из которого выделяются новые пространства.
FIRST_ALLOCATED_ID = 1001
STATE_VERSION = 1


class WorkspaceError(Exception):
    """Недопустимый запрос к реестру пространств или неполное окружение."""


@dataclass(frozen=True, slots=True)
class WorkspaceRef:
    """Локальное пространство монитора.

    `workspace_id` не меняется до конца сеанса; `display_monitor_key` — монитор,
    на котором пространство показано сейчас. `extra` хранит дополнительные поля записи
    из файла состояния: при загрузке они сохраняются, при записи возвращаются в файл.
    """

    monitor_key: str
    display_monitor_key: str
    number: int
    workspace_id: int
    mode: Mode = "windows"
    extra: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        """Запись для файла состояния: известные поля и `extra` на одном уровне."""
        return {
            **self.extra,
            "monitor_key": self.monitor_key,
            "display_monitor_key": self.display_monitor_key,
            "number": self.number,
            "workspace_id": self.workspace_id,
            "mode": self.mode,
        }

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "WorkspaceRef":
        """Запись из файла состояния; неизвестные поля уходят в `extra`."""
        known = {"monitor_key", "display_monitor_key", "number", "workspace_id", "mode"}
        monitor_key = data["monitor_key"]
        mode = data.get("mode", "windows")
        if mode not in ("windows", "tiles"):
            raise ValueError(f"unknown mode {mode!r}")
        return cls(
            monitor_key=str(monitor_key),
            display_monitor_key=str(data.get("display_monitor_key", monitor_key)),
            number=_checked_number(data["number"]),
            workspace_id=_checked_int(data["workspace_id"]),
            mode=mode,
            extra={k: v for k, v in data.items() if k not in known},
        )


def _checked_int(value: object) -> int:
    if type(value) is not int:
        raise ValueError(f"expected an integer, got {value!r}")
    return value


def _checked_number(value: object) -> int:
    if type(value) is not int or not MIN_NUMBER <= value <= MAX_NUMBER:
        raise WorkspaceError(f"workspace number must be an integer from {MIN_NUMBER} to {MAX_NUMBER}, got {value!r}")
    return value


def monitor_keys(snapshot: CompositorSnapshot) -> dict[str, str]:
    """Ключи мониторов снимка: имя разъёма → ключ.

    Ключ строится из производителя, модели и непустого серийного номера. Без номера
    ключ строится из имени разъёма. Если номер повторяется у нескольких мониторов,
    к ключу добавляется имя разъёма.
    """
    bases = {m.name: _base_key(m) for m in snapshot.monitors}
    counts: dict[str, int] = {}
    for base in bases.values():
        counts[base] = counts.get(base, 0) + 1
    return {name: base if counts[base] == 1 else f"{base}|{name}" for name, base in bases.items()}


def _base_key(monitor: Monitor) -> str:
    if monitor.serial:
        return f"{monitor.make}|{monitor.model}|{monitor.serial}"
    return f"connector:{monitor.name}"


def focused_monitor(snapshot: CompositorSnapshot) -> str:
    """Ключ монитора с фокусом.

    Монитор активного окна; без активного окна — монитор под указателем
    (геометрия в логических координатах: `width / scale`, `height / scale`).
    Указатель вне мониторов — монитор с флагом `focused`, иначе первый.
    """
    if not snapshot.monitors:
        raise WorkspaceError("no monitors in the compositor snapshot")
    keys = monitor_keys(snapshot)
    target = None
    if snapshot.active_window is not None:
        target = next((m for m in snapshot.monitors if m.id == snapshot.active_window.monitor_id), None)
    if target is None:
        px, py = snapshot.cursor_position
        target = next(
            (
                m
                for m in snapshot.monitors
                if m.x <= px < m.x + m.width / m.scale and m.y <= py < m.y + m.height / m.scale
            ),
            None,
        )
    if target is None:
        target = next((m for m in snapshot.monitors if m.focused), snapshot.monitors[0])
    return keys[target.name]


class WorkspaceRegistry:
    """Соответствие `(monitor_key, number) → workspace_id` в рамках сеанса Hyprland.

    Состояние лежит в одном JSON-файле, привязанном к `HYPRLAND_INSTANCE_SIGNATURE`:
    файл другого сеанса не читается и перезаписывается при первом сохранении.
    """

    def __init__(self, state_path: Path, instance_signature: str) -> None:
        self._path = state_path
        self._signature = instance_signature
        self._refs: dict[tuple[str, int], WorkspaceRef] = self._load()

    @classmethod
    def from_environment(cls, env: Mapping[str, str] | None = None) -> "WorkspaceRegistry":
        """Реестр с файлом `$XDG_RUNTIME_DIR/quietline/state.json` для текущего сеанса."""
        env = os.environ if env is None else env
        runtime_dir = env.get("XDG_RUNTIME_DIR")
        if not runtime_dir:
            raise WorkspaceError("XDG_RUNTIME_DIR is not set")
        signature = env.get("HYPRLAND_INSTANCE_SIGNATURE")
        if not signature:
            raise WorkspaceError("HYPRLAND_INSTANCE_SIGNATURE is not set")
        return cls(Path(runtime_dir) / "quietline" / "state.json", signature)

    def get(self, monitor_key: str, number: int) -> WorkspaceRef | None:
        """Назначенное пространство или `None`."""
        return self._refs.get((monitor_key, number))

    def resolve(self, number: int, monitor_key: str, snapshot: CompositorSnapshot) -> WorkspaceRef:
        """Пространство `number` монитора `monitor_key`; новое получает ID из `1001+`.

        Номер вне `1`–`10` отвергается без изменения состояния. Активное пространство
        монитора, ещё не назначенное другому, принимается как его локальное `1`.
        """
        _checked_number(number)
        keys = monitor_keys(snapshot)
        if monitor_key not in keys.values() and not any(k == monitor_key for k, _ in self._refs):
            raise WorkspaceError(f"unknown monitor {monitor_key!r}")
        existing = self._refs.get((monitor_key, number))
        if existing is not None:
            return existing
        ref = self._adopt_active(monitor_key, snapshot, keys) if number == 1 else None
        if ref is None:
            ref = WorkspaceRef(monitor_key, monitor_key, number, self._allocate_id(snapshot))
        self._refs[(monitor_key, number)] = ref
        self._save()
        return ref

    def reconcile(self, snapshot: CompositorSnapshot) -> list[HyprAction]:
        """Сверяет реестр со снимком и возвращает действия, не выполняя их.

        Активные пространства подключённых мониторов принимаются как локальные `1`.
        Пространство, показанное не на том мониторе, куда оно назначено, возвращается
        действием `MoveWorkspaceToMonitor`; пространства отключённых мониторов не трогаются.
        """
        keys = monitor_keys(snapshot)
        changed = False
        for key in keys.values():
            if (key, 1) not in self._refs:
                ref = self._adopt_active(key, snapshot, keys)
                if ref is not None:
                    self._refs[(key, 1)] = ref
                    changed = True
        if changed:
            self._save()

        connector_by_key = {key: name for name, key in keys.items()}
        shown_on = {w.id: w.monitor for w in snapshot.workspaces}
        actions: list[HyprAction] = []
        for ref in self._refs.values():
            target = connector_by_key.get(ref.display_monitor_key)
            current = shown_on.get(ref.workspace_id)
            if target is not None and current is not None and current != target:
                actions.append(MoveWorkspaceToMonitor(workspace_id=ref.workspace_id, monitor=target))
        return actions

    def _adopt_active(self, monitor_key: str, snapshot: CompositorSnapshot, keys: dict[str, str]) -> WorkspaceRef | None:
        """Активное пространство монитора как его локальное `1`, если оно свободно."""
        monitor = next((m for m in snapshot.monitors if keys[m.name] == monitor_key), None)
        if monitor is None or monitor.active_workspace_id <= 0:
            return None
        if monitor.active_workspace_id in self._assigned_ids():
            return None
        return WorkspaceRef(monitor_key, monitor_key, 1, monitor.active_workspace_id)

    def _assigned_ids(self) -> set[int]:
        return {ref.workspace_id for ref in self._refs.values()}

    def _allocate_id(self, snapshot: CompositorSnapshot) -> int:
        """Наименьший ID от `1001`, не встречающийся в снимке и реестре."""
        used = self._assigned_ids()
        used.update(w.id for w in snapshot.workspaces)
        used.update(m.active_workspace_id for m in snapshot.monitors)
        used.update(w.workspace_id for w in snapshot.windows)
        candidate = FIRST_ALLOCATED_ID
        while candidate in used:
            candidate += 1
        return candidate

    def _load(self) -> dict[tuple[str, int], WorkspaceRef]:
        """Записи файла своего сеанса; чужой, повреждённый или отсутствующий файл даёт пустой реестр."""
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if data["version"] != STATE_VERSION or data["signature"] != self._signature:
                return {}
            refs = [WorkspaceRef.from_json(item) for item in data["workspaces"]]
        except (OSError, ValueError, KeyError, TypeError, AttributeError, WorkspaceError):
            return {}
        return {(ref.monitor_key, ref.number): ref for ref in refs}

    def _save(self) -> None:
        """Атомарная запись: временный файл в том же каталоге и `os.replace`."""
        directory = self._path.parent
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(directory, 0o700)
        payload = {
            "version": STATE_VERSION,
            "signature": self._signature,
            "workspaces": [ref.to_json() for ref in self._refs.values()],
        }
        fd, temp_name = tempfile.mkstemp(dir=directory, prefix=".state-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, self._path)
        except BaseException:
            Path(temp_name).unlink(missing_ok=True)
            raise
