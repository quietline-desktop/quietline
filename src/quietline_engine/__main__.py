"""CLI `quietline-engine`: сервис `serve` и клиентские команды `switch`, `move`, `toggle`, `state`.

Клиентская команда отправляет один запрос в сокет сервиса и печатает короткую строку
(`state` — состояние в JSON). Код выхода: 0 — успех, 1 — ошибка, 2 — неверные аргументы.
"""

import argparse
import asyncio
import contextlib
import json
import logging
import os
import signal
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from quietline_engine.controller import WindowController
from quietline_engine.hyprland import Hyprland
from quietline_engine.server import EngineError, EngineServer, ServerError, request, socket_path
from quietline_engine.workspaces import WorkspaceError, WorkspaceRegistry


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quietline-engine", description="Quietline workspace and window engine.")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    commands.add_parser("serve", help="run the engine service")
    switch = commands.add_parser("switch", help="open local workspace N (1-10) of a monitor")
    switch.add_argument("number", type=int, metavar="N")
    switch.add_argument("--monitor", metavar="KEY", help="monitor key (default: the focused monitor)")
    move = commands.add_parser("move", help="move the active window to local workspace N and follow it")
    move.add_argument("number", type=int, metavar="N")
    toggle = commands.add_parser("toggle", help="switch the active workspace between windows and tiles mode")
    toggle.add_argument("--monitor", metavar="KEY", help="monitor key (default: the focused monitor)")
    commands.add_parser("state", help="print the engine state as JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "serve":
            return _serve()
        path = socket_path()
        match args.command:
            case "switch":
                params: dict[str, Any] = {"number": args.number}
                if args.monitor is not None:
                    params["monitor"] = args.monitor
                monitor = _monitor(request(path, "switch", params), args.monitor)
                print(f"Workspace {args.number} is active on {monitor}.")
            case "move":
                request(path, "move", {"number": args.number})
                print(f"Moved the active window to workspace {args.number}.")
            case "toggle":
                params = {} if args.monitor is None else {"monitor": args.monitor}
                state = request(path, "toggle", params)
                print(_mode_line(state, args.monitor))
            case _:
                print(json.dumps(request(path, "state"), indent=2, ensure_ascii=False))
    except (EngineError, ServerError, WorkspaceError) as error:
        print(f"quietline-engine: {error}", file=sys.stderr)
        return 1
    return 0


def _find_monitor(state: dict[str, Any], key: str | None) -> dict[str, Any] | None:
    """Монитор с ключом `key`, без него — монитор с фокусом."""
    return next((m for m in state["monitors"] if (m["key"] == key if key else m["focused"])), None)


def _monitor(state: dict[str, Any], key: str | None) -> str:
    monitor = _find_monitor(state, key)
    return monitor["name"] if monitor else key or "the focused monitor"


def _mode_line(state: dict[str, Any], key: str | None) -> str:
    monitor = _find_monitor(state, key)
    if monitor is None or monitor["mode"] is None:
        return "Workspace mode switched."
    return f"Workspace {monitor['active_number']} on {monitor['name']} is now in {monitor['mode']} mode."


def _serve() -> int:
    """Запускает сервис до SIGINT, SIGTERM, замены сервисом нового сеанса или конца сеанса Hyprland.

    Журнал — в stderr; конец сеанса — `ServerError` (код выхода 1).
    """
    logging.basicConfig(level=logging.INFO, format="quietline-engine: %(message)s")
    adapter = Hyprland()
    controller = WindowController(adapter, WorkspaceRegistry.from_environment())
    signature = os.environ["HYPRLAND_INSTANCE_SIGNATURE"]
    instance_dir = Path(os.environ["XDG_RUNTIME_DIR"]) / "hypr" / signature
    server = EngineServer(
        controller, adapter.events, socket_path(), signature=signature, instance_dir=instance_dir
    )
    asyncio.run(_run(server))
    return 0


async def _run(server: EngineServer) -> None:
    task = asyncio.current_task()
    loop = asyncio.get_running_loop()
    for number in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(number, task.cancel)
    with contextlib.suppress(asyncio.CancelledError):
        await server.serve_forever()
    logging.getLogger("quietline_engine").info("stopped")


if __name__ == "__main__":
    sys.exit(main())
