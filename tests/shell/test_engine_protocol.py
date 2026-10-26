"""Контракт между движком и оболочкой: `engine-protocol.json` — строки, которые выдаёт сервис.

Строки одного соединения подписчика создаёт настоящий `EngineServer` из `PublicState.to_json()`;
`models.test.cjs` прогоняет тот же файл через `Models.decodeMessage` оболочки. Смена полей
состояния или формы ответов роняет этот тест, пока файл не обновлён и оболочка не проверена
на новом файле.
"""

import asyncio
import json
from dataclasses import replace
from pathlib import Path

from quietline_engine.controller import MonitorState, PublicState, WorkspaceState
from quietline_engine.server import EngineServer

FIXTURE = Path(__file__).with_name("engine-protocol.json")

DELL = "Dell Inc.|U2723QE|SN1"
GONE = "Dell Inc.|U2723QE|SN2"
HDMI = "connector:HDMI-A-1"
LAPTOP = "connector:eDP-1"
ERROR = "mode switch failed: hyprctl eval failed: error: window not found"


def published() -> PublicState:
    """Три подключённых монитора; пространство 3 отключённого монитора показано на DP-1.

    На eDP-1 открыто пространство, которым движок не управляет.
    """
    return PublicState(
        revision=4,
        monitors=(
            MonitorState(DELL, "DP-1", True, 1, 1, "windows"),
            MonitorState(HDMI, "HDMI-A-1", False, 1002, 2, "tiles"),
            MonitorState(LAPTOP, "eDP-1", False, 7, None, None),
        ),
        workspaces=(
            WorkspaceState(DELL, DELL, 1, 1, "windows"),
            WorkspaceState(HDMI, HDMI, 1, 1001, "windows"),
            WorkspaceState(HDMI, HDMI, 2, 1002, "tiles"),
            WorkspaceState(GONE, DELL, 3, 1003, "tiles"),
        ),
    )


class Subscriber:
    """Соединение клиента без сокета: запоминает события, которые сервис ему отправил."""

    subscribed = False

    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, message) -> None:
        self.sent.append(message)


class Controller:
    """Контроллер, который на любую команду отвечает заданным состоянием."""

    def __init__(self, state: PublicState) -> None:
        self.result = state

    def state(self) -> PublicState:
        return self.result

    async def switch(self, number, monitor) -> PublicState:
        return self.result

    async def move(self, number) -> PublicState:
        return self.result

    async def toggle(self, monitor) -> PublicState:
        return self.result


def transcript() -> list[dict]:
    """Строки соединения по порядку: подписка, отказ по номеру, неудачная и удачная команды."""
    state = published()
    controller = Controller(state)
    server = EngineServer(controller, lambda: None, Path("engine.sock"), signature="contract")
    subscriber = Subscriber()
    server._connections.add(subscriber)
    lines: list[dict] = []

    async def answer(request: dict) -> None:
        sent = len(subscriber.sent)
        reply = await server._answer(json.dumps(request).encode(), subscriber)
        lines.extend(subscriber.sent[sent:])
        lines.append(reply)

    async def scenario() -> None:
        await answer({"id": 1, "method": "subscribe", "params": {}})
        await answer({"id": 2, "method": "switch", "params": {"number": 11}})
        controller.result = replace(state, error=ERROR)
        await answer({"id": 3, "method": "toggle", "params": {"monitor": HDMI}})
        controller.result = replace(
            state,
            revision=5,
            monitors=(replace(state.monitors[0], active_workspace_id=1003, active_number=3, mode="tiles"),)
            + state.monitors[1:],
        )
        await answer({"id": 4, "method": "switch", "params": {"number": 3, "monitor": GONE}})

    asyncio.run(scenario())
    return lines


def test_fixture_is_what_the_engine_sends():
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert transcript() == expected["lines"]


def test_fixture_covers_every_message_kind_the_shell_reads():
    lines = json.loads(FIXTURE.read_text(encoding="utf-8"))["lines"]
    kinds = ["event" if "event" in line else "error" if "error" in line else "result" for line in lines]
    assert kinds == ["result", "error", "event", "error", "event", "result"]
    assert [line["error"]["code"] for line in lines if "error" in line and "event" not in line] == [
        "invalid_number",
        "command_failed",
    ]
