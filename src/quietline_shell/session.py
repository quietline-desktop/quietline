"""Сеанс: блокировка экрана, выход из сеанса, перезагрузка и выключение.

Экран блокировки — отдельный процесс Quickshell `qs -p <конфигурация>/lock/LockScreen.qml`,
не зависящий от панели; запущенный экземпляр записан в `$XDG_RUNTIME_DIR/quietline/lock.pid`.
Выход, перезагрузка и выключение сначала корректно закрывают все окна Hyprland и
выполняются, только когда окон не осталось: окно с несохранённым документом останавливает
действие, и ответ называет оставшиеся приложения.
"""

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

SESSION_ACTIONS = ("logout", "reboot", "poweroff")
CLOSE_TIMEOUT = 20.0
_ADDRESS = re.compile(r"0x[0-9a-fA-F]+")


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


def wait_closed(addresses: set[str], timeout: float) -> list[dict[str, Any]]:
    """Ждёт закрытия окон `addresses`; оставшиеся к сроку окна — список."""
    deadline = time.monotonic() + timeout
    while True:
        remaining = [window for window in windows() if window["address"] in addresses]
        if not remaining or time.monotonic() >= deadline:
            return remaining
        time.sleep(0.5)


def _process_alive(pid: int) -> bool:
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().find(b"LockScreen.qml") >= 0
    except OSError:
        return False


def lock() -> dict[str, bool]:
    """Запускает экран блокировки, если он ещё не запущен."""
    state = runtime_dir()
    pidfile = state / "lock.pid"
    try:
        if _process_alive(int(pidfile.read_text(encoding="utf-8").strip())):
            return {"locked": True}
    except (OSError, ValueError):
        pass
    screen = lock_screen_path()
    if not screen.is_file():
        raise RuntimeError(f"lock screen not found: {screen}")
    try:
        process = subprocess.Popen(
            ["qs", "-p", str(screen)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True,
        )
    except FileNotFoundError as error:
        raise RuntimeError("qs (Quickshell) is not installed") from error
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    pidfile.write_text(f"{process.pid}\n", encoding="utf-8")
    return {"locked": True}


def end_session(action: str, timeout: float = CLOSE_TIMEOUT) -> dict[str, Any]:
    """Корректно закрывает все окна и выполняет `logout`, `reboot` или `poweroff`.

    Если к сроку остались окна, действие не выполняется: `{"done": false, "remaining": […]}`.
    """
    if action not in SESSION_ACTIONS:
        raise ValueError(f"unknown session action: {action!r}")
    opened = windows()
    for window in opened:
        close_window(window["address"])
    remaining = wait_closed({window["address"] for window in opened}, timeout) if opened else []
    if remaining:
        return {
            "action": action, "done": False,
            "remaining": [{"app": window["app"], "title": window["title"]} for window in remaining],
        }
    match action:
        case "logout":
            hyprland_dispatch("hl.dsp.exit()")
        case "reboot":
            run(["systemctl", "reboot"])
        case _:
            run(["systemctl", "poweroff"])
    return {"action": action, "done": True}
