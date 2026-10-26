"""Тесты IPC-сервера, CLI и клавиш Hyprland: протокол JSON Lines, подписки, сокет и перезапуск."""

import asyncio
import contextlib
import json
import logging
import os
import re
import shutil
import socket
import stat
import tempfile
from dataclasses import replace
from pathlib import Path

import pytest
from fakes import monitor, snapshot, workspace

from quietline_engine import server as server_module
from quietline_engine.__main__ import main
from quietline_engine.controller import WindowController
from quietline_engine.hyprland import HyprlandError
from quietline_engine.server import EngineServer, ServerError, socket_path
from quietline_engine.types import FocusMonitor, FocusWorkspace, HyprEvent
from quietline_engine.workspaces import WorkspaceRegistry

KEY = "Dell Inc.|U2723QE|SN1"
SECOND_KEY = "Dell Inc.|U2723QE|SN2"
LUA_CONFIG = Path(__file__).resolve().parents[2] / "config" / "hyprland" / "quietline.lua"
TIMEOUT = 2.0


class LiveFake:
    """Поддельный Hyprland с состоянием: два монитора без окон.

    `FocusMonitor` и `FocusWorkspace` меняют фокус и активное пространство; при `broken`
    чтение снимка завершается `HyprlandError`.
    """

    def __init__(self, active=(1, 2)) -> None:
        self.monitors = {
            "DP-1": monitor(0, "DP-1", active=active[0], focused=True, serial="SN1"),
            "HDMI-A-1": monitor(1, "HDMI-A-1", x=2560, active=active[1], focused=False, serial="SN2"),
        }
        self.applied = []
        self.reads = 0
        self.broken = False

    def snapshot(self):
        self.reads += 1
        if self.broken:
            raise HyprlandError("hyprctl -j monitors failed with exit code 1: no instance")
        monitors = tuple(self.monitors.values())
        return snapshot(monitors, [workspace(m.active_workspace_id, m) for m in monitors], [])

    def apply(self, actions):
        self.applied.append(list(actions))
        for action in actions:
            match action:
                case FocusMonitor(name):
                    self.monitors = {n: replace(m, focused=n == name) for n, m in self.monitors.items()}
                case FocusWorkspace(workspace_id):
                    self.monitors = {
                        n: replace(m, active_workspace_id=workspace_id) if m.focused else m
                        for n, m in self.monitors.items()
                    }


class FakeEvents:
    """Поток событий Hyprland: каждое подключение — новая очередь; `close` завершает поток.

    Первые `failures` подключений завершаются `HyprlandError`.
    """

    def __init__(self, failures=0) -> None:
        self.failures = failures
        self.connections = 0
        self.queue: asyncio.Queue | None = None

    def __call__(self):
        return self._stream()

    async def _stream(self):
        self.connections += 1
        if self.failures:
            self.failures -= 1
            raise HyprlandError("cannot connect to .socket2.sock: no such file")
        self.queue = asyncio.Queue()
        while (event := await self.queue.get()) is not None:
            yield event

    def emit(self, name="openwindow"):
        self.queue.put_nowait(HyprEvent(name, "0x1,1,kitty,kitty"))

    def close(self):
        self.queue.put_nowait(None)


class Client:
    """Клиент протокола для тестов: строка JSON на запрос и на ответ."""

    def __init__(self, reader, writer) -> None:
        self.reader = reader
        self.writer = writer

    async def send(self, data: bytes) -> None:
        self.writer.write(data)
        await self.writer.drain()

    async def call(self, method, params=None, id=1):
        request = {"id": id, "method": method}
        if params is not None:
            request["params"] = params
        await self.send(json.dumps(request).encode() + b"\n")
        return await self.read()

    async def read(self):
        line = await asyncio.wait_for(self.reader.readline(), TIMEOUT)
        assert line, "connection closed"
        return json.loads(line)

    async def nothing_pending(self):
        """Ничего не пришло за короткое время."""
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(self.reader.readline(), 0.1)

    async def close(self):
        self.writer.close()
        with contextlib.suppress(ConnectionError):
            await self.writer.wait_closed()


async def connect(path) -> Client:
    return Client(*await asyncio.open_unix_connection(path))


async def wait_until(condition):
    for _ in range(200):
        if condition():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition not reached")


@contextlib.asynccontextmanager
async def running(path, controller, events=None, **options):
    options.setdefault("signature", "sig")
    server = EngineServer(controller, events or FakeEvents(), path, reconnect_delay=(0.01, 0.05), **options)
    await server.start()
    try:
        yield server
    finally:
        await server.close()


