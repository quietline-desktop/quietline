"""Данные оболочки: закреплённые приложения, язык и регион, ограничение анимаций и сводка «О системе».

Закрепления хранятся в `pins.json` вида `{"version": 1, "pinned": [desktop ID, …]}`.
Запись атомарная: новый файл с правами `0600` пишется рядом и заменяет старый, поэтому
ошибка записи оставляет прежний список.

Язык и регион — `region.json` вида `{"version": 1, "language", "clock", "date", "barDate", "layouts",
"toggle"}`; `barDate` — дата на панели: `short` («Пн 2 нояб.»), `numeric` (дата по `date`),
`weekday` (день недели и дата по `date`). Сохранение region также обновляет `locale.conf` (строка `LANG`, остальные строки
файла сохраняются) и `quietline/keyboard.lua` с раскладками для Hyprland. Тексты уведомлений
`quietline-shell` — `NOTIFICATION_TEXTS` на языке из region.

Мониторы — `display.json` вида `{"version": 2, "monitors": {"<монитор>": {"mode", "position", "scale",
"transform", "vrr"}}}` (любое поле может отсутствовать), где монитор — правило вывода Hyprland
(`desc:<описание>` или имя разъёма); версия 1 `{"scales": {"<монитор>": <масштаб>}}` читается как
масштабы. Рядом пишется `display.lua`, который читает конфигурация Hyprland Quietline.

Мышь, тачпад и повтор клавиш — `input.json` вида `{"version": 1, "pointerSpeed", "acceleration",
"naturalScroll", "scrollSpeed", "leftHanded", "tapToClick", "touchpadNaturalScroll",
"disableWhileTyping", "touchpadScrollSpeed", "repeatDelay", "repeatRate", "numlock"}`; рядом пишется
`input.lua` с таблицей раздела `input` Hyprland.

Сроки простоя — `idle.json` вида `{"version": 1, "lock", "screenOff", "suspend"}` в минутах
(0 — никогда); рядом пишется `hypridle.conf`, с которым конфигурация Hyprland Quietline запускает hypridle.

Оформление — `appearance.json` вида `{"version": 1, "theme", "cursor", "cursorSize", "batteryPercent",
"dockAutohide"}`: тема окружения и цвет указателя (`dark` | `light`), размер указателя (24, 36 или 48),
процент заряда на панели (`off` | `beside` — рядом с батареей | `inside` — внутри значка), прячется
ли док (`true` | `false`). Рядом пишется
`appearance.lua` для конфигурации Hyprland. Только стандартная библиотека.
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
BAR_DATES = ("short", "numeric", "weekday")
LAYOUTS = ("us", "ru")
TOGGLES = ("grp:lalt_lshift_toggle", "grp:alt_shift_toggle", "grp:ctrl_shift_toggle", "grp:caps_toggle")

_REGION_FIELDS = ("language", "clock", "date", "barDate", "layouts", "toggle")
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
        "barDate": "short",
        "layouts": list(LAYOUTS),
        "toggle": TOGGLES[0],
    }


# Тексты уведомлений `quietline-shell`; одни ключи и подстановки в обоих языках.
NOTIFICATION_TEXTS: dict[str, dict[str, str]] = {
    "ru": {
        "capture_failed": "Не удалось снять экран",
        "save_failed": "Не удалось сохранить снимок",
        "copy_failed": "Снимок сохранён, но не скопирован в буфер",
        "screenshot_saved": "Снимок экрана сохранён и скопирован",
        "editor_failed": "Не удалось открыть редактор снимка",
        "lock_failed": "Не удалось заблокировать сеанс",
        "app_in_background": "«{app}» продолжает работать в фоне",
        "app_in_background_hint": "Super+Shift+Q завершит его принудительно.",
        "app_unnamed": "Приложение",
    },
    "en": {
        "capture_failed": "Could not take a screenshot",
        "save_failed": "Could not save the screenshot",
        "copy_failed": "Screenshot saved but not copied",
        "screenshot_saved": "Screenshot saved and copied",
        "editor_failed": "Could not open the screenshot editor",
        "lock_failed": "Could not lock the session",
        "app_in_background": "“{app}” keeps running in the background",
        "app_in_background_hint": "Super+Shift+Q will force it to quit.",
        "app_unnamed": "Application",
    },
}


def notification_text(key: str, **values: str) -> str:
    """Текст уведомления на языке из `region.json`; файл повреждён или не читается — язык по `LANG`."""
    lang = os.environ.get("LANG")
    try:
        language = load_region(default_region_path(), lang)["language"]
    except (ValueError, OSError):
        language = default_region(lang)["language"]
    return NOTIFICATION_TEXTS[language][key].format(**values)


def validated_region(data: object, current: dict[str, Any]) -> dict[str, Any]:
    """`current` с применёнными полями из `data`; неизвестное поле или значение — `ValueError`."""
    if not isinstance(data, dict):
        raise ValueError("region must be a JSON object")
    unknown = sorted(str(key) for key in data if key not in _REGION_FIELDS)
    if unknown:
        raise ValueError(f"unknown region field: {', '.join(unknown)}")
    base = {"barDate": BAR_DATES[0], **current}
    result = {key: (list(base[key]) if key == "layouts" else base[key]) for key in _REGION_FIELDS}
    choices = {"language": LANGUAGES, "clock": CLOCKS, "date": DATES, "barDate": BAR_DATES, "toggle": TOGGLES}
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
    layout = ",".join(region["layouts"])
    return _hyprctl_eval(f'hl.config({{ input = {{ kb_layout = "{layout}", kb_options = "{region["toggle"]}" }} }})')


def _locale_conf(existing: str, language: str) -> str | None:
    """`existing` с заменой каждой строки `LANG`; без неё строка дописывается в конец.

    `None`, если в файле уже есть строки `LANG` и все они совпадают с нужной.
    """
    line = f"LANG={_LOCALES[language]}"
    lines = existing.splitlines()
    positions = [index for index, item in enumerate(lines) if item.startswith("LANG=")]
    if positions and all(lines[index] == line for index in positions):
        return None
    for index in positions:
        lines[index] = line
    if not positions:
        lines.append(line)
    return "\n".join(lines) + "\n"


def save_region(path: Path, region: dict[str, Any], config_home: Path) -> None:
    """Пишет `config_home/locale.conf` (только при другой строке `LANG`), `config_home/quietline/keyboard.lua`
    и последним атомарно `region.json`: при сбое записи прежние настройки остаются в силе."""
    checked = validated_region(region, region)
    locale_path = config_home / "locale.conf"
    try:
        existing = locale_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        existing = ""
    locale_text = _locale_conf(existing, checked["language"])
    if locale_text is not None:
        _atomic_write_text(locale_path, locale_text)
    _atomic_write_text(config_home / "quietline" / "keyboard.lua", keyboard_lua(checked))
    atomic_write_json(path, {"version": 1, **checked})


# Монитор в правиле Hyprland: `desc:<описание>` без кавычек, обратной косой черты и управляющих
# символов (строка попадает в Lua-литерал) или имя разъёма вида `eDP-1`.
_DISPLAY_OUTPUT = re.compile(r'desc:[^"\\\x00-\x1f\x7f]{1,200}|[A-Za-z0-9_.-]{1,64}')
# Режим монитора `ШИРИНАxВЫСОТА@ЧАСТОТА`, как его принимает `hl.monitor`.
_DISPLAY_MODE = re.compile(r"[1-9][0-9]{1,4}x[1-9][0-9]{1,4}@[0-9]{1,3}(\.[0-9]{1,3})?")
SCALE_MIN = 0.5
SCALE_MAX = 4.0
DISPLAY_POSITIONS = ("auto-left", "auto-right", "auto-up", "auto-down")
# Поля монитора в порядке записи в `display.lua` и правило Hyprland.
_DISPLAY_FIELDS = ("mode", "position", "scale", "transform", "vrr")


def default_display_path() -> Path:
    """`$XDG_CONFIG_HOME/quietline/display.json`, без переменной — `~/.config/quietline/display.json`."""
    directory = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(directory) / "quietline" / "display.json"


def _checked_output(output: object) -> str:
    if not isinstance(output, str) or not _DISPLAY_OUTPUT.fullmatch(output):
        raise ValueError(f"invalid monitor: {output!r}")
    return output


def _checked_scale(scale: object) -> float:
    if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not SCALE_MIN <= scale <= SCALE_MAX:
        raise ValueError(f"scale must be a number from {SCALE_MIN} to {SCALE_MAX} or \"auto\": {scale!r}")
    return float(scale)


def _checked_choice(name: str, value: object, choices: range) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in choices:
        raise ValueError(f"{name} must be an integer from {choices.start} to {choices.stop - 1} or \"auto\": {value!r}")
    return value


def _checked_monitor_field(name: str, value: object) -> Any:
    """Проверенное значение поля монитора; неизвестное поле или значение — `ValueError`."""
    match name:
        case "scale":
            return _checked_scale(value)
        case "mode":
            if not isinstance(value, str) or not _DISPLAY_MODE.fullmatch(value):
                raise ValueError(f"mode must look like 2560x1440@74.96 or be \"auto\": {value!r}")
            return value
        case "position":
            if value not in DISPLAY_POSITIONS:
                raise ValueError(f"position must be one of auto, {', '.join(DISPLAY_POSITIONS)}: {value!r}")
            return value
        case "transform":
            return _checked_choice("transform", value, range(4))
        case "vrr":
            return _checked_choice("vrr", value, range(3))
    raise ValueError(f"unknown monitor field: {name}")


def _checked_monitor(record: object) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError(f"monitor settings must be an object: {record!r}")
    return {name: _checked_monitor_field(name, value) for name, value in record.items()}


def load_display(path: Path) -> dict[str, dict[str, Any]]:
    """Настройки мониторов из файла: «монитор → поля»; без файла — пусто. Версия 1 (только
    масштабы) читается как поле `scale`. Повреждённый файл — `ValueError`, файл не меняется."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as error:
        raise ValueError(f"cannot read display settings from {path}") from error
    if isinstance(data, dict) and data.get("version") == 1 and isinstance(data.get("scales"), dict):
        monitors = {output: {"scale": scale} for output, scale in data["scales"].items()}
    elif isinstance(data, dict) and data.get("version") == 2 and isinstance(data.get("monitors"), dict):
        monitors = data["monitors"]
    else:
        raise ValueError(f"unknown display file format in {path}")
    try:
        return {_checked_output(output): _checked_monitor(record) for output, record in monitors.items()}
    except ValueError as error:
        raise ValueError(f"invalid display settings in {path}: {error}") from error


