"""CLI `quietline-shell`: данные для оболочки Quickshell одной строкой JSON в stdout.

- `pins [--set JSON] [--path PATH]` — `{"pinned": [...]}`; с `--set` список сначала
  проверяется и атомарно записывается;
- `region [--set JSON] [--path PATH]` — `{"language", "clock", "date", "layouts", "toggle"}`:
  язык, форматы времени и даты, раскладки и сочетание переключения; с `--set` частичное
  обновление проверяется, пишется в `region.json`, `locale.conf` и `quietline/keyboard.lua`
  рядом с `PATH` (по умолчанию в `$XDG_CONFIG_HOME`), раскладки применяются в Hyprland,
  в ответ добавляется `"applied": true | false`;
- `motion` — `{"reducedMotion": true | false}`;
- `about` — `{os, kernel, hostname, cpu, memoryGb, hyprland, quickshell}` для страницы
  «О системе», недоступное значение — `null`;
- `lock` — `{"locked": true}`: экран блокировки запущен или уже работал;
- `session logout|reboot|poweroff [--timeout S]` — корректно закрывает окна и выполняет
  действие: `{"action", "done": true}` или `{"action", "done": false, "remaining": [{"app", "title"}]}`;
- `app quit [--pid P]` — корректный выход из приложения активного окна (или процесса `P`):
  `{"closed", "remaining", "background"}` (с `background` — ещё `app`); с `--notify` об оставшемся
  в фоне процессе сообщает уведомление; `app kill --pid P` — `{"killed": P}`;
- `screenshot output|region` — снимок монитора с фокусом `{"path", "copied": true}` или
  область в Satty `{"started": true}` / `{"cancelled": true}`; итог сообщает уведомление;
- `clipboard store|list|restore|delete|image|wipe|pause` — история буфера сеанса:
  `store` читает запись из stdin, `list` — `{"entries": [{"id", "kind", "preview"}], "paused"}`,
  `image --id ID` — `{"path"}`, остальные — `{"ok": true}`;
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
    about, apply_keyboard, default_pins_path, default_region_path, load_pins, load_region, reduced_motion,
    save_pins, save_region, validated_region,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quietline-shell", description="Quietline shell preferences.")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    pins = commands.add_parser("pins", help="print the pinned dock applications as JSON")
    pins.add_argument("--set", dest="new_pins", metavar="JSON", help="save this JSON list of desktop IDs first")
    pins.add_argument("--path", type=Path, help="pins file (default: $XDG_CONFIG_HOME/quietline/pins.json)")
    region = commands.add_parser("region", help="print the language and region settings as JSON")
    region.add_argument("--set", dest="new_region", metavar="JSON", help="apply this JSON object of fields first")
    region.add_argument("--path", type=Path, help="region file (default: $XDG_CONFIG_HOME/quietline/region.json)")
    commands.add_parser("motion", help="print whether animations should be reduced")
    commands.add_parser("about", help="print system facts for the settings window")
    commands.add_parser("lock", help="start the lock screen unless it is already running")
    ending = commands.add_parser("session", help="close all windows, then log out, reboot or power off")
    ending.add_argument("action", choices=session.SESSION_ACTIONS)
    ending.add_argument("--timeout", type=float, default=session.CLOSE_TIMEOUT, help="seconds to wait for windows to close")
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
        case "motion":
            return {"reducedMotion": reduced_motion()}
        case "lock":
            return session.lock()
        case "session":
            return session.end_session(args.action, args.timeout)
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
                session.notify(f"«{result['app'] or 'Приложение'}» продолжает работать в фоне",
                               "Super+Shift+Q завершит его принудительно.")
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
