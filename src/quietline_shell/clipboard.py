"""История буфера обмена текущего сеанса поверх cliphist.

База — `$XDG_RUNTIME_DIR/quietline/clipboard.db`, она исчезает с выходом из системы и
очищается при блокировке и выходе из сеанса. Запись приходит от
`wl-paste --type text|image --watch quietline-shell clipboard store` и не сохраняется:
на паузе (флаг `clipboard.paused`), с пометкой секрета (`CLIPBOARD_STATE=sensitive` от
wl-paste) и при копировании из окна менеджера паролей (класс окна из `PASSWORD_MANAGERS`).
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Any

from quietline_shell.session import active_window, runtime_dir

PASSWORD_MANAGERS = {"1password"}
_ID = re.compile(r"\d{1,12}")
_IMAGE = re.compile(r"^\[\[ binary data .* (png|jpeg|jpg|gif|bmp|tiff|webp) .*\]\]$")


def database() -> Path:
    return runtime_dir() / "clipboard.db"


def pause_flag() -> Path:
    return runtime_dir() / "clipboard.paused"


def cliphist(args: list[str], data: bytes | None = None) -> bytes:
    """Выполняет `cliphist -db-path <база> …`; ненулевой код — `RuntimeError`."""
    runtime_dir().mkdir(parents=True, exist_ok=True, mode=0o700)
    command = ["cliphist", "-db-path", str(database()), *args]
    try:
        result = subprocess.run(command, input=data, capture_output=True, timeout=10, check=False)
    except FileNotFoundError as error:
        raise RuntimeError("cliphist is not installed") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("cliphist did not respond") from error
    if result.returncode:
        detail = result.stderr.decode(errors="replace").strip() or f"exit code {result.returncode}"
        raise RuntimeError(f"cliphist failed: {detail}")
    return result.stdout


def _entry_id(entry_id: str) -> str:
    if not isinstance(entry_id, str) or not _ID.fullmatch(entry_id):
        raise ValueError(f"invalid clipboard entry id: {entry_id!r}")
    return entry_id


def store(data: bytes) -> dict[str, Any]:
    """Сохраняет запись буфера, если её не нужно пропустить; ответ называет причину пропуска."""
    if pause_flag().exists():
        return {"stored": False, "reason": "paused"}
    if os.environ.get("CLIPBOARD_STATE") == "sensitive":
        return {"stored": False, "reason": "sensitive"}
    try:
        app = active_window()["app"]
    except RuntimeError:
        app = ""
    if app.lower() in PASSWORD_MANAGERS:
        return {"stored": False, "reason": "password-manager"}
    cliphist(["store"], data)
    return {"stored": True}


def entries() -> dict[str, Any]:
    """Записи истории, новые первыми: `{id, kind: "text" | "image", preview}`."""
    result = []
    for line in cliphist(["list"]).decode(errors="replace").splitlines():
        entry_id, _, preview = line.partition("\t")
        if _ID.fullmatch(entry_id):
            result.append({"id": entry_id, "kind": "image" if _IMAGE.match(preview) else "text", "preview": preview})
    return {"entries": result, "paused": pause_flag().exists()}


def _decode(entry_id: str) -> bytes:
    return cliphist(["decode"], f"{_entry_id(entry_id)}\t\n".encode())


def restore(entry_id: str) -> dict[str, bool]:
    """Возвращает запись в буфер обмена через `wl-copy`."""
    data = _decode(entry_id)
    try:
        result = subprocess.run(["wl-copy"], input=data, capture_output=True, timeout=10, check=False)
    except FileNotFoundError as error:
        raise RuntimeError("wl-copy is not installed") from error
    if result.returncode:
        raise RuntimeError(f"wl-copy failed: {result.stderr.decode(errors='replace').strip()}")
    return {"ok": True}


def delete(entry_id: str) -> dict[str, bool]:
    cliphist(["delete"], f"{_entry_id(entry_id)}\t\n".encode())
    image_path(entry_id).unlink(missing_ok=True)
    return {"ok": True}


def image_path(entry_id: str) -> Path:
    return runtime_dir() / f"clipboard-{_entry_id(entry_id)}.png"


def image(entry_id: str) -> dict[str, str]:
    """Картинка записи во временном файле `$XDG_RUNTIME_DIR/quietline/clipboard-<id>.png`."""
    path = image_path(entry_id)
    if not path.exists():
        temporary = path.with_name(f".{path.name}.part")
        temporary.write_bytes(_decode(entry_id))
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    return {"path": str(path)}


def wipe() -> dict[str, bool]:
    """Очищает историю и временные картинки."""
    cliphist(["wipe"])
    for path in runtime_dir().glob("clipboard-*.png"):
        path.unlink(missing_ok=True)
    return {"ok": True}


def set_paused(paused: bool) -> dict[str, bool]:
    flag = pause_flag()
    if paused:
        runtime_dir().mkdir(parents=True, exist_ok=True, mode=0o700)
        flag.touch()
    else:
        flag.unlink(missing_ok=True)
    return {"ok": True}