def display_scales(monitors: dict[str, dict[str, Any]]) -> dict[str, float]:
    """Масштабы мониторов, у которых он выбран: «монитор → масштаб»."""
    return {output: record["scale"] for output, record in monitors.items() if "scale" in record}


def updated_display(change: object, monitors: dict[str, dict[str, Any]]) -> tuple[str, dict[str, dict[str, Any]]]:
    """Применяет `{"output", <поля>}` к `monitors`: `(монитор, новые настройки)`. `"auto"`, поворот 0
    и положение `auto` убирают поле; монитор без полей убирается целиком."""
    if not isinstance(change, dict) or "output" not in change or len(change) < 2:
        raise ValueError('display change must be {"output": ..., "<field>": ...} with at least one field')
    output = _checked_output(change["output"])
    record = dict(monitors.get(output, {}))
    for name, value in change.items():
        if name == "output":
            continue
        if name not in _DISPLAY_FIELDS:
            raise ValueError(f"unknown monitor field: {name}")
        if value == "auto" or (name == "transform" and value == 0):
            record.pop(name, None)
        else:
            record[name] = _checked_monitor_field(name, value)
    result = {key: value for key, value in monitors.items() if key != output}
    if record:
        result[output] = record
    return output, result


def _lua_value(value: Any) -> str:
    return f'"{value}"' if isinstance(value, str) else repr(value)


