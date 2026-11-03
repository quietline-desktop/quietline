import QtQuick
import Quickshell
import Quickshell.Io
import ".."

// Поиск файлов для панели поиска: `quietline-shell files` с задержкой 250 мс после ввода.
// Ответ на устаревший запрос не применяется; запрос короче двух символов файлов не ищет.
// Прежние файлы при новом запросе не сбрасываются — панель сужает их сама, пока не придёт
// ответ; `pending` — ответа на текущий запрос ещё нет.
Scope {
    id: root
    property string query: ""
    property var files: []
    property string errorMessage: ""
    property string answered: ""
    readonly property bool pending: query.trim().length >= 2 && answered !== query
    readonly property string home: Quickshell.env("HOME") || ""

    onQueryChanged: {
        if (query.trim().length < 2) { files = []; errorMessage = ""; answered = query; }
        delay.restart();
    }

    Timer {
        id: delay
        interval: 250
        onTriggered: {
            if (root.query.trim().length < 2) return;
            if (finder.running) { restart(); return; }
            finder.asked = root.query;
            finder.command = ["quietline-shell", "files", "--limit", "15", "--", root.query.trim()];
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
                    root.errorMessage = data.error ? Lang.f(Lang.s.searchFilesUnavailable, data.error) : "";
                } catch (_) { root.errorMessage = Lang.s.searchFilesNoReply; }
                root.answered = finder.asked;
            }
        }
    }
}
