"""CLI `quietline-shell`: данные для оболочки Quickshell одной строкой JSON в stdout.

- `pins [--set JSON] [--path PATH]` — `{"pinned": [...]}`; с `--set` список сначала
  проверяется и атомарно записывается;
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
- `network ACTION …` — NetworkManager: состояние, профили объекта, Wi-Fi, контрольные
  точки; подкоманды и их ответы — в docstring `quietline_shell.network`.

Ошибка — `{"error": "<текст>"}` в stdout и код выхода 1; у ошибки формы сетевого профиля
ещё `"field"` с полем формы. Неверные аргументы — код 2.
"""

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from quietline_shell import capture, network, session
from quietline_shell.config import about, default_pins_path, load_pins, reduced_motion, save_pins


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quietline-shell", description="Quietline shell preferences.")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    pins = commands.add_parser("pins", help="print the pinned dock applications as JSON")
    pins.add_argument("--set", dest="new_pins", metavar="JSON", help="save this JSON list of desktop IDs first")
    pins.add_argument("--path", type=Path, help="pins file (default: $XDG_CONFIG_HOME/quietline/pins.json)")
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
    network.add_parser(commands)
    return parser


def _run(args: argparse.Namespace) -> dict[str, Any]:
    match args.command:
        case "motion":
            return {"reducedMotion": reduced_motion()}
        case "lock":
            return session.lock()
        case "session":
            return session.end_session(args.action, args.timeout)
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
