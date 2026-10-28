"""Данные оболочки: закреплённые приложения, язык и регион, ограничение анимаций и сводка «О системе».

Закрепления хранятся в `pins.json` вида `{"version": 1, "pinned": [desktop ID, …]}`.
Запись атомарная: новый файл с правами `0600` пишется рядом и заменяет старый, поэтому
ошибка записи оставляет прежний список.

Язык и регион — `region.json` вида `{"version": 1, "language", "clock", "date", "layouts",
"toggle"}`. Сохранение region также обновляет `locale.conf` (строка `LANG`, остальные строки
файла сохраняются) и `quietline/keyboard.lua` с раскладками для Hyprland. Только стандартная
библиотека.
"""

import json
import os
import platform
import re
import socket
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
    atomic_write_json(path, {"version": 1, "pinned": validated_pins(ids)})


LANGUAGES = ("ru", "en")
CLOCKS = ("24h", "12h")
DATES = ("dmy", "ymd", "mdy")
LAYOUTS = ("us", "ru")
TOGGLES = ("grp:lalt_lshift_toggle", "grp:alt_shift_toggle", "grp:ctrl_shift_toggle", "grp:caps_toggle")

_REGION_FIELDS = ("language", "clock", "date", "layouts", "toggle")
_LOCALES = {"ru": "ru_RU.UTF-8", "en": "en_US.UTF-8"}
_HYPRCTL_TIMEOUT = 3


def default_region_path() -> Path:
    """`$XDG_CONFIG_HOME/quietline/region.json`, без переменной — `~/.config/quietline/region.json`."""
    directory = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(directory) / "quietline" / "region.json"


def default_region(lang: str | None) -> dict[str, Any]:
    """Настройки без файла: русский (`LANG` начинается с `ru`) — `24h` и `dmy`, иначе английский — `12h` и `mdy`."""
    russian = bool(lang) and lang.startswith("ru")
    return {
        "language": "ru" if russian else "en",
        "clock": "24h" if russian else "12h",
        "date": "dmy" if russian else "mdy",
        "layouts": list(LAYOUTS),
        "toggle": TOGGLES[0],
    }


def validated_region(data: object, current: dict[str, Any]) -> dict[str, Any]:
    """`current` с применёнными полями из `data`; неизвестное поле или значение — `ValueError`."""
    if not isinstance(data, dict):
        raise ValueError("region must be a JSON object")
    unknown = sorted(str(key) for key in data if key not in _REGION_FIELDS)
    if unknown:
        raise ValueError(f"unknown region field: {', '.join(unknown)}")
    result = {key: (list(current[key]) if key == "layouts" else current[key]) for key in _REGION_FIELDS}
    choices = {"language": LANGUAGES, "clock": CLOCKS, "date": DATES, "toggle": TOGGLES}
    for key, value in data.items():
        if key == "layouts":
            if not isinstance(value, list) or sorted(map(str, value)) != sorted(LAYOUTS) or not all(isinstance(item, str) for item in value):
                raise ValueError(f"layouts must be a permutation of {list(LAYOUTS)}")
            result[key] = list(value)
        elif not isinstance(value, str) or value not in choices[key]:
            raise ValueError(f"invalid {key}: {value!r}")
        else:
            result[key] = value
    return result


def load_region(path: Path, lang: str | None = None) -> dict[str, Any]:
    """Настройки из файла; без файла — `default_region(lang)`. Повреждённый файл — `ValueError`, файл не меняется."""
    if not path.exists():
        return default_region(lang)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as error:
        raise ValueError(f"cannot read region settings from {path}") from error
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError(f"unknown region file format in {path}")
    fields = {key: value for key, value in data.items() if key != "version"}
    try:
        return validated_region(fields, default_region(lang))
    except ValueError as error:
        raise ValueError(f"invalid region settings in {path}: {error}") from error


