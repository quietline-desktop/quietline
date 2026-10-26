"""IPC движка: JSON Lines поверх Unix-сокета, подписки на состояние и синхронный клиент.

Протокол. Одна строка UTF-8 — один JSON-объект. Запрос: `{"id", "method", "params"}`;
`id` — строка или целое число, `params` — объект (можно не передавать). Ответ несёт тот же
`id` и либо `result`, либо `error {code, message}`:

- `switch {number, monitor?}`, `move {number}`, `toggle {monitor?}` — `result` —
  подтверждённое состояние (`PublicState.to_json`), `result.error` всегда `null`;
- `state {}` — последнее опубликованное состояние с ошибкой последней команды или сверки;
- `subscribe {}` — `result` — то же полное состояние; затем по этому соединению приходят
  события `{"event": "state", "state": {...}}`, когда `revision` растёт или меняется
  текст `error`. `revision` событий не убывает и не меньше `revision` из `result`.

Коды ошибок:

- `invalid_request` — строка не JSON-объект; нет `id` или он не строка и не целое число
  (тогда в ответе `id` равен `null`); `method` не строка; `params` не объект; лишний
  параметр; `monitor` не строка;
- `unknown_method` — метода нет в списке выше;
- `invalid_number` — номер пространства не целое число от 1 до 10; Hyprland не вызывается;
- `command_failed` — команда не выполнена: `message` — текст `error` подтверждённого
  состояния; само состояние с ошибкой получают подписчики;
- `internal_error` — непредвиденный сбой обработки запроса.

Запросы одного соединения обрабатываются по порядку. Незавершённая строка в конце потока
не считается запросом; строка длиннее `REQUEST_LINE_LIMIT` получает `invalid_request`,
и соединение закрывается. Соединение закрывается после конца входного потока клиента.
Клиент, который не читает ответы и события, отключается при переполнении его очереди.
Ошибка или разрыв одного клиента не затрагивает других клиентов, сервис и начатую команду.
"""

import asyncio
import contextlib
import json
import logging
import os
import socket
import stat
from collections.abc import AsyncIterator, Callable, Mapping
from pathlib import Path
from typing import Any

from quietline_engine.controller import PublicState, WindowController
from quietline_engine.types import HyprEvent
from quietline_engine.workspaces import InvalidWorkspaceNumber, check_number

log = logging.getLogger(__name__)

REQUEST_LINE_LIMIT = 64 * 1024
# Сколько исходящих сообщений ждёт клиента, прежде чем его отключат.
CLIENT_QUEUE_LIMIT = 256
CLOSE_TIMEOUT_SECONDS = 5.0
CLIENT_TIMEOUT_SECONDS = 60.0
# Первая и наибольшая пауза перед повторным подключением к событиям Hyprland.
RECONNECT_DELAY_SECONDS = (0.5, 10.0)

# Параметры каждого метода.
_METHODS: dict[str, frozenset[str]] = {
    "switch": frozenset({"number", "monitor"}),
    "move": frozenset({"number"}),
    "toggle": frozenset({"monitor"}),
    "state": frozenset(),
    "subscribe": frozenset(),
}

# Сигналы сверки, не пришедшие из сокета событий.
_STARTED = HyprEvent("quietline", "started")
_RECONNECTED = HyprEvent("quietline", "reconnected")


class ServerError(Exception):
    """Сервис не может занять сокет или окружение неполное."""


