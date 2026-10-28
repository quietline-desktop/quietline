"""Сеанс и приложения: блокировка экрана, выход из сеанса, перезагрузка, выключение,
корректный выход из приложения и его принудительное завершение.

Экран блокировки — отдельный процесс Quickshell `qs -p <конфигурация>/lock/LockScreen.qml`,
не зависящий от панели; запущенный экземпляр записан в `$XDG_RUNTIME_DIR/quietline/lock.pid`,
а метка `lock.secure` рядом означает, что блокировка подтверждена.
Выход, перезагрузка и выключение сначала корректно закрывают все окна Hyprland и
выполняются, только когда окон не осталось: окно с несохранённым документом останавливает
действие, и ответ называет оставшиеся приложения.

Приложения, запущенные оболочкой, живут в группе процессов systemd `app-quietline-*.scope`.
Корректный выход закрывает окна процесса; процессу, оставшемуся без окон, `SIGTERM`
посылается, только если он из такой группы и ни у одного процесса группы нет окна (в том
числе диалога сохранения). `SIGKILL` — только у `app kill`, после подтверждения на панели.
"""

import json
import os
import re
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from quietline_shell.config import notification_text

SESSION_ACTIONS = ("logout", "reboot", "poweroff")
CLOSE_TIMEOUT = 20.0
QUIT_TIMEOUT = 10.0
# Сколько процесс без окон может завершаться сам, прежде чем получит `SIGTERM`.
EXIT_GRACE = 3.0
# Сколько ждать подтверждения блокировки от экрана блокировки.
LOCK_WAIT = 5.0
# Имена программы Quickshell: её окна не закрываются и не завершаются как приложения.
SHELL_PROGRAMS = {"qs", "quickshell"}
# Команды выхода приложений по классу окна: используются вместо закрытия окон.
KNOWN_QUIT: dict[str, list[str]] = {}
_ADDRESS = re.compile(r"0x[0-9a-fA-F]+")
_QUIETLINE_SCOPE = re.compile(r"/(app-quietline-[A-Za-z0-9_.:-]+\.scope)(?:/|$)")


def runtime_dir() -> Path:
    """`$XDG_RUNTIME_DIR/quietline`; без переменной — `RuntimeError`."""
    base = os.environ.get("XDG_RUNTIME_DIR")
    if not base:
        raise RuntimeError("XDG_RUNTIME_DIR is not set")
    return Path(base) / "quietline"


def lock_screen_path() -> Path:
    """`$XDG_CONFIG_HOME/quickshell/quietline/lock/LockScreen.qml`."""
    directory = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(directory) / "quickshell" / "quietline" / "lock" / "LockScreen.qml"


def run(args: list[str], timeout: float = 5) -> str:
    """stdout команды; ненулевой код, отсутствие программы или таймаут — `RuntimeError`."""
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError as error:
        raise RuntimeError(f"{args[0]} is not installed") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"{args[0]} did not respond") from error
    if result.returncode:
        detail = (result.stderr or result.stdout).strip() or f"exit code {result.returncode}"
        raise RuntimeError(f"{args[0]} failed: {detail}")
    return result.stdout


