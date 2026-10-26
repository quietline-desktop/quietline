"""Локальные пространства мониторов: ключи мониторов, выделение ID и состояние сеанса."""

import copy
import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
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


class InvalidWorkspaceNumber(WorkspaceError):
    """Номер локального пространства не целое число от 1 до 10."""


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
            extra={k: v for k, v in data.items() if k not in _KNOWN_FIELDS},
        )


def _checked_int(value: object) -> int:
    if type(value) is not int:
        raise ValueError(f"expected an integer, got {value!r}")
    return value


def _checked_number(value: object) -> int:
    if type(value) is not int or not MIN_NUMBER <= value <= MAX_NUMBER:
        raise InvalidWorkspaceNumber(f"workspace number must be an integer from {MIN_NUMBER} to {MAX_NUMBER}, got {value!r}")
    return value


_KNOWN_FIELDS = frozenset({"monitor_key", "display_monitor_key", "number", "workspace_id", "mode"})


type MonitorIdentity = tuple[str, str, str, str]


def _identity(monitor: Monitor) -> MonitorIdentity:
    """Монитор на разъёме: производитель, модель, серийный номер и имя разъёма; без номера — только разъём."""
    if monitor.serial:
        return (monitor.make, monitor.model, monitor.serial, monitor.name)
    return ("", "", "", monitor.name)


def _base_key(monitor: Monitor) -> str:
    if monitor.serial:
        return f"{monitor.make}|{monitor.model}|{monitor.serial}"
    return f"connector:{monitor.name}"


def _derive_keys(
    monitors: tuple[Monitor, ...], assigned: Mapping[MonitorIdentity, str]
) -> tuple[dict[str, str], dict[MonitorIdentity, str]]:
    """Ключи мониторов: имя разъёма → ключ и обновлённые назначения `identity → key`.

    Монитор с тем же производителем, моделью, серийным номером и разъёмом сохраняет ключ.
    Монитор с известным серийным номером на другом разъёме забирает ключ записи, чей
    разъём больше не занят монитором с этим номером. Остальные получают ключ из
    производителя, модели и серийного номера (без номера — из имени разъёма); к ключу
    добавляется имя разъёма, если тот же ключ уже назначен другому монитору или
    повторяется среди новых.
    """
    result = dict(assigned)
    keys: dict[str, str] = {}
    unmatched: list[Monitor] = []
    for monitor in monitors:
        key = assigned.get(_identity(monitor))
        if key is None:
            unmatched.append(monitor)
        else:
            keys[monitor.name] = key
    connected = {_identity(m) for m in monitors}

    fresh: list[Monitor] = []
    for monitor in unmatched:
        identity = _identity(monitor)
        previous = None
        if monitor.serial:
            previous = next((i for i in result if i[:3] == identity[:3] and i not in connected), None)
        if previous is None:
            fresh.append(monitor)
        else:
            keys[monitor.name] = result[identity] = result.pop(previous)

    taken = set(result.values())
    counts: dict[str, int] = {}
    for monitor in fresh:
        counts[_base_key(monitor)] = counts.get(_base_key(monitor), 0) + 1
    for monitor in fresh:
        base = _base_key(monitor)
        key = base if counts[base] == 1 and base not in taken else f"{base}|{monitor.name}"
        keys[monitor.name] = result[_identity(monitor)] = key
    return keys, result


def monitor_keys(snapshot: CompositorSnapshot) -> dict[str, str]:
    """Ключи мониторов одного снимка без учёта истории сеанса: имя разъёма → ключ.

    Ключ строится из производителя, модели и непустого серийного номера. Без номера
    ключ строится из имени разъёма. Если номер повторяется у нескольких мониторов,
    к ключу добавляется имя разъёма. Устойчивые в течение сеанса ключи выдаёт
    `WorkspaceRegistry.monitor_keys`.
    """
    return _derive_keys(snapshot.monitors, {})[0]