def display_lua(monitors: dict[str, dict[str, Any]]) -> str:
    """Содержимое `display.lua`: таблица «монитор → поля правила» для конфигурации Hyprland."""
    lines = []
    for output, record in sorted(monitors.items()):
        fields = ", ".join(f"{name} = {_lua_value(record[name])}" for name in _DISPLAY_FIELDS if name in record)
        lines.append(f'    ["{output}"] = {{ {fields} }},\n')
    return "return {\n" + "".join(lines) + "}\n"


def save_display(path: Path, monitors: dict[str, dict[str, Any]]) -> None:
    """Пишет `display.lua` рядом с `path` и последним атомарно `display.json` версии 2."""
    checked = {_checked_output(output): _checked_monitor(record) for output, record in monitors.items() if record}
    _atomic_write_text(path.with_name("display.lua"), display_lua(checked))
    atomic_write_json(path, {"version": 2, "monitors": checked})


def monitor_rule(output: str, record: dict[str, Any]) -> str:
    """Выражение `hl.monitor` для `hyprctl eval`: все поля монитора, отсутствующие — `preferred`,
    `auto` и масштаб `auto`."""
    checked = _checked_monitor(record)
    scale = repr(checked["scale"]) if "scale" in checked else '"auto"'
    fields = [f'output = "{_checked_output(output)}"', f'mode = "{checked.get("mode", "preferred")}"',
              f'position = "{checked.get("position", "auto")}"', f"scale = {scale}"]
    fields += [f"{name} = {checked[name]}" for name in ("transform", "vrr") if name in checked]
    return "hl.monitor({ " + ", ".join(fields) + " })"