def keyboard_lua(region: dict[str, Any]) -> str:
    """Содержимое `keyboard.lua`: раскладки и сочетание переключения для Hyprland."""
    return f'return {{ kb_layout = "{",".join(region["layouts"])}", kb_options = "{region["toggle"]}" }}\n'


def apply_keyboard(region: dict[str, Any]) -> bool:
    """Применяет раскладки в работающем Hyprland; `True` только при коде 0 `hyprctl`.

    Вне сеанса Hyprland, без `hyprctl` и по таймауту возвращает `False`.
    """
    if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return False
    layout = ",".join(region["layouts"])
    expression = f'hl.config({{ input = {{ kb_layout = "{layout}", kb_options = "{region["toggle"]}" }} }})'
    try:
        result = subprocess.run(["hyprctl", "eval", expression], capture_output=True, text=True,
                                timeout=_HYPRCTL_TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _locale_conf(existing: str, language: str) -> str:
    """`existing` с заменённой строкой `LANG`; без неё строка дописывается в конец."""
    line = f"LANG={_LOCALES[language]}"
    lines = existing.splitlines()
    for index, item in enumerate(lines):
        if item.startswith("LANG="):
            lines[index] = line
            break
    else:
        lines.append(line)
    return "\n".join(lines) + "\n"


def save_region(path: Path, region: dict[str, Any], config_home: Path) -> None:
    """Атомарно пишет `region.json`, затем `config_home/locale.conf` и `config_home/quietline/keyboard.lua`."""
    checked = validated_region(region, region)
    atomic_write_json(path, {"version": 1, **checked})
    locale_path = config_home / "locale.conf"
    try:
        existing = locale_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        existing = ""
    _atomic_write_text(locale_path, _locale_conf(existing, checked["language"]))
    _atomic_write_text(config_home / "quietline" / "keyboard.lua", keyboard_lua(checked))


def _atomic_write_text(path: Path, text: str) -> None:
    """Заменяет `path` текстовым файлом с правами `0644` только после полной записи на диск."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=path.parent, encoding="utf-8", delete=False) as handle:
            temporary = Path(handle.name)
            os.chmod(temporary, 0o644)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def atomic_write_json(path: Path, value: Any) -> None:
    """Заменяет `path` файлом с правами `0600` только после полной записи `value` на диск."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=path.parent, encoding="utf-8", delete=False) as handle:
            temporary = Path(handle.name)
            os.chmod(temporary, 0o600)
            json.dump(value, handle, ensure_ascii=False)
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


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _output(args: list[str]) -> str | None:
    """stdout команды с кодом 0; иначе, без программы или по таймауту — `None`."""
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=3, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


def _hyprland() -> str | None:
    output = _output(["hyprctl", "version", "-j"])
    try:
        return json.loads(output).get("tag") if output else None
    except (ValueError, AttributeError):
        return None


def about(
    os_release: Path = Path("/etc/os-release"),
    cpuinfo: Path = Path("/proc/cpuinfo"),
    meminfo: Path = Path("/proc/meminfo"),
) -> dict[str, Any]:
    """`{os, kernel, hostname, cpu, memoryGb, hyprland, quickshell}`."""
    name = re.search(r'^PRETTY_NAME="?([^"\n]*)"?', _read_text(os_release), re.M)
    cpu = re.search(r"^model name\s*:\s*(.+)$", _read_text(cpuinfo), re.M)
    memory = re.search(r"^MemTotal:\s+(\d+) kB", _read_text(meminfo), re.M)
    quickshell = _output(["qs", "--version"])
    return {
        "os": name.group(1) if name else None,
        "kernel": platform.release(),
        "hostname": socket.gethostname(),
        "cpu": cpu.group(1).strip() if cpu else None,
        "memoryGb": round(int(memory.group(1)) / 1048576, 1) if memory else None,
        "hyprland": _hyprland(),
        "quickshell": quickshell.strip().splitlines()[0] if quickshell and quickshell.strip() else None,
    }