class EngineError(Exception):
    """Ответ `error` движка или сбой связи с ним; `code` — код ошибки протокола."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def socket_path(env: Mapping[str, str] | None = None) -> Path:
    """Путь сокета `$XDG_RUNTIME_DIR/quietline/engine.sock`."""
    env = os.environ if env is None else env
    runtime_dir = env.get("XDG_RUNTIME_DIR")
    if not runtime_dir:
        raise ServerError("XDG_RUNTIME_DIR is not set")
    return Path(runtime_dir) / "quietline" / "engine.sock"


class _Connection:
    """Исходящая сторона клиента: ответы и события пишутся по порядку отдельной задачей."""

    def __init__(self, writer: asyncio.StreamWriter) -> None:
        self.subscribed = False
        self._writer = writer
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue(CLIENT_QUEUE_LIMIT)
        self._task = asyncio.create_task(self._send())

    def send(self, message: Mapping[str, Any]) -> None:
        """Ставит сообщение в очередь; при переполнении очереди соединение обрывается."""
        if self._task.done():
            return
        try:
            self._queue.put_nowait(json.dumps(message, ensure_ascii=False).encode() + b"\n")
        except asyncio.QueueFull:
            log.warning("IPC client is not reading; disconnecting it")
            self.abort()

    def abort(self) -> None:
        """Обрывает соединение сразу, не дописывая очередь и буфер записи."""
        self._task.cancel()
        self._writer.transport.abort()

    async def finish(self) -> None:
        """Дописывает очередь и закрывает соединение; не дольше `CLOSE_TIMEOUT_SECONDS`."""
        if not self._task.done():
            try:
                self._queue.put_nowait(None)
            except asyncio.QueueFull:
                self.abort()
            await asyncio.wait({self._task}, timeout=CLOSE_TIMEOUT_SECONDS)
        if not self._task.done():
            self.abort()
            await asyncio.wait({self._task})

    async def _send(self) -> None:
        """Пишет очередь до `None`, затем закрывает соединение; недописанное за `CLOSE_TIMEOUT_SECONDS` обрывается."""
        writer = self._writer
        try:
            while (data := await self._queue.get()) is not None:
                writer.write(data)
                await writer.drain()
            writer.close()
            async with asyncio.timeout(CLOSE_TIMEOUT_SECONDS):
                await writer.wait_closed()
        except Exception as error:
            log.debug("IPC client connection closed: %s", error)
        finally:
            writer.transport.abort()


class EngineServer:
    """Сервис движка: IPC-клиенты и сверка по событиям Hyprland.

    `events` открывает новый поток событий Hyprland (см. `Hyprland.events`). Сверка
    выполняется при запуске, после каждого события и после каждого переподключения;
    закрытый или недоступный поток открывается снова с паузой от `reconnect_delay[0]`
    до `reconnect_delay[1]` секунд, удваивающейся при каждой неудаче подряд. IPC-клиенты
    обслуживаются всё это время.
    """

    def __init__(
        self,
        controller: WindowController,
        events: Callable[[], AsyncIterator[HyprEvent]],
        path: Path,
        *,
        reconnect_delay: tuple[float, float] = RECONNECT_DELAY_SECONDS,
    ) -> None:
        self._controller = controller
        self._events = events
        self._path = path
        self._delay = reconnect_delay
        self._latest: PublicState | None = None
        self._connections: set[_Connection] = set()
        self._server: asyncio.Server | None = None
        self._events_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Занимает сокет, сверяет состояние и начинает принимать клиентов и события.

        Каталог сокета получает права `0700`, сокет — `0600`. Файл сокета, который никто
        не слушает, заменяется; живой сокет означает запущенный экземпляр — `ServerError`.
        """
        _claim(self._path)
        try:
            self._server = await asyncio.start_unix_server(
                self._serve_client, path=str(self._path), limit=REQUEST_LINE_LIMIT, start_serving=False
            )
        except OSError as error:
            raise ServerError(f"cannot listen on {self._path}: {error}") from error
        try:
            os.chmod(self._path, 0o600)
            await self._reconcile(_STARTED)
            await self._server.start_serving()
        except BaseException:
            await self.close()
            raise
        self._events_task = asyncio.create_task(self._follow_events())
        log.info("listening on %s", self._path)

    async def serve_forever(self) -> None:
        """`start`, затем работа до отмены; при выходе сокет удаляется."""
        await self.start()
        try:
            await asyncio.Event().wait()
        finally:
            await self.close()

    async def close(self) -> None:
        """Останавливает события, закрывает клиентов и удаляет файл сокета."""
        if self._events_task is not None:
            self._events_task.cancel()
            await asyncio.wait({self._events_task})
            self._events_task = None
        if self._server is not None:
            self._server.close()
            for connection in list(self._connections):
                connection.abort()
            await self._server.wait_closed()
            self._server = None

    async def _serve_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        connection = _Connection(writer)
        self._connections.add(connection)
        try:
            while True:
                try:
                    line = await reader.readline()
                except ValueError:
                    message = f"request is longer than {REQUEST_LINE_LIMIT} bytes"
                    connection.send(_error_reply(None, "invalid_request", message))
                    break
                except OSError:
                    break
                if not line.endswith(b"\n"):
                    break
                if line.strip():
                    connection.send(await self._answer(line, connection))
        finally:
            self._connections.discard(connection)
            await connection.finish()

    async def _answer(self, line: bytes, connection: _Connection) -> dict[str, Any]:
        """Ответ на одну строку запроса; никогда не бросает исключение."""
        request_id = None
        try:
            data = _decode(line)
            request_id = _request_id(data)
            method, params = _call(data)
            result = await self._dispatch(method, params, connection)
        except EngineError as error:
            return _error_reply(request_id, error.code, error.message)
        except Exception as error:
            log.exception("IPC request failed")
            return _error_reply(request_id, "internal_error", f"internal error: {error}")
        return {"id": request_id, "result": result}

    async def _dispatch(self, method: str, params: Mapping[str, Any], connection: _Connection) -> dict[str, Any]:
        """Проверяет параметры и выполняет метод.

        `subscribe` не ждёт ничего после регистрации, поэтому ответ попадает в очередь
        клиента раньше любого события.
        """
        allowed = _METHODS.get(method)
        if allowed is None:
            raise EngineError("unknown_method", f"unknown method {method!r}")
        extra = sorted(set(params) - allowed)
        if extra:
            raise EngineError("invalid_request", f"unknown parameter {extra[0]!r} for {method}")
        monitor = params.get("monitor")
        if monitor is not None and not isinstance(monitor, str):
            raise EngineError("invalid_request", "monitor must be a string")
        number = 0
        if "number" in allowed:
            try:
                number = check_number(params.get("number"))
            except InvalidWorkspaceNumber as error:
                raise EngineError("invalid_number", str(error)) from error

        match method:
            case "state":
                return self._current().to_json()
            case "subscribe":
                connection.subscribed = True
                return self._current().to_json()
            case "switch":
                state = await self._controller.switch(number, monitor)
            case "move":
                state = await self._controller.move(number)
            case _:
                state = await self._controller.toggle(monitor)
        self._publish(state)
        if state.error is not None:
            raise EngineError("command_failed", state.error)
        return state.to_json()

    def _current(self) -> PublicState:
        return self._latest or self._controller.state()

    def _publish(self, state: PublicState) -> None:
        """Запоминает состояние и рассылает подписчикам, если вырос `revision` или сменился `error`."""
        latest = self._latest
        if latest is not None:
            if state.revision < latest.revision:
                return
            if state.revision == latest.revision and state.error == latest.error:
                return
        self._latest = state
        message = {"event": "state", "state": state.to_json()}
        for connection in list(self._connections):
            if connection.subscribed:
                connection.send(message)

    async def _reconcile(self, event: HyprEvent) -> None:
        """Сверка; без изменений публикуется последнее состояние без ошибки."""
        try:
            state = await self._controller.reconcile(event)
        except Exception:
            log.exception("reconciliation failed")
            return
        self._publish(state if state is not None else self._controller.state())

    async def _follow_events(self) -> None:
        low, high = self._delay
        delay = low
        while True:
            try:
                async with contextlib.aclosing(self._events()) as stream:
                    async for event in stream:
                        delay = low
                        await self._reconcile(event)
                log.warning("Hyprland event socket closed; reconnecting in %gs", delay)
            except Exception as error:
                log.warning("Hyprland event socket failed: %s; reconnecting in %gs", error, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, high)
            await self._reconcile(_RECONNECTED)


