"""Снимки экрана: монитор с фокусом без диалога и область с разметкой в Satty.

Снимок монитора: `grim -o <монитор> -` → файл `Screenshot_ГГГГ-ММ-ДД_ЧЧ-ММ-СС.png` в каталоге
`Screenshots` внутри «Изображений» (`xdg-user-dir PICTURES`) → PNG в буфер через `wl-copy`.
Уведомление об успехе — только после обоих шагов; ошибка называет неудавшийся шаг.
Область: `grim -o <монитор> -` сразу, пока открытые панели и меню оболочки ещё на экране →
застывший снимок в Satty на весь экран с инструментом обрезки: выделение задаёт область,
Enter копирует, `Ctrl+S` сохраняет в тот же каталог, `Esc` отменяет.
"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from quietline_shell.config import notification_text
from quietline_shell.session import copy_to_clipboard, notify, run

FILE_PATTERN = "Screenshot_%Y-%m-%d_%H-%M-%S"


class CaptureError(RuntimeError):
    """Ошибка шага снимка; `step` — `capture`, `save` или `copy`."""

    def __init__(self, step: str, message: str) -> None:
        super().__init__(message)
        self.step = step


_STEP_KEYS = {"capture": "capture_failed", "save": "save_failed", "copy": "copy_failed"}


def screenshots_dir() -> Path:
    """`<Изображения>/Screenshots`; без `xdg-user-dir` — `~/Pictures/Screenshots`."""
    try:
        pictures = run(["xdg-user-dir", "PICTURES"]).strip()
    except RuntimeError:
        pictures = ""
    return Path(pictures or Path.home() / "Pictures") / "Screenshots"


def _bytes(args: list[str], step: str) -> bytes:
    try:
        result = subprocess.run(args, capture_output=True, timeout=15, check=False)
    except FileNotFoundError as error:
        raise CaptureError(step, f"{args[0]} is not installed") from error
    except subprocess.TimeoutExpired as error:
        raise CaptureError(step, f"{args[0]} did not respond") from error
    if result.returncode:
        detail = result.stderr.decode(errors="replace").strip() or f"exit code {result.returncode}"
        raise CaptureError(step, f"{args[0]} failed: {detail}")
    return result.stdout


def focused_output() -> str:
    try:
        monitors = json.loads(run(["hyprctl", "monitors", "-j"]))
    except (RuntimeError, ValueError) as error:
        raise CaptureError("capture", f"cannot find the focused monitor: {error}") from error
    name = next((item.get("name") for item in monitors if isinstance(item, dict) and item.get("focused")), None)
    if not name:
        raise CaptureError("capture", "no monitor has focus")
    return name


def new_path(directory: Path, now: datetime) -> Path:
    """Свободное имя файла снимка: при совпадении времени добавляется `-2`, `-3`…"""
    base = now.strftime(FILE_PATTERN)
    path = directory / f"{base}.png"
    number = 2
    while path.exists():
        path = directory / f"{base}-{number}.png"
        number += 1
    return path


def _save(png: bytes, now: datetime) -> Path:
    directory = screenshots_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        path = new_path(directory, now)
        temporary = path.with_name(f".{path.name}.part")
        temporary.write_bytes(png)
        os.replace(temporary, path)
    except OSError as error:
        raise CaptureError("save", f"cannot write {directory}: {error.strerror or error}") from error
    return path


def capture_output(now: datetime | None = None) -> dict[str, Any]:
    """Снимок монитора с фокусом: файл, затем буфер, затем уведомление."""
    try:
        png = _bytes(["grim", "-o", focused_output(), "-"], "capture")
        path = _save(png, now or datetime.now())
        try:
            copy_to_clipboard(png, "image/png")
        except RuntimeError as error:
            raise CaptureError("copy", str(error)) from error
    except CaptureError as error:
        notify(notification_text(_STEP_KEYS[error.step]), str(error), urgency="critical")
        raise
    notify(notification_text("screenshot_saved"), str(path))
    return {"path": str(path), "copied": True}


def capture_region() -> dict[str, bool]:
    """Снимок монитора с фокусом и выбор области обрезкой в Satty поверх застывшего экрана."""
    try:
        png = _bytes(["grim", "-o", focused_output(), "-"], "capture")
        directory = screenshots_dir()
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        notify(notification_text(_STEP_KEYS["save"]), str(error), urgency="critical")
        raise CaptureError("save", f"cannot create {error.filename}: {error.strerror}") from error
    except CaptureError as error:
        notify(notification_text(_STEP_KEYS[error.step]), str(error), urgency="critical")
        raise
    command = [
        "satty", "--filename", "-", "--output-filename", str(directory / f"{FILE_PATTERN}.png"),
        "--copy-command", "wl-copy", "--early-exit", "all", "--fullscreen", "--initial-tool", "crop",
    ]
    try:
        editor = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, start_new_session=True)
    except FileNotFoundError as error:
        notify(notification_text("editor_failed"), "satty is not installed", urgency="critical")
        raise CaptureError("capture", "satty is not installed") from error
    assert editor.stdin is not None
    editor.stdin.write(png)
    editor.stdin.close()
    return {"started": True}
