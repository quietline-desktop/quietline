import QtQuick
import Quickshell
import Quickshell.Io

// Поиск файлов для панели поиска: `quietline-shell files` с задержкой 250 мс после ввода.
// Ответ на устаревший запрос не применяется; запрос короче двух символов файлов не ищет.
Scope {
    id: root
    property string query: ""
    property var files: []
    property string errorMessage: ""
    readonly property string home: Quickshell.env("HOME") || ""

    onQueryChanged: { files = []; errorMessage = ""; delay.restart(); }

    Timer {
        id: delay
        interval: 250
        onTriggered: {
            if (root.query.trim().length < 2) return;
            if (finder.running) { restart(); return; }
            finder.asked = root.query;
            finder.command = ["quietline-shell", "files", root.query.trim(), "--limit", "15"];
            finder.running = true;
        }
    }
    Process {
        id: finder
        property string asked: ""
        stdout: StdioCollector {
            onStreamFinished: {
                if (finder.asked !== root.query) return;
                try {
                    var data = JSON.parse(text);
                    root.files = data.files || [];
                    root.errorMessage = data.error ? "Поиск файлов недоступен: " + data.error : "";
                } catch (_) { root.errorMessage = "Поиск файлов недоступен: quietline-shell не ответил"; }
            }
        }
    }
}
