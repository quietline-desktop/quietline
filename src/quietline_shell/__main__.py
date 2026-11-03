"""CLI `quietline-shell`: данные для оболочки Quickshell одной строкой JSON в stdout.

- `pins [--set JSON] [--path PATH]` — `{"pinned": [...]}`; с `--set` список сначала
  проверяется и атомарно записывается;
- `region [--set JSON] [--path PATH]` — `{"language", "clock", "date", "barDate", "layouts", "toggle"}`:
  язык, форматы времени и даты, вид даты на панели, раскладки и сочетание переключения; с `--set` частичное
  обновление проверяется и пишется в `region.json`, а `locale.conf` и `quietline/keyboard.lua`
  — в каталог на два уровня выше `PATH` (`PATH/../../`; по умолчанию `$XDG_CONFIG_HOME`), раскладки применяются в Hyprland,
  в ответ добавляется `"applied": true | false`;
- `display [--set JSON] [--path PATH]` — `{"monitors": {"<монитор>": {"mode", "position", "scale",
  "transform", "vrr"}}, "scales": {"<монитор>": <масштаб>}, "outputs": [...]}`: настройки мониторов,
  выбранные в «Настройках» (монитор — `desc:<описание>` или имя разъёма; любое поле может
  отсутствовать), их масштабы и подключённые мониторы из Hyprland (`name`, `description`, `output`,
  `width`, `height`, `refreshRate`, `scale`, `transform`, `vrr`, `x`, `y`, `modes: [{width, height,
  refresh}]`; вне Hyprland — `[]`); с `--set {"output", <поля>}` поля (`scale` 0.5–4, `mode`
  `"WxH@R"`, `position` `auto-left|auto-right|auto-up|auto-down`, `transform` 0–3, `vrr` 0–2;
  `"auto"` убирает поле) пишутся в `display.json` и `display.lua` рядом с ним, монитор применяется
  в Hyprland, в ответ добавляется `"applied": true | false`;
- `input [--set JSON] [--path PATH]` — `{"pointerSpeed", "acceleration", "naturalScroll", "scrollSpeed",
  "leftHanded", "tapToClick", "touchpadNaturalScroll", "disableWhileTyping", "touchpadScrollSpeed",
  "repeatDelay", "repeatRate", "numlock", "touchpad"}`: мышь, тачпад и повтор клавиш (скорость
  указателя −1…1, скорости прокрутки 0.25–3, задержка повтора 150–1000 мс, частота 10–60 в секунду),
  `touchpad` — есть ли тачпад; с `--set` часть полей проверяется и пишется в `input.json` и
  `input.lua` рядом с ним, применяется в Hyprland, в ответ добавляется `"applied": true | false`;
- `appearance [--set JSON] [--path PATH]` — `{"theme", "cursor", "cursorSize", "batteryPercent"}`:
  тема окружения и цвет указателя (`dark` | `light`), размер указателя (24, 36, 48), процент
  заряда на панели (`off` | `beside` | `inside`); с `--set` часть полей
  проверяется и пишется в `appearance.json` и `appearance.lua` рядом с ним, схема приложений
  меняется в gsettings, в Hyprland перечитывается конфигурация и меняется указатель; в ответ
  добавляется `"applied": true | false`;
- `greeter [--remember JSON] [--path PATH]` — данные экрана входа `{users: [{name, display}],
  sessions: [{id, name, command, desktopNames}], last: {user, session}}`; с `--remember
  {"user", "session"}` выбор проверяется и пишется в `greeter.json` (по умолчанию
  `$XDG_STATE_HOME/quietline/greeter.json`), ответ — `{"user", "session"}`;
- `motion` — `{"reducedMotion": true | false}`;
- `about` — `{os, kernel, hostname, cpu, memoryGb, hyprland, quickshell}` для страницы
  «О системе» (`hyprland` и `quickshell` — номера версий вида `0.55.1`), недоступное значение — `null`;
- `lock` — `{"locked": true}`: экран блокировки запущен или уже работал;
- `session logout|reboot|poweroff [--timeout S] [--force]` — корректно закрывает окна и выполняет
  действие: `{"action", "done": true}` или `{"action", "done": false, "remaining": [{"app", "title"}]}`;
  с `--force` — выполняет действие сразу, не закрывая окна;
- `app quit [--pid P]` — корректный выход из приложения активного окна (или процесса `P`):
  `{"closed", "remaining", "background"}` (с `background` — ещё `app`); с `--notify` об оставшемся
  в фоне процессе сообщает уведомление; `app kill --pid P` — `{"killed": P}`;
- `screenshot output|region` — снимок монитора с фокусом `{"path", "copied": true}` или
  область в Satty `{"started": true}` / `{"cancelled": true}`; итог сообщает уведомление;
- `clipboard store|list|restore|delete|image|wipe|pause` — история буфера сеанса:
  `store` читает запись из stdin, `list` — `{"entries": [{"id", "kind", "preview"}], "paused"}`,
  `image --id ID` — `{"path"}`, остальные — `{"ok": true}`;
- `idle settings [--set JSON] [--path PATH]` — `{"lock", "screenOff", "suspend"}`: сроки блокировки,
  отключения экрана и сна от батареи в минутах (0 — никогда); с `--set` часть полей проверяется и
  пишется в `idle.json` и `hypridle.conf` рядом с ним, hypridle перезапускается с этим файлом, в ответ
  добавляется `"applied": true | false`;
- `idle suspend` — сон после долгого простоя (зовёт hypridle): `{"suspended": true}` или
  `{"suspended": false, "reason": "ac" | "no-battery"}` — от зарядки и без своей батареи сна нет;
- `files QUERY [--limit N]` — файлы домашнего каталога `{"files": [path…], "indexedAt"}`;
  `files --update` — перестроить базу, `{"indexedAt"}`;
- `network ACTION …` — NetworkManager: состояние, профили объекта, Wi-Fi, контрольные
  точки; подкоманды и их ответы — в docstring `quietline_shell.network`.

Ошибка — `{"error": "<текст>"}` в stdout и код выхода 1; у ошибки формы сетевого профиля
ещё `"field"` с полем формы. Неверные аргументы — код 2.
"""

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from quietline_shell import capture, clipboard, network, search, session
from quietline_shell.config import (
    about, apply_appearance, apply_display, apply_keyboard, default_appearance_path, default_display_path, display_outputs,
    display_scales, default_idle_path, load_idle, updated_idle, save_idle, restart_hypridle, default_input_path, load_input, updated_input, save_input, apply_input, has_touchpad,
    default_pins_path, default_region_path, load_appearance, load_display, load_pins, load_region, reduced_motion,
    notification_text, save_appearance, save_display, save_pins, save_region, updated_appearance, updated_display,
    validated_region,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quietline-shell", description="Quietline shell preferences.")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    pins = commands.add_parser("pins", help="print the pinned dock applications as JSON")
    pins.add_argument("--set", dest="new_pins", metavar="JSON", help="save this JSON list of desktop IDs first")
    pins.add_argument("--path", type=Path, help="pins file (default: $XDG_CONFIG_HOME/quietline/pins.json)")
    region = commands.add_parser("region", help="print the language and region settings as JSON")
    region.add_argument("--set", dest="new_region", metavar="JSON", help="apply this JSON object of fields first")
    region.add_argument("--path", type=Path, help="region file (default: $XDG_CONFIG_HOME/quietline/region.json); locale.conf and quietline/keyboard.lua are written two directories above it")
    display = commands.add_parser("display", help="print the monitor settings and connected monitors as JSON")
    display.add_argument("--set", dest="change", metavar="JSON", help='apply {"output": ..., "scale" | "mode" | "position" | "transform" | "vrr": VALUE | "auto"} first')
    display.add_argument("--path", type=Path, help="display file (default: $XDG_CONFIG_HOME/quietline/display.json); display.lua is written next to it")
    pointer = commands.add_parser("input", help="print the mouse, touchpad and key repeat settings as JSON")
    pointer.add_argument("--set", dest="change", metavar="JSON", help="apply this JSON object of fields first")
    pointer.add_argument("--path", type=Path, help="input file (default: $XDG_CONFIG_HOME/quietline/input.json); input.lua is written next to it")
    appearance = commands.add_parser("appearance", help="print the theme and pointer settings as JSON")
    appearance.add_argument("--set", dest="change", metavar="JSON", help='apply {"theme", "cursor", "cursorSize", "batteryPercent"} (any of them) first')
    appearance.add_argument("--path", type=Path, help="appearance file (default: $XDG_CONFIG_HOME/quietline/appearance.json); appearance.lua is written next to it")
    greeter = commands.add_parser("greeter", help="print the users and sessions for the login screen as JSON")
    greeter.add_argument("--remember", metavar="JSON", help="store this {user, session} choice instead")
    greeter.add_argument("--path", type=Path, help="state file (default: $XDG_STATE_HOME/quietline/greeter.json)")
    commands.add_parser("motion", help="print whether animations should be reduced")
    commands.add_parser("about", help="print system facts for the settings window")
    commands.add_parser("lock", help="start the lock screen unless it is already running")
    ending = commands.add_parser("session", help="close all windows, then log out, reboot or power off")
    ending.add_argument("action", choices=session.SESSION_ACTIONS)
    ending.add_argument("--timeout", type=float, default=session.CLOSE_TIMEOUT, help="seconds to wait for windows to close")
    ending.add_argument("--force", action="store_true", help="act at once without closing windows")
    app = commands.add_parser("app", help="quit or kill an application")
    app_actions = app.add_subparsers(dest="action", required=True, metavar="ACTION")
    quit_parser = app_actions.add_parser("quit", help="close the windows of the active application (or --pid) gracefully")
    quit_parser.add_argument("--pid", type=int)
    quit_parser.add_argument("--timeout", type=float, default=session.QUIT_TIMEOUT, help="seconds to wait for windows to close")
    quit_parser.add_argument("--notify", action="store_true", help="send a notification if the process stays in the background")
    app_actions.add_parser("kill", help="kill an application process with SIGKILL").add_argument("--pid", type=int, required=True)
    shot = commands.add_parser("screenshot", help="capture the focused monitor or a region")
    shot.add_argument("target", choices=("output", "region"))
    clip = commands.add_parser("clipboard", help="session clipboard history")
    clip_actions = clip.add_subparsers(dest="action", required=True, metavar="ACTION")
    clip_actions.add_parser("store", help="store the clipboard entry read from stdin (for wl-paste --watch)")
    clip_actions.add_parser("list", help="print the history, newest first")
    for name, text in (("restore", "copy an entry back to the clipboard"), ("delete", "delete an entry"),
                       ("image", "write an image entry to a temporary PNG")):
        clip_actions.add_parser(name, help=text).add_argument("--id", required=True)
    clip_actions.add_parser("wipe", help="delete the whole history")
    pause = clip_actions.add_parser("pause", help="pause or resume recording")
    pause_switch = pause.add_mutually_exclusive_group(required=True)
    pause_switch.add_argument("--on", dest="paused", action="store_true")
    pause_switch.add_argument("--off", dest="paused", action="store_false")
    idle = commands.add_parser("idle", help="idle timeouts and actions for long idle periods")
    idle_actions = idle.add_subparsers(dest="action", required=True, metavar="ACTION")
    idle_actions.add_parser("suspend", help="suspend the computer if it runs on its own battery (called by hypridle)")
    idle_settings = idle_actions.add_parser("settings", help="print the lock, screen off and sleep timeouts as JSON")
    idle_settings.add_argument("--set", dest="change", metavar="JSON", help='apply {"lock", "screenOff", "suspend"} (minutes, 0 = never) first')
    idle_settings.add_argument("--path", type=Path, help="idle file (default: $XDG_CONFIG_HOME/quietline/idle.json); hypridle.conf is written next to it")
    files = commands.add_parser("files", help="find files in the home directory by name")
    files.add_argument("query", nargs="?", help="part of the file name")
    files.add_argument("--limit", type=int, default=20)
    files.add_argument("--update", action="store_true", help="rebuild the home directory index")
    network.add_parser(commands)
    return parser


def _run(args: argparse.Namespace) -> dict[str, Any]:
    match args.command:
        case "region":
            path = args.path or default_region_path()
            current = load_region(path, os.environ.get("LANG"))
            if args.new_region is None:
                return current
            updated = validated_region(json.loads(args.new_region), current)
            save_region(path, updated, path.parent.parent)
            return {**updated, "applied": apply_keyboard(updated)}
        case "display":
            path = args.path or default_display_path()
            monitors = load_display(path)
            if args.change is None:
                return {"monitors": monitors, "scales": display_scales(monitors), "outputs": display_outputs()}
            output, monitors = updated_display(json.loads(args.change), monitors)
            save_display(path, monitors)
            applied = apply_display(output, monitors.get(output, {}))
            return {"monitors": monitors, "scales": display_scales(monitors), "outputs": display_outputs(), "applied": applied}
        case "input":
            path = args.path or default_input_path()
            current = load_input(path)
            if args.change is None:
                return {**current, "touchpad": has_touchpad()}
            updated = updated_input(json.loads(args.change), current)
            save_input(path, updated)
            return {**updated, "touchpad": has_touchpad(), "applied": apply_input(updated)}
        case "appearance":
            path = args.path or default_appearance_path()
            current = load_appearance(path)
            if args.change is None:
                return current
            updated = updated_appearance(json.loads(args.change), current)
            save_appearance(path, updated)
            return {**updated, "applied": apply_appearance(updated)}
        case "greeter":
            path = args.path or session.default_greeter_path()
            if args.remember is not None:
                return session.remember_greeter(path, json.loads(args.remember))
            language = "ru" if os.environ.get("LANG", "").startswith("ru") else "en"
            return session.greeter_data(path, language=language)
        case "motion":
            return {"reducedMotion": reduced_motion()}
        case "lock":
            return session.lock()
        case "session":
            return session.end_session(args.action, args.timeout, args.force)
        case "clipboard":
            match args.action:
                case "store":
                    return clipboard.store(sys.stdin.buffer.read())
                case "list":
                    return clipboard.entries()
                case "restore":
                    return clipboard.restore(args.id)
                case "delete":
                    return clipboard.delete(args.id)
                case "image":
                    return clipboard.image(args.id)
                case "wipe":
                    return clipboard.wipe()
                case _:
                    return clipboard.set_paused(args.paused)
        case "idle":
            if args.action == "suspend":
                return session.idle_suspend()
            path = args.path or default_idle_path()
            current = load_idle(path)
            if args.change is None:
                return current
            updated = updated_idle(json.loads(args.change), current)
            save_idle(path, updated)
            return {**updated, "applied": restart_hypridle(path.with_name("hypridle.conf"))}
        case "files":
            if args.update:
                return search.update_index()
            return search.find_files(args.query or "", args.limit)
        case "screenshot":
            return capture.capture_output() if args.target == "output" else capture.capture_region()
        case "app":
            if args.action == "kill":
                return session.kill_app(args.pid)
            result = session.quit_app(args.pid, args.timeout)
            if args.notify and result["background"]:
                app = result["app"] or notification_text("app_unnamed")
                session.notify(notification_text("app_in_background", app=app),
                               notification_text("app_in_background_hint"))
            return result
        case "about":
            return about()
        case "network":
            return network.run(args, sys.stdin)
        case _:
            path = args.path or default_pins_path()
            if args.new_pins is not None:
                save_pins(path, json.loads(args.new_pins))
            return {"pinned": load_pins(path)}


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        response = _run(args)
    except network.ProfileError as error:
        print(json.dumps({"error": str(error), "field": error.field}, ensure_ascii=False))
        return 1
    except (OSError, ValueError, TypeError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(response, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
