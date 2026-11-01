import QtQuick
import Quickshell
import Quickshell.Io
import ".."
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
    // Результат прошлого действия (оставшиеся приложения, ошибка) держится до нового действия
    // или явной отмены: меню показывает его и после повторного открытия.
    // `force` — выполнить действие сразу, не закрывая окна (после списка оставшихся приложений).
    function end(name, force) {
        if (busy || Models.SESSION_ACTIONS.indexOf(name) < 0) return;
        busy = true;
        action = name;
        remaining = [];
        errorMessage = "";
        ending.answered = false;
        ending.command = force ? ["quietline-shell", "session", name, "--force"] : ["quietline-shell", "session", name];
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
                catch (_) { root.errorMessage = Models.sessionErrorText(root.action, "quietline-shell returned no JSON", Lang.s); return; }
                if (data.error) root.errorMessage = Models.sessionErrorText(root.action, data.error, Lang.s);
                else if (!data.done) root.remaining = data.remaining || [];
            }
        }
        // Незапустившийся процесс не даёт сигнала завершения, поэтому итог подводится по `running`.
        onRunningChanged: {
            if (running) return;
            Qt.callLater(function() {
                if (!ending.answered) root.errorMessage = Models.sessionErrorText(root.action, "quietline-shell did not respond", Lang.s);
                root.busy = false;
            });
        }
    }
}