@pytest.fixture
def runtime_dir():
    """Короткий каталог в `/tmp`: путь к Unix-сокету на macOS ограничен ~104 байтами."""
    path = Path(tempfile.mkdtemp(dir="/tmp", prefix="ql-"))
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def env(runtime_dir):
    return {"XDG_RUNTIME_DIR": str(runtime_dir), "HYPRLAND_INSTANCE_SIGNATURE": "sig"}


@pytest.fixture
def path(env):
    return socket_path(env)


def controller_for(adapter, env):
    return WindowController(adapter, WorkspaceRegistry.from_environment(env))


def run(coroutine):
    return asyncio.run(coroutine)


def active_mode(state, name="DP-1"):
    return next(m for m in state["monitors"] if m["name"] == name)["mode"]


def test_socket_path_is_in_runtime_dir(runtime_dir):
    assert socket_path({"XDG_RUNTIME_DIR": str(runtime_dir)}) == runtime_dir / "quietline" / "engine.sock"
    with pytest.raises(ServerError, match="XDG_RUNTIME_DIR"):
        socket_path({})


def test_ipc_rejects_invalid_number_and_survives_client_disconnect(path, env):
    fake = LiveFake()

    async def scenario():
        async with running(path, controller_for(fake, env)):
            applied = len(fake.applied)
            client = await connect(path)
            for number in (11, 0, "3", True, None):
                reply = await client.call("switch", {"number": number}, id=7)
                assert reply["id"] == 7 and "result" not in reply
                assert reply["error"]["code"] == "invalid_number"
                assert "1 to 10" in reply["error"]["message"]
            reply = await client.call("move", {"number": 12}, id="m")
            assert reply == {"id": "m", "error": reply["error"]} and reply["error"]["code"] == "invalid_number"
            assert len(fake.applied) == applied

            broken = await connect(path)
            await broken.send(b'{"id": 2, "meth')
            await broken.close()

            await client.send(b"not json\n")
            assert (await client.read())["error"]["code"] == "invalid_request"
            await client.send(b"[1, 2]\n")
            reply = await client.read()
            assert reply["id"] is None and reply["error"]["code"] == "invalid_request"
            assert (await client.call("reboot", id=3))["error"]["code"] == "unknown_method"
            reply = await client.call("switch", {"number": 2, "monitor": 5}, id=4)
            assert reply["error"]["code"] == "invalid_request"
            reply = await client.call("toggle", {"monitr": KEY}, id=5)
            assert reply["error"]["code"] == "invalid_request"

            impatient = await connect(path)
            await impatient.send(b'{"id": 1, "method": "toggle", "params": {}}\n')
            await impatient.close()

            async def mode():
                return active_mode((await client.call("state", id=6))["result"])

            for _ in range(100):
                if await mode() == "tiles":
                    break
                await asyncio.sleep(0.01)
            assert await mode() == "tiles"
            await client.close()

            fresh = await connect(path)
            assert (await fresh.call("state"))["result"]["error"] is None
            await fresh.close()

    run(scenario())


def test_oversized_request_closes_only_that_connection(path, env):
    async def scenario():
        async with running(path, controller_for(LiveFake(), env)):
            other = await connect(path)
            flood = await connect(path)
            await flood.send(b"x" * (server_module.REQUEST_LINE_LIMIT + 10))
            reply = await flood.read()
            assert reply["id"] is None and reply["error"]["code"] == "invalid_request"
            assert await asyncio.wait_for(flood.reader.read(), TIMEOUT) == b""
            await flood.close()
            assert "result" in await other.call("state")
            await other.close()

    run(scenario())


def test_command_failure_is_an_error_reply(path, env):
    fake = LiveFake()

    async def scenario():
        async with running(path, controller_for(fake, env)):
            client = await connect(path)
            reply = await client.call("toggle", {"monitor": "no-such-monitor"})
            assert reply["error"] == {"code": "command_failed", "message": "unknown monitor 'no-such-monitor'"}
            reply = await client.call("switch", {"number": 3, "monitor": SECOND_KEY}, id=2)
            assert reply["id"] == 2 and reply["result"]["error"] is None
            await client.close()

    run(scenario())