def _hyprctl_eval(expression: str) -> bool:
    """`hyprctl eval EXPRESSION` в работающем Hyprland; `True` только при коде 0. Вне сеанса
    Hyprland, без `hyprctl` и по таймауту — `False`."""
    if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return False
    try:
        result = subprocess.run(["hyprctl", "eval", expression], capture_output=True, text=True,
                                timeout=_HYPRCTL_TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def apply_display(output: str, record: dict[str, Any]) -> bool:
    """Применяет настройки монитора `output` в работающем Hyprland; `True` только при коде 0 `hyprctl`."""
    return _hyprctl_eval(monitor_rule(output, record))


_MODE_TEXT = re.compile(r"([0-9]+)x([0-9]+)@([0-9]+(?:\.[0-9]+)?)Hz")


def display_outputs() -> list[dict[str, Any]]:
    """Подключённые мониторы из `hyprctl monitors -j`: имя, описание, правило (`output`), текущий
    режим, масштаб, поворот, VRR, положение и доступные режимы `{width, height, refresh}` без
    повторов. Вне сеанса Hyprland и при ошибке `hyprctl` — пусто."""
    if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return []
    try:
        result = subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True, text=True,
                                timeout=_HYPRCTL_TIMEOUT, check=False)
        monitors = json.loads(result.stdout) if result.returncode == 0 else []
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return []
    outputs = []
    for monitor in monitors if isinstance(monitors, list) else []:
        if not isinstance(monitor, dict) or not isinstance(monitor.get("name"), str):
            continue
        description = monitor.get("description") or ""
        rule = f"desc:{description}" if description and _DISPLAY_OUTPUT.fullmatch(f"desc:{description}") else monitor["name"]
        modes = []
        for text in monitor.get("availableModes") or []:
            found = _MODE_TEXT.fullmatch(str(text))
            mode = found and {"width": int(found[1]), "height": int(found[2]), "refresh": float(found[3])}
            if mode and mode not in modes:
                modes.append(mode)
        outputs.append({
            "name": monitor["name"], "description": description, "output": rule,
            "width": monitor.get("width"), "height": monitor.get("height"),
            "refreshRate": monitor.get("refreshRate"), "scale": monitor.get("scale"),
            "transform": monitor.get("transform"), "vrr": bool(monitor.get("vrr")),
            "x": monitor.get("x"), "y": monitor.get("y"), "modes": modes,
        })
    return outputs


# Мышь, тачпад и клавиатура: поле → (по умолчанию, допустимые значения). Числа с плавающей точкой —
# диапазон `(от, до)`, целые — `range`, флаги — `bool`. Значения по умолчанию — значения Hyprland.
_INPUT_FIELDS: dict[str, tuple[Any, Any]] = {
    "pointerSpeed": (0.0, (-1.0, 1.0)),
    "acceleration": (True, bool),
    "naturalScroll": (False, bool),
    "scrollSpeed": (1.0, (0.25, 3.0)),
    "leftHanded": (False, bool),
    "tapToClick": (True, bool),
    "touchpadNaturalScroll": (False, bool),
    "disableWhileTyping": (True, bool),
    "touchpadScrollSpeed": (1.0, (0.25, 3.0)),
    "repeatDelay": (600, range(150, 1001)),
    "repeatRate": (25, range(10, 61)),
    "numlock": (False, bool),
}
INPUT_DEFAULTS = {name: default for name, (default, _) in _INPUT_FIELDS.items()}


def default_input_path() -> Path:
    """`$XDG_CONFIG_HOME/quietline/input.json`, без переменной — `~/.config/quietline/input.json`."""
    directory = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(directory) / "quietline" / "input.json"


def _checked_input(values: dict[str, Any]) -> dict[str, Any]:
    """Все поля ввода с допустимыми значениями (дробные округляются до сотых); иначе `ValueError`."""
    result = {}
    for name, (_, allowed) in _INPUT_FIELDS.items():
        value = values.get(name)
        if allowed is bool:
            valid = isinstance(value, bool)
        elif isinstance(allowed, range):
            valid = isinstance(value, int) and not isinstance(value, bool) and value in allowed
        else:
            valid = isinstance(value, (int, float)) and not isinstance(value, bool) and allowed[0] <= value <= allowed[1]
            value = round(float(value), 2) if valid else value
        if not valid:
            raise ValueError(f"invalid {name}: {value!r}")
        result[name] = value
    return result