def focused_monitor(snapshot: CompositorSnapshot, keys: Mapping[str, str] | None = None) -> str:
    """Ключ монитора с фокусом; `keys` — ключи реестра (имя разъёма → ключ), иначе ключи снимка.

    Монитор активного окна; без активного окна — монитор под указателем
    (геометрия в логических координатах: `width / scale`, `height / scale`).
    Указатель вне мониторов — монитор с флагом `focused`, иначе первый.
    """
    if not snapshot.monitors:
        raise WorkspaceError("no monitors in the compositor snapshot")
    keys = monitor_keys(snapshot) if keys is None else keys
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

    Ключ монитора, однажды назначенный физическому монитору, не меняется до конца сеанса,
    даже если монитор отключён или рядом появился такой же. Состояние лежит в одном
    JSON-файле, привязанном к `HYPRLAND_INSTANCE_SIGNATURE`: файл другого сеанса
    не читается и перезаписывается при первом сохранении.
    """

    def __init__(self, state_path: Path, instance_signature: str) -> None:
        self._path = state_path
        self._signature = instance_signature
        self._identities: dict[MonitorIdentity, str] = {}
        self._refs: dict[tuple[str, int], WorkspaceRef] = {}
        self._load()

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

    def workspaces(self) -> tuple[WorkspaceRef, ...]:
        """Все назначенные пространства по ключу монитора и номеру."""
        return tuple(ref for _, ref in sorted(self._refs.items()))

    def update(
        self, ref: WorkspaceRef, *, mode: Mode | None = None, extra: Mapping[str, Any] | None = None
    ) -> WorkspaceRef:
        """Заменяет режим и (или) дополнительные данные записи и атомарно сохраняет файл.

        `ref` должен совпадать с назначенной записью по монитору, номеру и ID. `extra`
        заменяет данные целиком (копируется) и не может содержать имена основных полей.
        Ошибка проверки или записи оставляет реестр и файл без изменений.
        """
        key = (ref.monitor_key, ref.number)
        current = self._refs.get(key)
        if current is None or current.workspace_id != ref.workspace_id:
            raise WorkspaceError(f"workspace {ref.number} of monitor {ref.monitor_key!r} is not assigned")
        if mode is not None and mode not in ("windows", "tiles"):
            raise ValueError(f"unknown mode {mode!r}")
        if extra is not None and not _KNOWN_FIELDS.isdisjoint(extra):
            raise ValueError(f"extra data must not override record fields: {sorted(_KNOWN_FIELDS & set(extra))}")
        updated = replace(
            current,
            mode=current.mode if mode is None else mode,
            extra=current.extra if extra is None else copy.deepcopy(dict(extra)),
        )
        self._refs[key] = updated
        try:
            self._save()
        except BaseException:
            self._refs[key] = current
            raise
        return updated

    def monitor_keys(self, snapshot: CompositorSnapshot) -> dict[str, str]:
        """Устойчивые ключи мониторов снимка: имя разъёма → ключ; новые назначения сохраняются."""
        keys, identities = _derive_keys(snapshot.monitors, self._identities)
        if identities != self._identities:
            self._identities = identities
            self._save()
        return keys

    def focused_monitor(self, snapshot: CompositorSnapshot) -> str:
        """Ключ монитора с фокусом (см. `focused_monitor`) среди устойчивых ключей реестра."""
        return focused_monitor(snapshot, self.monitor_keys(snapshot))

    def resolve(self, number: int, monitor_key: str, snapshot: CompositorSnapshot) -> WorkspaceRef:
        """Пространство `number` монитора `monitor_key`; новое получает ID из `1001+`.

        Номер вне `1`–`10` отвергается без изменения состояния. Перед выделением нового ID
        активные пространства подключённых мониторов, у которых ещё нет локального `1`,
        принимаются как их локальные `1`.
        """
        _checked_number(number)
        keys = self.monitor_keys(snapshot)
        if monitor_key not in keys.values() and monitor_key not in self._identities.values():
            raise WorkspaceError(f"unknown monitor {monitor_key!r}")
        changed = self._adopt_active_workspaces(snapshot, keys)
        ref = self._refs.get((monitor_key, number))
        if ref is None:
            ref = WorkspaceRef(monitor_key, monitor_key, number, self._allocate_id(snapshot))
            self._refs[(monitor_key, number)] = ref
            changed = True
        if changed:
            self._save()
        return ref

    def reconcile(self, snapshot: CompositorSnapshot) -> list[HyprAction]:
        """Сверяет реестр со снимком и возвращает действия, не выполняя их.

        Активные пространства подключённых мониторов принимаются как локальные `1`.
        Пространство, показанное не на том мониторе, куда оно назначено, возвращается
        действием `MoveWorkspaceToMonitor`; пространства отключённых мониторов не трогаются.
        """
        keys = self.monitor_keys(snapshot)
        if self._adopt_active_workspaces(snapshot, keys):
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

    def _adopt_active_workspaces(self, snapshot: CompositorSnapshot, keys: Mapping[str, str]) -> bool:
        """Активное пространство монитора как его локальное `1`, если `1` не назначено, а ID свободен.

        Возвращает `True`, если реестр изменился.
        """
        changed = False
        for monitor in snapshot.monitors:
            key = keys[monitor.name]
            workspace_id = monitor.active_workspace_id
            if (key, 1) in self._refs or workspace_id <= 0 or workspace_id in self._assigned_ids():
                continue
            self._refs[(key, 1)] = WorkspaceRef(key, key, 1, workspace_id)
            changed = True
        return changed

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

    def _load(self) -> None:
        """Читает файл своего сеанса; чужой, повреждённый или отсутствующий файл оставляет реестр пустым."""
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if data["version"] != STATE_VERSION or data["signature"] != self._signature:
                return
            refs = [WorkspaceRef.from_json(item) for item in data["workspaces"]]
            identities = {
                (str(m["make"]), str(m["model"]), str(m["serial"]), str(m["connector"])): str(m["key"])
                for m in data.get("monitors", [])
            }
        except (OSError, ValueError, KeyError, TypeError, AttributeError, WorkspaceError):
            return
        self._refs = {(ref.monitor_key, ref.number): ref for ref in refs}
        self._identities = identities

    def _save(self) -> None:
        """Атомарная запись: временный файл в том же каталоге и `os.replace`."""
        directory = self._path.parent
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(directory, 0o700)
        payload = {
            "version": STATE_VERSION,
            "signature": self._signature,
            "monitors": [
                {"make": make, "model": model, "serial": serial, "connector": connector, "key": key}
                for (make, model, serial, connector), key in self._identities.items()
            ],
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
