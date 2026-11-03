import QtQuick
import Quickshell
import Quickshell.Io
import "../.."

// Настройки одной подкоманды `quietline-shell` для страницы «Настроек»: `load()` читает
// `command`, `set(change)` сразу показывает изменение в `values` и пишет его через
// `command --set JSON`; изменения во время записи и в течение `delay` мс (ползунки) копятся
// и уходят одной записью. Ответ записи заменяет `values`; ошибка — текст `error` с подписью
// `failure`, после неё значения перечитываются.
Scope {
    id: root
    required property var command
    property string failure: ""
    property int delay: 0
    property var values: null
    property string error: ""
    property bool applied: true
    readonly property bool busy: writer.running
    property var pending: null

    function load() {
        if (!reader.running && !writer.running) reader.running = true;
    }
    function set(change) {
        values = Object.assign({}, values || {}, change);
        pending = Object.assign({}, pending || {}, change);
        if (delay > 0) debounce.restart();
        else flush();
    }
    function flush() {
        if (!pending || writer.running) return;
        error = "";
        writer.command = root.command.concat(["--set", JSON.stringify(pending)]);
        pending = null;
        writer.running = true;
    }
    function receive(text, writing) {
        var data;
        try { data = JSON.parse(text); } catch (_) { data = {error: "quietline-shell returned no JSON"}; }
        if (data.error) {
            error = failure + ": " + data.error;
            if (writing) reader.running = true;
            return;
        }
        if (writing) applied = data.applied !== false;
        if (!pending) values = data;
    }

    Timer { id: debounce; interval: root.delay; onTriggered: root.flush() }
    Process {
        id: reader
        command: root.command
        stdout: StdioCollector { onStreamFinished: root.receive(text, false) }
    }
    Process {
        id: writer
        stdout: StdioCollector { onStreamFinished: root.receive(text, true) }
        onRunningChanged: { if (!running && root.pending && !debounce.running) Qt.callLater(root.flush); }
    }
}
