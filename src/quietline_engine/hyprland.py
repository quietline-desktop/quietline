"""Адаптер Hyprland: снимок через `hyprctl -j`, действия через `hyprctl eval`, события из `.socket2.sock`."""

import asyncio
import json
import math
import os
import re
import subprocess
from collections.abc import AsyncIterator, Callable, Mapping, Sequence

from quietline_engine.types import (
    CompositorSnapshot,
    FocusMonitor,
    FocusWindow,
    FocusWorkspace,
    HyprAction,
    HyprEvent,
    MoveWindow,
    MoveWindowToWorkspace,
    MoveWorkspaceToMonitor,
    Monitor,
    ResizeColumn,
    ResizeWindow,
    SetFloating,
    SwapColumn,
    Window,
    Workspace,
)

HYPRCTL_TIMEOUT_SECONDS = 5.0
EVENT_LINE_LIMIT = 1 << 20

# Запускает hyprctl по списку аргументов (первый — сам `hyprctl`) и возвращает stdout.
Runner = Callable[[Sequence[str]], str]


class HyprlandError(Exception):
    """Hyprland недоступен, отклонил действие или вернул неожиданный ответ."""


def run_hyprctl(argv: Sequence[str]) -> str:
    """Запускает команду без оболочки и с таймаутом; любой сбой — `HyprlandError`."""
    try:
        done = subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            timeout=HYPRCTL_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as error:
        raise HyprlandError(f"{argv[0]} not found") from error
    except subprocess.TimeoutExpired as error:
        raise HyprlandError(f"{' '.join(argv[:3])} timed out") from error
    if done.returncode != 0:
        detail = done.stderr.strip() or done.stdout.strip()
        raise HyprlandError(f"{' '.join(argv[:3])} failed with exit code {done.returncode}: {detail}")
    return done.stdout


_ADDRESS = re.compile(r"0x[0-9a-f]+")
_MONITOR_NAME = re.compile(r"[A-Za-z0-9-]+")


def _address(value: object) -> str:
    if not isinstance(value, str) or not _ADDRESS.fullmatch(value):
        raise HyprlandError(f"invalid window address: {value!r}")
    return value


def _integer(value: object, what: str) -> int:
    if type(value) is not int:
        raise HyprlandError(f"invalid {what}: {value!r}")
    return value


def _monitor_name(value: object) -> str:
    if not isinstance(value, str) or not _MONITOR_NAME.fullmatch(value):
        raise HyprlandError(f"invalid monitor name: {value!r}")
    return value


def _boolean(value: object, what: str) -> bool:
    if type(value) is not bool:
        raise HyprlandError(f"invalid {what}: {value!r}")
    return value


def _dispatch(expression: str) -> str:
    return f"hl.dispatch({expression})"


def render_action(action: HyprAction) -> str:
    """Собирает код Lua одного действия; значения проверяются до подстановки."""
    match action:
        case SetFloating(address, floating):
            mode = "enable" if _boolean(floating, "floating flag") else "disable"
            return _dispatch(f'hl.dsp.window.float({{ action = "{mode}", window = "address:{_address(address)}" }})')
        case MoveWindow(address, x, y):
            return _dispatch(
                f'hl.dsp.window.move({{ x = {_integer(x, "x")}, y = {_integer(y, "y")}, '
                f'window = "address:{_address(address)}" }})'
            )
        case ResizeWindow(address, width, height):
            return _dispatch(
                f'hl.dsp.window.resize({{ x = {_integer(width, "width")}, y = {_integer(height, "height")}, '
                f'window = "address:{_address(address)}" }})'
            )
        case FocusWindow(address):
            # Фокус сам по себе плавающее окно не поднимает: окно поднимается следом.
            return (_dispatch(f'hl.dsp.focus({{ window = "address:{_address(address)}" }})') + "\n"
                    + _dispatch("hl.dsp.window.bring_to_top()"))
        case FocusWorkspace(workspace_id):
            return _dispatch(
                f'hl.dsp.focus({{ workspace = "{_integer(workspace_id, "workspace id")}", on_current_monitor = true }})'
            )
        case FocusMonitor(monitor):
            return _dispatch(f'hl.dsp.focus({{ monitor = "{_monitor_name(monitor)}" }})')
        case MoveWindowToWorkspace(address, workspace_id, follow):
            return _dispatch(
                f'hl.dsp.window.move({{ workspace = "{_integer(workspace_id, "workspace id")}", '
                f'window = "address:{_address(address)}", follow = {str(_boolean(follow, "follow flag")).lower()} }})'
            )
        case MoveWorkspaceToMonitor(workspace_id, monitor):
            return _dispatch(
                f'hl.dsp.workspace.move({{ workspace = "{_integer(workspace_id, "workspace id")}", '
                f'monitor = "{_monitor_name(monitor)}" }})'
            )
        case ResizeColumn(fraction):
            if type(fraction) is not float or not math.isfinite(fraction) or not 0 < fraction <= 1:
                raise HyprlandError(f"invalid column fraction: {fraction!r}")
            text = f"{fraction:.4f}".rstrip("0").rstrip(".")
            return _dispatch(f'hl.dsp.layout("colresize {text}")')
        case SwapColumn(direction):
            if direction not in ("l", "r"):
                raise HyprlandError(f"invalid column direction: {direction!r}")
            return _dispatch(f'hl.dsp.layout("swapcol {direction}")')
        case _:
            raise HyprlandError(f"unsupported action: {action!r}")


