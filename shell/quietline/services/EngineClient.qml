import QtQuick
import Quickshell
import Quickshell.Io
import "../logic/Models.js" as Models

// Клиент IPC движка: подписка на подтверждённое состояние, команды switch и toggle, переподключение.
// Каждое новое соединение подписывается заново и принимает первое состояние при любой
// ревизии: после перезапуска сервиса ревизия начинается заново. Команда одна за раз,
// с ID и таймаутом; `monitor` в командах — ключ монитора движка.
Scope {
    id: root
    property var state: null
    property bool ready: false
    property string errorMessage: "Подключение к сервису окон…"
    // Ошибка команды держится дольше следующего снимка, который иначе сразу стёр бы её.
    property string commandError: ""
    readonly property string message: commandError || errorMessage
    property int revision: -1
    property int nextId: 10
    property int pendingId: -1
    property string pendingMonitor: ""
    property bool freshConnection: true
    readonly property bool busy: pendingId >= 0
    readonly property string socketPath: Quickshell.env("QUIETLINE_ENGINE_SOCKET") || (Quickshell.env("XDG_RUNTIME_DIR") + "/quietline/engine.sock")

    function send(method, params) {
        if (!ready || !connection.connected || busy) return;
        pendingId = nextId++;
        pendingMonitor = params.monitor || "";
        commandError = "";
        connection.write(JSON.stringify({id: pendingId, method: method, params: params}) + "\n");
        connection.flush();
        commandTimeout.restart();
    }
    function switchWorkspace(number, monitor) { send("switch", {number: number, monitor: monitor}); }
    function toggle(monitor) { send("toggle", {monitor: monitor}); }
    function retry() {
        errorMessage = "Подключение к сервису окон…";
        reconnect();
    }
    function reconnect() { if (!connection.connected) connection.connected = true; }
    function dismiss() { commandError = ""; if (ready) errorMessage = ""; }
    function receive(line) {
        var response = Models.decodeMessage(line, revision, freshConnection);
        if (response.id === pendingId) {
            pendingId = -1;
            pendingMonitor = "";
            commandTimeout.stop();
        }
        if (response.kind === "state") {
            state = response.state;
            revision = state.revision;
            freshConnection = false;
            subscriptionTimeout.stop();
            ready = true;
            errorMessage = Models.stateError(state);
        } else if (response.kind === "error" || response.kind === "invalid") {
            commandError = response.message;
        }
    }
    Socket {
        id: connection
        path: root.socketPath
        connected: true
        onConnectedChanged: {
            root.ready = false;
            root.pendingId = -1;
            commandTimeout.stop();
            if (connected) {
                root.freshConnection = true;
                root.revision = -1;
                write(JSON.stringify({id: 1, method: "subscribe", params: {}}) + "\n");
                flush();
                subscriptionTimeout.restart();
            } else {
                root.errorMessage = "Сервис окон недоступен · повторное подключение…";
            }
        }
        onError: {
            root.ready = false;
            root.errorMessage = "Сервис окон недоступен · повторное подключение…";
        }
        parser: SplitParser { onRead: data => root.receive(data) }
    }
    Timer {
        id: subscriptionTimeout
        interval: 6000
        onTriggered: { if (!root.ready) connection.connected = false; }
    }
    Timer { interval: 1500; repeat: true; running: !connection.connected; onTriggered: root.reconnect() }
    Timer { interval: 10000; running: root.commandError.length > 0; onTriggered: root.commandError = "" }
    Timer {
        id: commandTimeout
        interval: 12000
        onTriggered: {
            root.pendingId = -1;
            root.pendingMonitor = "";
            root.ready = false;
            root.commandError = "Сервис окон не ответил. Восстанавливаем состояние…";
            connection.connected = false;
        }
    }
}
