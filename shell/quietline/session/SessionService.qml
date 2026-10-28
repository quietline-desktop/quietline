import QtQuick
import Quickshell
import Quickshell.Io
import "../logic/Models.js" as Models

// Действия сеанса через `quietline-shell`: блокировка сразу, выход, перезагрузка и
// выключение — после корректного закрытия окон. Оставшиеся окна приходят списком `remaining`.
Scope {
    id: root
    property bool busy: false
    // Выполняемое или последнее действие: `logout`, `reboot`, `poweroff`.
    property string action: ""
    property var remaining: []
    property string errorMessage: ""

    function lock() { Quickshell.execDetached(["quietline-shell", "lock"]); }
    function end(name) {
        if (busy || Models.SESSION_ACTIONS.indexOf(name) < 0) return;
        busy = true;
        action = name;
        remaining = [];
        errorMessage = "";
        ending.answered = false;
        ending.command = ["quietline-shell", "session", name];
        ending.running = true;
    }
    function reset() { if (!busy) { action = ""; remaining = []; errorMessage = ""; } }

    Process {
        id: ending
        property bool answered: false
        stdout: StdioCollector {
            onStreamFinished: {
                ending.answered = true;
                var data;
                try { data = JSON.parse(text); }
                catch (_) { root.errorMessage = Models.sessionErrorText(root.action, "quietline-shell returned no JSON"); return; }
                if (data.error) root.errorMessage = Models.sessionErrorText(root.action, data.error);
                else if (!data.done) root.remaining = data.remaining || [];
            }
        }
        // Незапустившийся процесс не даёт сигнала завершения, поэтому итог подводится по `running`.
        onRunningChanged: {
            if (running) return;
            Qt.callLater(function() {
                if (!ending.answered) root.errorMessage = Models.sessionErrorText(root.action, "quietline-shell did not respond");
                root.busy = false;
            });
        }
    }
}