def test_subscribe_sends_snapshot_then_revision(path, env):
    fake = LiveFake()
    events = FakeEvents()

    async def scenario():
        async with running(path, controller_for(fake, env), events):
            subscriber = await connect(path)
            first = await subscriber.call("subscribe", id="s")
            assert first["id"] == "s"
            state = first["result"]
            assert [m["key"] for m in state["monitors"]] == [KEY, SECOND_KEY]
            assert [(w["number"], w["workspace_id"]) for w in state["workspaces"]] == [(1, 1), (1, 2)]
            revision = state["revision"]

            commands = await connect(path)
            reply = await commands.call("switch", {"number": 3})
            assert reply["result"]["revision"] == revision + 1
            push = await subscriber.read()
            assert push == {"event": "state", "state": reply["result"]}

            await wait_until(lambda: events.queue is not None)
            reads = fake.reads
            events.emit()
            await wait_until(lambda: fake.reads > reads)
            await subscriber.nothing_pending()

            reply = await commands.call("toggle", id=2)
            push = await subscriber.read()
            assert push["state"]["revision"] == revision + 2 == reply["result"]["revision"]
            assert active_mode(push["state"]) == "tiles"
            await commands.close()
            await subscriber.close()

    run(scenario())


def test_subscribers_get_each_error_once(path, env):
    fake = LiveFake()
    events = FakeEvents()

    async def scenario():
        async with running(path, controller_for(fake, env), events):
            subscriber = await connect(path)
            revision = (await subscriber.call("subscribe"))["result"]["revision"]
            await wait_until(lambda: events.queue is not None)

            fake.broken = True
            events.emit()
            push = await subscriber.read()
            assert push["state"]["revision"] == revision
            assert push["state"]["error"].startswith("cannot read compositor state")
            reads = fake.reads
            events.emit()
            await wait_until(lambda: fake.reads > reads)
            await subscriber.nothing_pending()

            fake.broken = False
            events.emit()
            push = await subscriber.read()
            assert push["state"]["revision"] == revision and push["state"]["error"] is None
            await subscriber.close()

    run(scenario())


def test_resubscribe_after_disconnect(path, env):
    fake = LiveFake()

    async def scenario():
        async with running(path, controller_for(fake, env)):
            gone = await connect(path)
            await gone.call("subscribe")
            await gone.close()

            commands = await connect(path)
            changed = (await commands.call("switch", {"number": 4}))["result"]

            again = await connect(path)
            state = (await again.call("subscribe"))["result"]
            assert state == changed
            reply = await commands.call("switch", {"number": 1}, id=2)
            assert (await again.read())["state"] == reply["result"]
            await commands.close()
            await again.close()

    run(scenario())


def test_subscriber_that_stops_reading_is_disconnected(path, env, monkeypatch, caplog):
    monkeypatch.setattr(server_module, "CLIENT_QUEUE_LIMIT", 2)
    caplog.set_level(logging.WARNING, logger="quietline_engine")

    def dropped():
        return any("not reading" in r.getMessage() for r in caplog.records)

    async def scenario():
        async with running(path, controller_for(LiveFake(), env)):
            stalled = await connect(path)
            await stalled.call("subscribe")
            commands = await connect(path)
            for attempt in range(5000):
                reply = await commands.call("switch", {"number": 1 + attempt % 2}, id=attempt)
                assert reply["result"]["error"] is None
                if dropped():
                    break
            assert dropped()
            assert "result" in await commands.call("state")
            await commands.close()
            await stalled.close()

    run(scenario())


def test_restart_preserves_session_state(path, env):
    async def first_run():
        async with running(path, controller_for(LiveFake(), env)):
            client = await connect(path)
            assert (await client.call("switch", {"number": 3}))["result"]["error"] is None
            state = (await client.call("toggle", id=2))["result"]
            await client.close()
            return state

    async def second_run(environment):
        async with running(path, controller_for(LiveFake(active=(1001, 2)), environment)):
            client = await connect(path)
            state = (await client.call("state"))["result"]
            await client.close()
            return state

    before = run(first_run())
    assert active_mode(before) == "tiles"
    after = run(second_run(env))
    assert after["workspaces"] == before["workspaces"]
    assert active_mode(after) == "tiles"
    assert {(w["number"], w["workspace_id"], w["mode"]) for w in after["workspaces"]} >= {(3, 1001, "tiles")}

    other_session = run(second_run({**env, "HYPRLAND_INSTANCE_SIGNATURE": "other"}))
    assert all(w["number"] != 3 for w in other_session["workspaces"])