def _claim(path: Path) -> None:
    """Готовит каталог `0700` и убирает файл сокета, который никто не слушает."""
    directory = path.parent
    try:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(directory, 0o700)
        info = os.lstat(path)
    except FileNotFoundError:
        return
    except OSError as error:
        raise ServerError(f"cannot prepare {directory}: {error}") from error
    if not stat.S_ISSOCK(info.st_mode):
        raise ServerError(f"{path} exists and is not a socket")
    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    probe.settimeout(1.0)
    try:
        probe.connect(str(path))
    except ConnectionRefusedError:
        path.unlink(missing_ok=True)
        log.info("removed stale socket %s", path)
        return
    except FileNotFoundError:
        return
    except OSError as error:
        raise ServerError(f"cannot check {path}: {error}") from error
    finally:
        probe.close()
    raise ServerError(f"another quietline-engine is already running on {path}")


def _decode(line: bytes) -> dict[str, Any]:
    """Объект запроса или `EngineError("invalid_request")`."""
    try:
        data = json.loads(line)
    except ValueError as error:
        raise EngineError("invalid_request", "request is not valid JSON") from error
    if not isinstance(data, dict):
        raise EngineError("invalid_request", "request must be a JSON object")
    return data


def _request_id(data: Mapping[str, Any]) -> str | int:
    request_id = data.get("id")
    if type(request_id) not in (str, int):
        raise EngineError("invalid_request", "request id must be a string or an integer")
    return request_id


def _call(data: Mapping[str, Any]) -> tuple[str, Mapping[str, Any]]:
    """`method` и `params` запроса; `params` по умолчанию — пустой объект."""
    method = data.get("method")
    if not isinstance(method, str):
        raise EngineError("invalid_request", "request method must be a string")
    params = data.get("params", {})
    if not isinstance(params, dict):
        raise EngineError("invalid_request", "request params must be an object")
    return method, params


def _error_reply(request_id: str | int | None, code: str, message: str) -> dict[str, Any]:
    return {"id": request_id, "error": {"code": code, "message": message}}


def request(path: Path, method: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Отправляет один запрос и возвращает `result`.

    Ответ `error` — `EngineError` с его кодом; нет связи с сервисом — код `unavailable`.
    """
    line = json.dumps({"id": 1, "method": method, "params": dict(params or {})}).encode() + b"\n"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(CLIENT_TIMEOUT_SECONDS)
        try:
            sock.connect(str(path))
        except OSError as error:
            raise EngineError(
                "unavailable", f"cannot connect to quietline-engine at {path} ({error}); is 'quietline-engine serve' running?"
            ) from error
        try:
            sock.sendall(line)
            with sock.makefile("rb") as stream:
                raw = stream.readline()
        except OSError as error:
            raise EngineError("unavailable", f"lost connection to quietline-engine: {error}") from error
    try:
        reply = json.loads(raw)
    except ValueError as error:
        raise EngineError("unavailable", "quietline-engine closed the connection without a reply") from error
    if "error" in reply:
        raise EngineError(str(reply["error"]["code"]), str(reply["error"]["message"]))
    return reply["result"]
