import QtQuick
import Quickshell
import Quickshell.Io

// История буфера через `quietline-shell clipboard`: список, восстановление, удаление,
// очистка и пауза записи. Превью картинок запрашиваются по одной и кешируются в `images`.
Scope {
    id: root
    property var entries: []
    property bool paused: false
    property bool busy: false
    property string errorMessage: ""
    property var images: ({})
    property var imageQueue: []
    // Выбранная запись возвращена в буфер.
    signal restored()

    function refresh() { if (!lister.running) lister.running = true; }
    function run(args, kind) {
        if (busy) return;
        busy = true;
        errorMessage = "";
        action.kind = kind;
        action.answered = false;
        action.command = ["quietline-shell", "clipboard"].concat(args);
        action.running = true;
    }
    function restore(id) { run(["restore", "--id", id], "restore"); }
    function remove(id) { run(["delete", "--id", id], "delete"); }
    function wipe() { run(["wipe"], "wipe"); }
    function setPaused(on) { run(["pause", on ? "--on" : "--off"], "pause"); }
    function nextImage() {
        if (imager.running || imageQueue.length === 0) return;
        imager.entryId = imageQueue[0];
        imageQueue = imageQueue.slice(1);
        imager.command = ["quietline-shell", "clipboard", "image", "--id", imager.entryId];
        imager.running = true;
    }

    Process {
        id: lister
        command: ["quietline-shell", "clipboard", "list"]
        stdout: StdioCollector {
            onStreamFinished: {
                var data;
                try { data = JSON.parse(text); } catch (_) { root.errorMessage = "История буфера недоступна: quietline-shell не ответил"; return; }
                if (data.error) { root.errorMessage = "История буфера недоступна: " + data.error; return; }
                root.entries = data.entries || [];
                root.paused = !!data.paused;
                root.imageQueue = root.entries.filter(entry => entry.kind === "image" && !root.images[entry.id]).map(entry => entry.id);
                root.nextImage();
            }
        }
    }
    Process {
        id: action
        property string kind: ""
        property bool answered: false
        stdout: StdioCollector {
            onStreamFinished: {
                action.answered = true;
                var data;
                try { data = JSON.parse(text); } catch (_) { data = {error: "quietline-shell returned no JSON"}; }
                if (data.error) root.errorMessage = "Действие с историей буфера не выполнено: " + data.error;
                else if (action.kind === "restore") root.restored();
                else if (action.kind === "wipe") root.images = ({});
            }
        }
        // Незапустившийся процесс не даёт сигнала завершения, поэтому итог подводится по `running`.
        onRunningChanged: {
            if (running) return;
            Qt.callLater(function() {
                if (!action.answered) root.errorMessage = "Действие с историей буфера не выполнено: quietline-shell did not respond";
                root.busy = false;
                root.refresh();
            });
        }
    }
    Process {
        id: imager
        property string entryId: ""
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var data = JSON.parse(text);
                    if (data.path) {
                        var next = Object.assign({}, root.images);
                        next[imager.entryId] = "file://" + data.path;
                        root.images = next;
                    }
                } catch (_) {}
            }
        }
        onRunningChanged: { if (!running) Qt.callLater(root.nextImage); }
    }
}