def notify(summary: str, body: str = "", urgency: str = "normal") -> None:
    """Уведомление окружения через `notify-send`; без сервера уведомлений — молча ничего."""
    try:
        subprocess.run(["notify-send", "--app-name=Quietline", f"--urgency={urgency}", summary, body],
                       capture_output=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        pass


def hyprland_dispatch(expression: str) -> None:
    """Выполняет Lua-диспетчер Hyprland 0.55: `hyprctl dispatch '<hl.dsp…>'`."""
    run(["hyprctl", "dispatch", expression])


def windows() -> list[dict[str, Any]]:
    """Окна Hyprland: `{address, app, title, pid}`."""
    try:
        clients = json.loads(run(["hyprctl", "clients", "-j"]))
    except ValueError as error:
        raise RuntimeError("hyprctl returned no JSON for clients") from error
    return [
        {"address": item.get("address", ""), "app": item.get("class") or item.get("initialClass") or "",
         "title": item.get("title", ""), "pid": item.get("pid", -1)}
        for item in clients if isinstance(item, dict) and _ADDRESS.fullmatch(str(item.get("address", "")))
    ]


def close_window(address: str) -> None:
    if not _ADDRESS.fullmatch(address):
        raise ValueError(f"invalid window address: {address!r}")
    hyprland_dispatch(f'hl.dsp.window.close({{window = "address:{address}"}})')


def wait_for_windows(blocking, timeout: float) -> list[dict[str, Any]]:
    """Ждёт, пока среди окон не останется ни одного, для которого `blocking(window)` истинно.

    Окна каждый раз читаются заново: окно, открытое во время ожидания (например, диалог
    сохранения), тоже задерживает. Оставшиеся к сроку окна — список.
    """
    deadline = time.monotonic() + timeout
    while True:
        remaining = [window for window in windows() if blocking(window)]
        if not remaining or time.monotonic() >= deadline:
            return remaining
        time.sleep(0.5)


def copy_to_clipboard(data: bytes, mime: str | None = None) -> None:
    """Кладёт `data` в буфер через `wl-copy`.

    `wl-copy` оставляет в фоне процесс, который держит буфер и унаследованный stderr,
    поэтому stderr идёт во временный файл, а ожидание — только до выхода первого процесса.
    """
    command = ["wl-copy", *(["--type", mime] if mime else [])]
    with tempfile.TemporaryFile() as errors:
        try:
            result = subprocess.run(command, input=data, stdout=subprocess.DEVNULL, stderr=errors, timeout=10, check=False)
        except FileNotFoundError as error:
            raise RuntimeError("wl-copy is not installed") from error
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("wl-copy did not respond") from error
        if result.returncode:
            errors.seek(0)
            detail = errors.read(4096).decode(errors="replace").strip() or f"exit code {result.returncode}"
            raise RuntimeError(f"wl-copy failed: {detail}")


def _remaining(found: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [{"app": window["app"], "title": window["title"]} for window in found]


def _lock_running(pidfile: Path) -> int | None:
    """pid запущенного экрана блокировки, если он есть."""
    try:
        pid = int(pidfile.read_text(encoding="utf-8").strip())
        if Path(f"/proc/{pid}/cmdline").read_bytes().find(b"LockScreen.qml") >= 0:
            return pid
    except (OSError, ValueError):
        pass
    return None


def _wipe_clipboard() -> None:
    """Очищает историю буфера; недоступный cliphist не мешает блокировке и выходу."""
    from quietline_shell import clipboard

    try:
        clipboard.wipe()
    except (RuntimeError, OSError):
        pass


def lock() -> dict[str, bool]:
    """Запускает экран блокировки, ждёт подтверждения блокировки и очищает историю буфера.

    Экран блокировки создаёт файл-метку `lock.secure`, когда Hyprland подтвердил, что все
    экраны закрыты. Без метки за `LOCK_WAIT` секунд процесс экрана блокировки завершается,
    ответ — ошибка.
    """
    state = runtime_dir()
    pidfile, marker = state / "lock.pid", state / "lock.secure"
    running = _lock_running(pidfile)
    if running is not None and marker.exists():
        _wipe_clipboard()
        return {"locked": True}
    if running is not None:
        os.kill(running, signal.SIGTERM)
    screen = lock_screen_path()
    if not screen.is_file():
        raise RuntimeError(f"lock screen not found: {screen}")
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    marker.unlink(missing_ok=True)
    try:
        process = subprocess.Popen(
            ["qs", "-p", str(screen)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True, env={**os.environ, "QUIETLINE_LOCK_MARKER": str(marker)},
        )
    except FileNotFoundError as error:
        raise RuntimeError("qs (Quickshell) is not installed") from error
    pidfile.write_text(f"{process.pid}\n", encoding="utf-8")
    deadline = time.monotonic() + LOCK_WAIT
    while not marker.exists():
        if process.poll() is not None:
            notify(notification_text("lock_failed"), "The lock screen exited.", urgency="critical")
            raise RuntimeError("the lock screen exited before locking")
        if time.monotonic() >= deadline:
            process.terminate()
            notify(notification_text("lock_failed"), "The lock screen did not lock in time.", urgency="critical")
            raise RuntimeError("the lock screen did not lock in time")
        time.sleep(0.1)
    _wipe_clipboard()
    return {"locked": True}


def end_session(action: str, timeout: float = CLOSE_TIMEOUT) -> dict[str, Any]:
    """Корректно закрывает все окна и выполняет `logout`, `reboot` или `poweroff`.

    Действие выполняется, только когда окон не осталось совсем, в том числе открытых во
    время ожидания; иначе — `{"done": false, "remaining": […]}`.
    """
    if action not in SESSION_ACTIONS:
        raise ValueError(f"unknown session action: {action!r}")
    for window in windows():
        close_window(window["address"])
    remaining = wait_for_windows(lambda window: True, timeout)
    if not remaining:
        remaining = windows()
    if remaining:
        return {"action": action, "done": False, "remaining": _remaining(remaining)}
    match action:
        case "logout":
            _wipe_clipboard()
            hyprland_dispatch("hl.dsp.exit()")
        case "reboot":
            run(["systemctl", "reboot"])
        case _:
            run(["systemctl", "poweroff"])
    return {"action": action, "done": True}


def active_window() -> dict[str, Any]:
    """Активное окно Hyprland `{address, app, title, pid}`; без активного окна — `RuntimeError`."""
    try:
        data = json.loads(run(["hyprctl", "activewindow", "-j"]))
    except ValueError as error:
        raise RuntimeError("hyprctl returned no JSON for the active window") from error
    if not isinstance(data, dict) or not _ADDRESS.fullmatch(str(data.get("address", ""))):
        raise RuntimeError("there is no active window")
    return {"address": data["address"], "app": data.get("class") or "", "title": data.get("title", ""),
            "pid": int(data.get("pid", -1))}


def process_alive(pid: int) -> bool:
    return Path(f"/proc/{pid}").exists()


def quietline_scope(pid: int) -> str | None:
    """Группа процессов `app-quietline-*.scope`, в которой живёт `pid`, или `None`."""
    try:
        cgroup = Path(f"/proc/{pid}/cgroup").read_text(encoding="utf-8")
    except OSError:
        return None
    match = _QUIETLINE_SCOPE.search(cgroup)
    return match.group(1) if match else None


def is_shell_process(pid: int) -> bool:
    """`pid` — процесс самой оболочки Quickshell (её окно «Настройки»)."""
    try:
        program = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0", 1)[0]
    except OSError:
        return False
    return Path(program.decode(errors="replace")).name in SHELL_PROGRAMS


def _valid_pid(pid: int) -> int:
    if not isinstance(pid, int) or pid <= 1:
        raise ValueError(f"invalid process id: {pid!r}")
    if is_shell_process(pid):
        raise RuntimeError("this window belongs to the Quietline shell; close it with Super+W")
    return pid


def quit_app(pid: int | None = None, timeout: float = QUIT_TIMEOUT) -> dict[str, Any]:
    """Корректный выход из приложения процесса `pid` (по умолчанию — процесса активного окна).

    Ответ: `closed` — закрыто окон, `remaining` — оставшиеся окна (сигнал не посылался),
    `background` — процесс остался без окон и не из группы Quietline. `SIGTERM` получает
    только сам `pid` и только когда ни у одного процесса его группы нет окон.
    """
    if pid is None:
        target = active_window()
        pid, app = target["pid"], target["app"]
    else:
        app = ""
    _valid_pid(pid)
    opened = [window for window in windows() if window["pid"] == pid]
    app = app or (opened[0]["app"] if opened else "")
    if app in KNOWN_QUIT:
        run(KNOWN_QUIT[app])
    else:
        for window in opened:
            close_window(window["address"])
    scope = quietline_scope(pid)

    def blocking(window: dict[str, Any]) -> bool:
        return window["pid"] == pid or (scope is not None and quietline_scope(window["pid"]) == scope)

    remaining = wait_for_windows(blocking, timeout)
    result: dict[str, Any] = {
        "closed": len([window for window in opened if window not in remaining]),
        "remaining": _remaining(remaining),
        "background": False,
    }
    if remaining:
        return result
    deadline = time.monotonic() + EXIT_GRACE
    while process_alive(pid) and time.monotonic() < deadline:
        time.sleep(0.25)
    if not process_alive(pid):
        return result
    if scope is None:
        result["background"] = True
        result["app"] = app
        return result
    late = [window for window in windows() if blocking(window)]
    if late:
        result["remaining"] = _remaining(late)
        return result
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    return result


def kill_app(pid: int) -> dict[str, int]:
    """Принудительно завершает процесс `pid` сигналом `SIGKILL`."""
    _valid_pid(pid)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError as error:
        raise RuntimeError(f"process {pid} is not running") from error
    except PermissionError as error:
        raise RuntimeError(f"process {pid} belongs to another user") from error
    return {"killed": pid}
