"""Данные оболочки: закреплённые приложения, настройка ограничения анимаций и сводка сети.

Закрепления хранятся в `pins.json` вида `{"version": 1, "pinned": [desktop ID, …]}`.
Запись атомарная: новый файл с правами `0600` пишется рядом и заменяет старый, поэтому
ошибка записи оставляет прежний список. Только стандартная библиотека.
"""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

# Закрепления, когда файла ещё нет: Dolphin, Chrome, VS Code, Ghostty, Telegram.
DEFAULT_PINS = ("org.kde.dolphin", "google-chrome", "code", "com.mitchellh.ghostty", "org.telegram.desktop")
PINS_LIMIT = 100

# Допустимый desktop ID: без разделителей пути, пробелов и символов оболочки.
_DESKTOP_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.+-]{0,199}")


def default_pins_path() -> Path:
    """`$XDG_CONFIG_HOME/quietline/pins.json`, без переменной — `~/.config/quietline/pins.json`."""
    directory = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(directory) / "quietline" / "pins.json"


def validated_pins(ids: object) -> list[str]:
    """Список desktop ID без повторов в исходном порядке; `ValueError` при неверных данных."""
    if not isinstance(ids, list) or len(ids) > PINS_LIMIT:
        raise ValueError(f"pins must be a list of at most {PINS_LIMIT} desktop IDs")
    result: list[str] = []
    for item in ids:
        if not isinstance(item, str) or not _DESKTOP_ID.fullmatch(item) or ".." in item:
            raise ValueError(f"invalid desktop ID: {item!r}")
        if item not in result:
            result.append(item)
    return result


def load_pins(path: Path) -> list[str]:
    """Закрепления из файла; без файла — `DEFAULT_PINS`. Повреждённый файл — `ValueError`, файл не меняется."""
    if not path.exists():
        return list(DEFAULT_PINS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as error:
        raise ValueError(f"cannot read pinned applications from {path}") from error
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError(f"unknown pins file format in {path}")
    try:
        return validated_pins(data.get("pinned"))
    except ValueError as error:
        raise ValueError(f"invalid pins in {path}: {error}") from error


def save_pins(path: Path, ids: object) -> None:
    """Атомарно записывает закрепления; при ошибке проверки или записи прежний файл остаётся."""
    pins = validated_pins(ids)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=path.parent, encoding="utf-8", delete=False) as handle:
            temporary = Path(handle.name)
            os.chmod(temporary, 0o600)
            json.dump({"version": 1, "pinned": pins}, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def reduced_motion() -> bool:
    """Нужно ли ограничить анимации.

    `QUIETLINE_REDUCED_MOTION` (`1`, `true`, `yes` — да, другое значение — нет) важнее
    настройки системы. Без переменной читается `org.freedesktop.appearance reduced-motion`
    портала через `gdbus`; портал недоступен — анимации остаются.
    """
    override = os.environ.get("QUIETLINE_REDUCED_MOTION")
    if override is not None:
        return override.lower() in {"1", "true", "yes"}
    command = [
        "gdbus", "call", "--session",
        "--dest", "org.freedesktop.portal.Desktop",
        "--object-path", "/org/freedesktop/portal/desktop",
        "--method", "org.freedesktop.portal.Settings.ReadOne",
        "org.freedesktop.appearance", "reduced-motion",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=1.5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and re.search(r"\buint32\s+1\b", result.stdout) is not None


def network_devices() -> list[dict[str, Any]]:
    """Сетевые устройства NetworkManager: имя, профиль (`""` без профиля) и адреса IPv4/IPv6.

    Только чтение через `nmcli`; NetworkManager недоступен — `RuntimeError`.
    """
    command = [
        "nmcli", "--terse", "--escape", "no",
        "--fields", "GENERAL.DEVICE,GENERAL.CONNECTION,IP4.ADDRESS,IP6.ADDRESS",
        "device", "show",
    ]
    result = subprocess.run(
        command, capture_output=True, text=True, timeout=2, check=False, env={**os.environ, "LC_ALL": "C"}
    )
    if result.returncode:
        raise RuntimeError("NetworkManager is unavailable")
    devices: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in result.stdout.splitlines():
        key, _, value = line.partition(":")
        if key == "GENERAL.DEVICE":
            current = {"device": value, "profile": "", "addresses": []}
            devices.append(current)
        elif current is None:
            continue
        elif key == "GENERAL.CONNECTION":
            current["profile"] = "" if value == "--" else value
        elif key.startswith(("IP4.ADDRESS[", "IP6.ADDRESS[")) and value:
            current["addresses"].append(value)
    return devices