def parse_event(line: str) -> HyprEvent:
    """Разбирает строку `EVENT>>DATA` по первому разделителю."""
    name, _, data = line.partition(">>")
    return HyprEvent(name=name, data=data)


def _monitor(raw: Mapping) -> Monitor:
    left, top, right, bottom = raw["reserved"]
    return Monitor(
        id=raw["id"],
        name=raw["name"],
        make=raw["make"],
        model=raw["model"],
        serial=raw["serial"],
        x=raw["x"],
        y=raw["y"],
        width=raw["width"],
        height=raw["height"],
        scale=float(raw["scale"]),
        reserved=(left, top, right, bottom),
        active_workspace_id=raw["activeWorkspace"]["id"],
        focused=raw["focused"],
    )


# Специальное пространство (scratchpad, свёрнутые окна): Hyprland ≥ 0.57 не отдаёт его `id`
# ни в `workspaces`, ни в `clients`. Движок видит такие пространства под одним отрицательным
# id — он не совпадает ни с одним управляемым пространством, поэтому их окна не планируются.
SPECIAL_WORKSPACE_ID = -1


def _workspace_id(raw: Mapping) -> int:
    """ID пространства из записи hyprctl; специальное без `id` — `SPECIAL_WORKSPACE_ID`."""
    if "id" in raw:
        return raw["id"]
    if raw.get("type") == "special" or str(raw.get("name", "")).startswith("special:"):
        return SPECIAL_WORKSPACE_ID
    raise KeyError("id")


def _workspace(raw: Mapping) -> Workspace:
    return Workspace(
        id=_workspace_id(raw),
        name=raw["name"],
        monitor=raw["monitor"],
        monitor_id=raw["monitorID"],
        windows=raw["windows"],
        tiled_layout=raw["tiledLayout"],
    )


def _window(raw: Mapping) -> Window:
    at_x, at_y = raw["at"]
    width, height = raw["size"]
    return Window(
        address=raw["address"],
        workspace_id=_workspace_id(raw["workspace"]),
        monitor_id=raw["monitor"],
        at=(at_x, at_y),
        size=(width, height),
        floating=raw["floating"],
        fullscreen=int(raw["fullscreen"]),
        class_name=raw["class"],
        title=raw["title"],
        pid=raw["pid"],
        mapped=raw["mapped"],
        hidden=raw["hidden"],
        pinned=raw["pinned"],
        tags=_tags(raw["tags"]),
    )


def _tags(raw: object) -> tuple[str, ...]:
    """Теги окна: список строк, иначе `TypeError`."""
    if not isinstance(raw, list) or not all(isinstance(tag, str) for tag in raw):
        raise TypeError(f"window tags must be a list of strings, got {raw!r}")
    return tuple(raw)


class Hyprland:
    """Единственная точка связи с Hyprland.

    `snapshot` и `apply` синхронны (вызывать через `asyncio.to_thread`),
    `events` — асинхронный поток событий.
    """

    def __init__(self, runner: Runner = run_hyprctl, env: Mapping[str, str] | None = None) -> None:
        self._runner = runner
        self._env = os.environ if env is None else env

    def _read(self, command: str) -> object:
        output = self._runner(["hyprctl", "-j", command])
        try:
            return json.loads(output)
        except json.JSONDecodeError as error:
            raise HyprlandError(f"hyprctl -j {command} returned invalid JSON") from error

    def snapshot(self) -> CompositorSnapshot:
        """Читает мониторы, пространства, окна, активное окно и указатель."""
        monitors = self._read("monitors")
        workspaces = self._read("workspaces")
        clients = self._read("clients")
        active = self._read("activewindow")
        cursor = self._read("cursorpos")
        try:
            return CompositorSnapshot(
                monitors=tuple(_monitor(m) for m in monitors),
                workspaces=tuple(_workspace(w) for w in workspaces),
                windows=tuple(_window(c) for c in clients),
                active_window=_window(active) if active else None,
                cursor_position=(int(cursor["x"]), int(cursor["y"])),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise HyprlandError(f"unexpected hyprctl reply shape: {error!r}") from error

    def apply(self, actions: Sequence[HyprAction]) -> None:
        """Выполняет действия одним `hyprctl eval`; успех — ровно ответ `ok`."""
        if not actions:
            return
        script = "\n".join(render_action(action) for action in actions)
        reply = self._runner(["hyprctl", "eval", script]).strip()
        if reply != "ok":
            raise HyprlandError(f"hyprctl eval failed: {reply or 'empty reply'}")

    def _events_socket_path(self) -> str:
        runtime_dir = self._env.get("XDG_RUNTIME_DIR")
        signature = self._env.get("HYPRLAND_INSTANCE_SIGNATURE")
        if not runtime_dir:
            raise HyprlandError("XDG_RUNTIME_DIR is not set")
        if not signature:
            raise HyprlandError("HYPRLAND_INSTANCE_SIGNATURE is not set")
        return os.path.join(runtime_dir, "hypr", signature, ".socket2.sock")

    async def events(self) -> AsyncIterator[HyprEvent]:
        """Поток событий Hyprland; завершается, когда Hyprland закрывает сокет."""
        path = self._events_socket_path()
        try:
            reader, writer = await asyncio.open_unix_connection(path, limit=EVENT_LINE_LIMIT)
        except OSError as error:
            raise HyprlandError(f"cannot connect to {path}: {error}") from error
        try:
            async for raw in reader:
                line = raw.decode("utf-8", errors="replace").rstrip("\n")
                if line:
                    yield parse_event(line)
        finally:
            writer.close()