def load_input(path: Path) -> dict[str, Any]:
    """Настройки ввода из файла; без файла — значения Hyprland по умолчанию. Повреждённый файл — `ValueError`."""
    if not path.exists():
        return dict(INPUT_DEFAULTS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as error:
        raise ValueError(f"cannot read input settings from {path}") from error
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError(f"unknown input file format in {path}")
    try:
        return _checked_input({**INPUT_DEFAULTS, **{key: data[key] for key in INPUT_DEFAULTS if key in data}})
    except ValueError as error:
        raise ValueError(f"invalid input settings in {path}: {error}") from error


def updated_input(change: object, current: dict[str, Any]) -> dict[str, Any]:
    """Применяет часть полей `change` к `current`; неизвестное поле или значение — `ValueError`."""
    if not isinstance(change, dict) or not change:
        raise ValueError("input change must be a non-empty JSON object")
    unknown = set(change) - set(INPUT_DEFAULTS)
    if unknown:
        raise ValueError(f"unknown input fields: {', '.join(sorted(unknown))}")
    return _checked_input({**current, **change})


def _lua_bool(value: bool) -> str:
    return "true" if value else "false"


def input_table(values: dict[str, Any]) -> str:
    """Таблица Lua раздела `input` Hyprland из настроек ввода (ключи с подчёркиванием, как в Lua API)."""
    checked = _checked_input(values)
    touchpad = (f'tap_to_click = {_lua_bool(checked["tapToClick"])}, '
                f'natural_scroll = {_lua_bool(checked["touchpadNaturalScroll"])}, '
                f'disable_while_typing = {_lua_bool(checked["disableWhileTyping"])}, '
                f'scroll_factor = {checked["touchpadScrollSpeed"]!r}')
    return (f'{{ sensitivity = {checked["pointerSpeed"]!r}, '
            f'accel_profile = "{"adaptive" if checked["acceleration"] else "flat"}", '
            f'natural_scroll = {_lua_bool(checked["naturalScroll"])}, scroll_factor = {checked["scrollSpeed"]!r}, '
            f'left_handed = {_lua_bool(checked["leftHanded"])}, repeat_delay = {checked["repeatDelay"]}, '
            f'repeat_rate = {checked["repeatRate"]}, numlock_by_default = {_lua_bool(checked["numlock"])}, '
            f'touchpad = {{ {touchpad} }} }}')


def save_input(path: Path, values: dict[str, Any]) -> None:
    """Пишет `input.lua` рядом с `path` и последним атомарно `input.json`."""
    checked = _checked_input(values)
    _atomic_write_text(path.with_name("input.lua"), f"return {input_table(checked)}\n")
    atomic_write_json(path, {"version": 1, **checked})


def apply_input(values: dict[str, Any]) -> bool:
    """Применяет настройки ввода в работающем Hyprland; `True` только при коде 0 `hyprctl`."""
    return _hyprctl_eval(f"hl.config({{ input = {input_table(values)} }})")


def has_touchpad() -> bool:
    """Есть ли тачпад среди указателей `hyprctl devices -j`; вне Hyprland и при ошибке — `False`."""
    if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return False
    try:
        result = subprocess.run(["hyprctl", "devices", "-j"], capture_output=True, text=True,
                                timeout=_HYPRCTL_TIMEOUT, check=False)
        mice = json.loads(result.stdout).get("mice", []) if result.returncode == 0 else []
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, AttributeError):
        return False
    return any(isinstance(mouse, dict) and "touchpad" in str(mouse.get("name", "")).lower() for mouse in mice)


# Сроки простоя в минутах (0 — никогда) и допустимые значения для «Питания» → «Когда компьютер
# не используется». По умолчанию — сроки файла пакета `hypridle.conf`.
IDLE_DEFAULTS = {"lock": 5, "screenOff": 5, "suspend": 15}
IDLE_CHOICES = {"lock": (1, 2, 5, 10, 15, 30, 0), "screenOff": (1, 2, 5, 10, 15, 30, 0), "suspend": (10, 15, 30, 60, 0)}
# Если экран гаснет в один срок с блокировкой — на столько секунд позже: сначала виден экран блокировки.
SCREEN_OFF_AFTER_LOCK = 30
_HYPRIDLE_GENERAL = """general {
    lock_cmd = quietline-shell lock
    before_sleep_cmd = loginctl lock-session
    after_sleep_cmd = hyprctl dispatch 'hl.dsp.dpms({ action = "enable" })'
    inhibit_sleep = 3
    ignore_dbus_inhibit = false
    ignore_systemd_inhibit = false
    ignore_wayland_inhibit = false
}
"""


def default_idle_path() -> Path:
    """`$XDG_CONFIG_HOME/quietline/idle.json`, без переменной — `~/.config/quietline/idle.json`."""
    directory = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(directory) / "quietline" / "idle.json"


def _checked_idle(values: dict[str, Any]) -> dict[str, int]:
    result = {}
    for key, choices in IDLE_CHOICES.items():
        value = values.get(key)
        if isinstance(value, bool) != isinstance(choices[0], bool) or value not in choices:
            raise ValueError(f"{key} must be one of {', '.join(map(str, choices))} minutes: {value!r}")
        result[key] = value
    return result