def test_socket_permissions_and_single_instance(path, env, runtime_dir):
    (runtime_dir / "quietline").mkdir(mode=0o755)
    os.chmod(runtime_dir / "quietline", 0o755)
    stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale.bind(str(path))
    stale.close()
    assert path.exists()

    async def scenario():
        async with running(path, controller_for(LiveFake(), env)):
            assert stat.S_IMODE(os.stat(path.parent).st_mode) == 0o700
            info = os.stat(path)
            assert stat.S_ISSOCK(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600

            second = EngineServer(controller_for(LiveFake(), env), FakeEvents(), path, signature="sig")
            with pytest.raises(ServerError, match="already running"):
                await second.start()
            client = await connect(path)
            assert "result" in await client.call("state")
            await client.close()
        assert not path.exists()

    run(scenario())


def test_start_refuses_a_path_that_is_not_a_socket(path, env):
    path.parent.mkdir(mode=0o700)
    path.write_text("keep me")

    async def scenario():
        server = EngineServer(controller_for(LiveFake(), env), FakeEvents(), path, signature="sig")
        with pytest.raises(ServerError, match="not a socket"):
            await server.start()

    run(scenario())
    assert path.read_text() == "keep me"


def instance_dir(env):
    """Каталог экземпляра Hyprland `$XDG_RUNTIME_DIR/hypr/<сигнатура>`."""
    return Path(env["XDG_RUNTIME_DIR"]) / "hypr" / env["HYPRLAND_INSTANCE_SIGNATURE"]


def make_instance(env):
    """Каталог работающего экземпляра: `hyprland.lock` и `.socket2.sock` на месте."""
    directory = instance_dir(env)
    directory.mkdir(parents=True)
    (directory / "hyprland.lock").write_text("1\n")
    (directory / ".socket2.sock").touch()
    (directory / "hyprland.log").touch()
    return directory


def test_serve_reconnects_to_event_socket(path, env, caplog):
    fake = LiveFake()
    events = FakeEvents(failures=1)
    caplog.set_level(logging.INFO, logger="quietline_engine")
    make_instance(env)

    async def scenario():
        async with running(path, controller_for(fake, env), events, instance_dir=instance_dir(env)):
            await wait_until(lambda: events.queue is not None)
            assert events.connections == 2
            events.close()
            await wait_until(lambda: events.connections == 3)
            await wait_until(lambda: events.queue is not None and events.queue.empty())
            reads = fake.reads
            events.emit()
            await wait_until(lambda: fake.reads > reads)
            client = await connect(path)
            assert "result" in await client.call("state")
            await client.close()

    run(scenario())
    messages = [r.getMessage() for r in caplog.records]
    assert any("Hyprland event socket failed" in m and "reconnecting" in m for m in messages)
    assert any("Hyprland event socket closed" in m and "reconnecting" in m for m in messages)


def test_serve_exits_when_its_hyprland_instance_is_gone_at_start(path, env):
    async def scenario():
        server = EngineServer(
            controller_for(LiveFake(), env),
            FakeEvents(failures=1),
            path,
            reconnect_delay=(0.01, 0.05),
            signature="sig",
            instance_dir=instance_dir(env),
        )
        with pytest.raises(ServerError, match="is gone"):
            await asyncio.wait_for(server.serve_forever(), TIMEOUT)

    run(scenario())
    assert not path.exists()


@pytest.mark.parametrize("removed", ["directory", ".socket2.sock", "hyprland.lock"])
def test_serve_exits_when_hyprland_closes_and_its_instance_is_gone(path, env, removed):
    events = FakeEvents()
    directory = make_instance(env)

    async def scenario():
        server = EngineServer(
            controller_for(LiveFake(), env),
            events,
            path,
            reconnect_delay=(0.01, 0.05),
            signature="sig",
            instance_dir=directory,
        )
        serving = asyncio.create_task(server.serve_forever())
        await wait_until(lambda: events.queue is not None)
        client = await connect(path)
        assert "result" in await client.call("state")
        if removed == "directory":
            shutil.rmtree(directory)
        else:
            (directory / removed).unlink()
        events.close()
        with pytest.raises(ServerError, match="is gone"):
            await asyncio.wait_for(serving, TIMEOUT)
        assert await asyncio.wait_for(client.reader.read(), TIMEOUT) == b""
        await client.close()

    run(scenario())
    assert not path.exists()


def test_new_session_replaces_service_of_previous_session(path, env):
    old_env = {**env, "HYPRLAND_INSTANCE_SIGNATURE": "old"}

    async def scenario():
        old = EngineServer(controller_for(LiveFake(), old_env), FakeEvents(), path, signature="old")
        serving = asyncio.create_task(old.serve_forever())
        await wait_until(path.exists)
        async with running(path, controller_for(LiveFake(), env), signature="sig"):
            await asyncio.wait_for(serving, TIMEOUT)
            assert serving.exception() is None
            client = await connect(path)
            assert "result" in await client.call("state")
            await client.close()

    run(scenario())


def test_same_session_service_is_not_replaced(path, env):
    async def scenario():
        async with running(path, controller_for(LiveFake(), env), signature="sig"):
            second = EngineServer(controller_for(LiveFake(), env), FakeEvents(), path, signature="sig")
            with pytest.raises(ServerError, match="already running"):
                await second.start()
            client = await connect(path)
            assert "result" in await client.call("state")
            reply = await client.call("takeover", {"signature": "sig"}, id=2)
            assert reply["error"]["code"] == "already_running"
            assert "result" in await client.call("state", id=3)
            await client.close()

    run(scenario())


def test_takeover_requires_a_valid_signature(path, env):
    async def scenario():
        async with running(path, controller_for(LiveFake(), env), signature="sig"):
            client = await connect(path)
            for params in ({}, {"signature": None}, {"signature": ""}, {"signature": "a b"}, {"signature": "../x"}, {"signature": 5}):
                reply = await client.call("takeover", params, id=9)
                assert reply["id"] == 9 and reply["error"]["code"] == "invalid_request", params
            await asyncio.sleep(0.05)
            assert "result" in await client.call("state")
            await client.close()
            assert path.exists()

    run(scenario())


def test_server_requires_a_valid_own_signature(path, env):
    for signature in ("", "a b", "x/y"):
        with pytest.raises(ServerError, match="signature"):
            EngineServer(controller_for(LiveFake(), env), FakeEvents(), path, signature=signature)


def test_cli_serve_fails_when_hyprland_instance_is_gone(env, monkeypatch, capsys):
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    assert main(["serve"]) == 1
    assert "Hyprland instance sig is gone" in capsys.readouterr().err


def test_cli_prints_results_and_fails_on_errors(path, env, monkeypatch, capsys):
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    async def scenario():
        async with running(path, controller_for(LiveFake(), env)):
            assert await asyncio.to_thread(main, ["switch", "3"]) == 0
            assert capsys.readouterr().out == "Workspace 3 is active on DP-1.\n"
            assert await asyncio.to_thread(main, ["switch", "2", "--monitor", SECOND_KEY]) == 0
            assert capsys.readouterr().out == "Workspace 2 is active on HDMI-A-1.\n"
            assert await asyncio.to_thread(main, ["toggle", "--monitor", SECOND_KEY]) == 0
            assert capsys.readouterr().out == "Workspace 2 on HDMI-A-1 is now in tiles mode.\n"
            assert await asyncio.to_thread(main, ["move", "5"]) == 1
            captured = capsys.readouterr()
            assert captured.out == "" and "no active window to move" in captured.err
            assert await asyncio.to_thread(main, ["switch", "11"]) == 1
            assert "1 to 10" in capsys.readouterr().err
            assert await asyncio.to_thread(main, ["state"]) == 0
            state = json.loads(capsys.readouterr().out)
            assert active_mode(state, "HDMI-A-1") == "tiles"

    run(scenario())
    assert main(["state"]) == 1
    assert "cannot connect to quietline-engine" in capsys.readouterr().err


def test_shortcuts_target_expected_cli_calls():
    text = LUA_CONFIG.read_text(encoding="utf-8")
    binds = re.findall(r'hl\.bind\("([^"]+)",\s*hl\.dsp\.exec_cmd\("([^"]+)"\)\)', text)
    assert len(binds) == text.count("hl.bind(")
    keys = [key for key, _ in binds]
    assert len(keys) == len(set(keys))

    expected = {}
    for number in range(1, 11):
        key = str(number % 10)
        expected[f"SUPER + {key}"] = f"quietline-engine switch {number}"
        expected[f"SUPER + SHIFT + {key}"] = f"quietline-engine move {number}"
    expected["SUPER + M"] = "quietline-engine toggle"
    expected["SUPER + Return"] = "ghostty"
    assert dict(binds) == expected

    assert re.search(r'hl\.config\(\{\s*general\s*=\s*\{\s*layout\s*=\s*"scrolling"\s*\}\s*\}\)', text)
    assert re.search(
        r'hl\.on\("hyprland\.start",\s*function\s*\(\)\s*hl\.exec_cmd\("quietline-engine serve"\)\s*end\)', text
    )
    comments = [line.split("--", 1)[1] for line in text.splitlines() if "--" in line]
    assert comments and all(re.search("[а-яё]", c, re.IGNORECASE) for c in comments if c.strip())
