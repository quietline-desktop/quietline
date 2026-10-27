"""CLI `quietline-shell`: данные для оболочки Quickshell одной строкой JSON в stdout.

- `pins [--set JSON] [--path PATH]` — `{"pinned": [...]}`; с `--set` список сначала
  проверяется и атомарно записывается;
- `motion` — `{"reducedMotion": true | false}`;
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

from quietline_shell import network
from quietline_shell.config import default_pins_path, load_pins, reduced_motion, save_pins


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quietline-shell", description="Quietline shell preferences.")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    pins = commands.add_parser("pins", help="print the pinned dock applications as JSON")
    pins.add_argument("--set", dest="new_pins", metavar="JSON", help="save this JSON list of desktop IDs first")
    pins.add_argument("--path", type=Path, help="pins file (default: $XDG_CONFIG_HOME/quietline/pins.json)")
    commands.add_parser("motion", help="print whether animations should be reduced")
    network.add_parser(commands)
    return parser


def _run(args: argparse.Namespace) -> dict[str, Any]:
    match args.command:
        case "motion":
            return {"reducedMotion": reduced_motion()}
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
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(response, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