def load_idle(path: Path) -> dict[str, int]:
    """Сроки простоя из файла; без файла — сроки по умолчанию. Повреждённый файл — `ValueError`."""
    if not path.exists():
        return dict(IDLE_DEFAULTS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as error:
        raise ValueError(f"cannot read idle settings from {path}") from error
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError(f"unknown idle file format in {path}")
    try:
        return _checked_idle({**IDLE_DEFAULTS, **{key: data[key] for key in IDLE_DEFAULTS if key in data}})
    except ValueError as error:
        raise ValueError(f"invalid idle settings in {path}: {error}") from error


def updated_idle(change: object, current: dict[str, int]) -> dict[str, int]:
    """Применяет часть полей `change` к `current`; неизвестное поле или срок — `ValueError`."""
    if not isinstance(change, dict) or not change:
        raise ValueError("idle change must be a non-empty JSON object")
    unknown = set(change) - set(IDLE_DEFAULTS)
    if unknown:
        raise ValueError(f"unknown idle fields: {', '.join(sorted(unknown))}")
    return _checked_idle({**current, **change})


def hypridle_conf(values: dict[str, int]) -> str:
    """`hypridle.conf` со сроками простоя: общий блок как у файла пакета, слушатели только для
    сроков, отличных от «никогда»; сон — только от своей батареи (`quietline-shell idle suspend`)."""
    checked = _checked_idle(values)
    parts = ["# Quietline: простой и сон по срокам из «Настроек» → «Питание»; файл пишет quietline-shell idle settings.\n",
             _HYPRIDLE_GENERAL]
    if checked["lock"]:
        parts.append(f"listener {{\n    timeout = {checked['lock'] * 60}\n    on-timeout = loginctl lock-session\n}}\n")
    if checked["screenOff"]:
        seconds = checked["screenOff"] * 60 + (SCREEN_OFF_AFTER_LOCK if checked["screenOff"] == checked["lock"] else 0)
        parts.append(f"listener {{\n    timeout = {seconds}\n"
                     "    on-timeout = hyprctl dispatch 'hl.dsp.dpms({ action = \"disable\" })'\n"
                     "    on-resume = hyprctl dispatch 'hl.dsp.dpms({ action = \"enable\" })'\n}\n")
    if checked["suspend"]:
        parts.append(f"listener {{\n    timeout = {checked['suspend'] * 60}\n    on-timeout = quietline-shell idle suspend\n}}\n")
    return "\n".join(parts)


def save_idle(path: Path, values: dict[str, int]) -> None:
    """Пишет `hypridle.conf` рядом с `path` и последним атомарно `idle.json`."""
    checked = _checked_idle(values)
    _atomic_write_text(path.with_name("hypridle.conf"), hypridle_conf(checked))
    atomic_write_json(path, {"version": 1, **checked})


def restart_hypridle(conf: Path) -> bool:
    """Перезапускает hypridle с файлом `conf` в своей сессии; вне сеанса Hyprland — `False`."""
    if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return False
    _succeeds(["pkill", "-x", "hypridle"], _HYPRCTL_TIMEOUT)
    try:
        subprocess.Popen(["hypridle", "-c", str(conf)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        return False
    return True


_TIMEDATECTL_TIMEOUT = 10
_TIMEZONE = re.compile(r"[A-Za-z0-9_+-]+(/[A-Za-z0-9_+-]+){0,2}")


def _timedatectl(*args: str) -> str:
    """Вывод `timedatectl --no-ask-password ARGS`; ненулевой код — `RuntimeError` с текстом ошибки."""
    result = subprocess.run(["timedatectl", "--no-ask-password", *args], capture_output=True, text=True,
                            timeout=_TIMEDATECTL_TIMEOUT, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"timedatectl {args[0]} failed")
    return result.stdout


def time_state() -> dict[str, Any]:
    """Часовой пояс и синхронизация времени по сети: `{"timezone", "ntp"}`."""
    fields = dict(line.split("=", 1) for line in _timedatectl("show", "-p", "Timezone", "-p", "NTP").splitlines() if "=" in line)
    return {"timezone": fields.get("Timezone", ""), "ntp": fields.get("NTP") == "yes"}


def time_zones() -> list[str]:
    """Часовые пояса системы (`timedatectl list-timezones`)."""
    return [line.strip() for line in _timedatectl("list-timezones").splitlines() if line.strip()]


def set_time(change: object) -> dict[str, Any]:
    """`{"timezone": "<пояс>"}` или `{"ntp": bool}` через `timedatectl`; ответ — новое состояние.
    Пояс должен быть в списке системы; ошибка `timedatectl` (нет прав polkit) — `RuntimeError`."""
    if isinstance(change, dict) and set(change) == {"timezone"}:
        zone = change["timezone"]
        if not isinstance(zone, str) or not _TIMEZONE.fullmatch(zone) or zone not in time_zones():
            raise ValueError(f"unknown time zone: {zone!r}")
        _timedatectl("set-timezone", zone)
    elif isinstance(change, dict) and set(change) == {"ntp"} and isinstance(change["ntp"], bool):
        _timedatectl("set-ntp", "true" if change["ntp"] else "false")
    else:
        raise ValueError('time change must be {"timezone": NAME} or {"ntp": true | false}')
    return time_state()


# Приложения по умолчанию: категория → типы MIME. Кандидаты ищутся по первому типу, выбор пишется
# для всех типов категории.
DEFAULT_APP_CATEGORIES = {
    "browser": ("x-scheme-handler/http", "x-scheme-handler/https", "text/html"),
    "files": ("inode/directory",),
    "mail": ("x-scheme-handler/mailto",),
    "text": ("text/plain",),
    "images": ("image/png", "image/jpeg", "image/webp", "image/gif"),
    "video": ("video/mp4", "video/x-matroska", "video/webm"),
    "music": ("audio/mpeg", "audio/flac", "audio/ogg"),
    "pdf": ("application/pdf",),
}
_DESKTOP_FILE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.+-]{0,199}\.desktop")


def _application_dirs() -> list[Path]:
    """Каталоги desktop-файлов по порядку старшинства: `$XDG_DATA_HOME`, затем `$XDG_DATA_DIRS`."""
    home = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    dirs = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    return [Path(directory) / "applications" for directory in [home, *dirs.split(":")] if directory]


def _desktop_entry(path: Path) -> dict[str, str]:
    """Ключи раздела `[Desktop Entry]` desktop-файла; нечитаемый файл — пусто."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return {}
    entry, inside = {}, False
    for line in lines:
        if line.startswith("["):
            inside = line.strip() == "[Desktop Entry]"
        elif inside and "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            entry.setdefault(key.strip(), value.strip())
    return entry


def default_app_candidates(language: str = "en") -> dict[str, list[dict[str, str]]]:
    """Видимые приложения для каждой категории: `{"id", "name"}` по имени. Desktop-файл из каталога
    со старшинством выше закрывает файл с тем же ID ниже; имя — на `language`, если оно есть."""
    entries: dict[str, dict[str, str]] = {}
    for directory in _application_dirs():
        for path in sorted(directory.glob("**/*.desktop")) if directory.is_dir() else []:
            desktop_id = str(path.relative_to(directory)).replace("/", "-")
            if _DESKTOP_FILE.fullmatch(desktop_id) and desktop_id not in entries:
                entries[desktop_id] = _desktop_entry(path)
    result: dict[str, list[dict[str, str]]] = {category: [] for category in DEFAULT_APP_CATEGORIES}
    for desktop_id, entry in entries.items():
        if entry.get("Type", "Application") != "Application" or "true" in (entry.get("NoDisplay"), entry.get("Hidden")):
            continue
        mimes = set(filter(None, entry.get("MimeType", "").split(";")))
        name = entry.get(f"Name[{language}]") or entry.get("Name") or desktop_id.removesuffix(".desktop")
        for category, types in DEFAULT_APP_CATEGORIES.items():
            if types[0] in mimes:
                result[category].append({"id": desktop_id, "name": name})
    for apps in result.values():
        apps.sort(key=lambda app: app["name"].casefold())
    return result


def _default_app(mime: str) -> str | None:
    try:
        result = subprocess.run(["xdg-mime", "query", "default", mime], capture_output=True, text=True,
                                timeout=_HYPRCTL_TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and _DESKTOP_FILE.fullmatch(value) else None


def default_apps(language: str = "en") -> dict[str, Any]:
    """Категории приложений по умолчанию: `{"categories": [{"id", "current", "apps"}]}`; текущее —
    `xdg-mime query default` первого типа категории (нет — `null`)."""
    candidates = default_app_candidates(language)
    return {"categories": [{"id": category, "current": _default_app(types[0]), "apps": candidates[category]}
                           for category, types in DEFAULT_APP_CATEGORIES.items()]}


def mimeapps_with(text: str, mimes: tuple[str, ...], app: str) -> str:
    """Текст `mimeapps.list`, где в `[Default Applications]` каждый тип из `mimes` указывает на `app`;
    остальные строки и разделы сохраняются, раздела нет — он дописывается в конец."""
    lines = text.splitlines()
    try:
        start = lines.index("[Default Applications]") + 1
    except ValueError:
        lines += ([""] if lines else []) + ["[Default Applications]"]
        start = len(lines)
    end = next((index for index in range(start, len(lines)) if lines[index].startswith("[")), len(lines))
    kept = [line for line in lines[start:end] if line.split("=", 1)[0].strip() not in mimes]
    return "\n".join(lines[:start] + [f"{mime}={app};" for mime in mimes] + kept + lines[end:]) + "\n"


def set_default_app(change: object, config_home: Path, language: str = "en") -> dict[str, Any]:
    """`{"category", "app"}`: приложение из кандидатов категории становится приложением по умолчанию
    для всех её типов в `config_home/mimeapps.list`; ответ — новое состояние."""
    if not isinstance(change, dict) or set(change) != {"category", "app"} or change["category"] not in DEFAULT_APP_CATEGORIES:
        raise ValueError('default app change must be {"category": ..., "app": "<id>.desktop"}')
    category, app = change["category"], change["app"]
    if app not in [item["id"] for item in default_app_candidates(language)[category]]:
        raise ValueError(f"{app!r} cannot open {category}")
    path = config_home / "mimeapps.list"
    try:
        existing = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        existing = ""
    _atomic_write_text(path, mimeapps_with(existing, DEFAULT_APP_CATEGORIES[category], app))
    return default_apps(language)


APPEARANCE_DEFAULTS = {"theme": "dark", "cursor": "dark", "cursorSize": 24, "batteryPercent": "off", "dockAutohide": True}
_APPEARANCE_CHOICES = {"theme": ("dark", "light"), "cursor": ("dark", "light"), "cursorSize": (24, 36, 48),
                       "batteryPercent": ("off", "beside", "inside"), "dockAutohide": (True, False)}
CURSOR_THEMES = {"dark": "capitaine-cursors", "light": "capitaine-cursors-light"}
_GSETTINGS_TIMEOUT = 5


def default_appearance_path() -> Path:
    """`$XDG_CONFIG_HOME/quietline/appearance.json`, без переменной — `~/.config/quietline/appearance.json`."""
    directory = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(directory) / "quietline" / "appearance.json"


def _checked_appearance(values: dict[str, Any]) -> dict[str, Any]:
    """Все поля с допустимыми значениями (`True` не считается числом 1); иначе `ValueError` с именем поля."""
    result = {}
    for key, choices in _APPEARANCE_CHOICES.items():
        value = values.get(key)
        if isinstance(value, bool) != isinstance(choices[0], bool) or value not in choices:
            raise ValueError(f"{key} must be one of {', '.join(map(str, choices))}: {value!r}")
        result[key] = value
    return result


def load_appearance(path: Path) -> dict[str, Any]:
    """Оформление из файла; без файла — значения по умолчанию. Повреждённый файл — `ValueError`."""
    if not path.exists():
        return dict(APPEARANCE_DEFAULTS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as error:
        raise ValueError(f"cannot read appearance settings from {path}") from error
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError(f"unknown appearance file format in {path}")
    try:
        return _checked_appearance({**APPEARANCE_DEFAULTS, **{key: data[key] for key in APPEARANCE_DEFAULTS if key in data}})
    except ValueError as error:
        raise ValueError(f"invalid appearance settings in {path}: {error}") from error


def updated_appearance(change: object, current: dict[str, Any]) -> dict[str, Any]:
    """Применяет часть полей `change` к `current`; неизвестное поле или значение — `ValueError`."""
    if not isinstance(change, dict) or not change:
        raise ValueError("appearance change must be a non-empty JSON object")
    unknown = set(change) - set(APPEARANCE_DEFAULTS)
    if unknown:
        raise ValueError(f"unknown appearance fields: {', '.join(sorted(unknown))}")
    return _checked_appearance({**current, **change})


def appearance_lua(values: dict[str, Any]) -> str:
    """Содержимое `appearance.lua`: таблица оформления для конфигурации Hyprland."""
    checked = _checked_appearance({**APPEARANCE_DEFAULTS, **values})
    return (f'return {{ theme = "{checked["theme"]}", cursor = "{checked["cursor"]}", '
            f'cursor_size = {checked["cursorSize"]} }}\n')


def save_appearance(path: Path, values: dict[str, Any]) -> None:
    """Пишет `appearance.lua` рядом с `path` и последним атомарно `appearance.json`."""
    checked = _checked_appearance(values)
    _atomic_write_text(path.with_name("appearance.lua"), appearance_lua(checked))
    atomic_write_json(path, {"version": 1, **checked})


def _succeeds(args: list[str], timeout: float) -> bool:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def apply_appearance(values: dict[str, Any]) -> bool:
    """Применяет оформление сразу: схему приложений в gsettings (`color-scheme`, `gtk-theme` для
    GTK 3), затем в работающем Hyprland перечитывает конфигурацию (рамки, тени, заголовки) и меняет
    указатель. `True` только если все шаги вернули код 0; вне сеанса Hyprland — `False` после gsettings."""
    checked = _checked_appearance({**APPEARANCE_DEFAULTS, **values})
    light = checked["theme"] == "light"
    interface = "org.gnome.desktop.interface"
    steps = [
        ["gsettings", "set", interface, "color-scheme", "prefer-light" if light else "prefer-dark"],
        ["gsettings", "set", interface, "gtk-theme", "Adwaita" if light else "Adwaita-dark"],
    ]
    applied = all([_succeeds(step, _GSETTINGS_TIMEOUT) for step in steps])
    if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return False
    for step in (["hyprctl", "reload", "config-only"],
                 ["hyprctl", "setcursor", CURSOR_THEMES[checked["cursor"]], str(checked["cursorSize"])]):
        applied = _succeeds(step, _HYPRCTL_TIMEOUT) and applied
    return applied


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


def _version(text: str | None) -> str | None:
    """Номер версии `X.Y[.Z]` из строки версии программы; без номера — первая строка, пусто — `None`."""
    if not text or not text.strip():
        return None
    number = re.search(r"\d+\.\d+(?:\.\d+)*", text)
    return number.group(0) if number else text.strip().splitlines()[0]


def _hyprland() -> str | None:
    output = _output(["hyprctl", "version", "-j"])
    try:
        return _version(json.loads(output).get("tag")) if output else None
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
        "quickshell": _version(quickshell),
    }
