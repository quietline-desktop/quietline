import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import ".."

// Мониторы из `quietline-shell display`: подключённые (`outputs`) и сохранённые настройки
// (`monitors`). `set(output, change, confirm)` пишет поля монитора; с `confirm` изменение ждёт
// подтверждения `keep()` 15 секунд, без него прежние значения записываются обратно. Сервис
// живёт всё время работы оболочки: откат случается, даже если окно «Настройки» закрылось
// вместе со сменой режима монитора.
Scope {
    id: root
    property var outputs: []
    property var monitors: ({})
    property string error: ""
    property bool applied: true
    // Ожидающее подтверждения изменение: {output, previous: {поле: прежнее значение}}.
    property var confirming: null
    property int secondsLeft: 0
    readonly property bool busy: writer.running

    function refresh() {
        if (!reader.running) reader.running = true;
    }
    // Значение поля для отката: отсутствующее поле — значение по умолчанию.
    function previousValue(record, field) {
        if (record[field] !== undefined) return record[field];
        return field === "transform" ? 0 : "auto";
    }
    function set(output, change, confirm) {
        if (writer.running) return;
        var record = monitors[output] || {};
        var previous = {};
        for (var field in change) previous[field] = previousValue(record, field);
        error = "";
        writer.confirmChange = confirm ? {output: output, previous: previous} : null;
        writer.command = ["quietline-shell", "display", "--set", JSON.stringify(Object.assign({output: output}, change))];
        writer.running = true;
    }
    function keep() { confirming = null; countdown.stop(); }
    function revert() {
        var change = confirming;
        keep();
        if (change) set(change.output, change.previous, false);
    }
    function receive(text, writing) {
        var data;
        try { data = JSON.parse(text); } catch (_) { data = {error: "quietline-shell returned no JSON"}; }
        if (data.error) {
            error = Lang.s.displayScaleFailed + ": " + data.error;
            if (writing) reader.running = true;
            return;
        }
        monitors = data.monitors || {};
        outputs = data.outputs || [];
        if (!writing) return;
        applied = data.applied !== false;
        Hyprland.refreshMonitors();
        settle.restart();
        if (writer.confirmChange && applied) {
            confirming = writer.confirmChange;
            secondsLeft = 15;
            countdown.restart();
        }
    }

    Process {
        id: reader
        command: ["quietline-shell", "display"]
        stdout: StdioCollector { onStreamFinished: root.receive(text, false) }
    }
    Process {
        id: writer
        property var confirmChange: null
        stdout: StdioCollector { onStreamFinished: root.receive(text, true) }
    }
    // Hyprland меняет режим не мгновенно: состояние мониторов перечитывается ещё раз.
    Timer { id: settle; interval: 1200; onTriggered: root.refresh() }
    Timer {
        id: countdown
        interval: 1000; repeat: true
        onTriggered: {
            root.secondsLeft -= 1;
            if (root.secondsLeft <= 0) root.revert();
        }
    }
    Connections {
        target: Hyprland
        function onRawEvent(event) {
            if (["monitoradded", "monitorremoved", "monitoraddedv2", "monitorremovedv2"].indexOf(event.name) >= 0) root.refresh();
        }
    }
}
