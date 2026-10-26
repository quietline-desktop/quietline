import QtQuick
import Quickshell
import Quickshell.Io
import "services"

// Отдельный корень для проверки клиента движка без панели: IPC `testClient`.
ShellRoot {
    EngineClient { id: client }
    IpcHandler {
        target: "testClient"
        function status(): string { return JSON.stringify({ready: client.ready, revision: client.revision, busy: client.busy, error: client.message, state: client.state}); }
        function toggle(monitor: string): void { client.toggle(monitor); }
    }
}
