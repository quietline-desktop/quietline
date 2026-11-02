pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// Оформление из `quietline-shell appearance`: тема окружения, цвет и размер указателя, процент
// заряда на панели. Читает
// настройки при старте; `update` меняет значения в оболочке сразу (Theme перекрашивает поверхности),
// затем записывает и применяет их через `--set` и перечитывает файл. Пока ответа нет — тёмная
// тема, тёмный указатель 24 px.
Singleton {
    id: root
    // `dark` | `light`
    property string theme: "dark"
    // `dark` | `light`
    property string cursor: "dark"
    // 24 | 36 | 48
    property int cursorSize: 24
    // Процент заряда рядом с батареей на панели.
    property bool batteryPercent: false
    readonly property bool light: theme === "light"
    // Текст последней ошибки чтения или записи; пусто — ошибок нет.
    property string error: ""
    // Применились ли схема приложений, Hyprland и указатель при последней записи.
    property bool applied: true
    // Изменения, пришедшие во время записи: отправляются следующей записью.
    property var pending: null

    // Сохраняет часть настроек (`{theme, cursor, cursorSize, batteryPercent}`) и применяет их.
    function update(changes) {
        apply(changes);
        if (writer.running) {
            pending = Object.assign({}, pending || {}, changes);
            return;
        }
        error = "";
        writer.answered = false;
        writer.command = ["quietline-shell", "appearance", "--set", JSON.stringify(changes)];
        writer.running = true;
    }
    function reload() {
        if (reader.running) return;
        reader.answered = false;
        reader.running = true;
    }
    function apply(data) {
        if (data.theme === "dark" || data.theme === "light") theme = data.theme;
        if (data.cursor === "dark" || data.cursor === "light") cursor = data.cursor;
        if ([24, 36, 48].indexOf(data.cursorSize) >= 0) cursorSize = data.cursorSize;
        if (typeof data.batteryPercent === "boolean") batteryPercent = data.batteryPercent;
    }
    function failure(key, detail) { error = Lang.s[key] + (detail ? ": " + detail : ""); }

    Process {
        id: reader
        property bool answered: false
        command: ["quietline-shell", "appearance"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                reader.answered = true;
                var data;
                try { data = JSON.parse(text); }
                catch (_) { root.failure("appearanceReadFailed", "quietline-shell returned no JSON"); return; }
                if (data.error) root.failure("appearanceReadFailed", data.error);
                else root.apply(data);
            }
        }
        // Незапустившийся процесс не даёт сигнала завершения, поэтому итог подводится по `running`.
        onRunningChanged: {
            if (running) return;
            Qt.callLater(function() {
                if (!reader.answered) root.failure("appearanceReadFailed", "quietline-shell did not respond");
            });
        }
    }
    Process {
        id: writer
        property bool answered: false
        stdout: StdioCollector {
            onStreamFinished: {
                writer.answered = true;
                var data;
                try { data = JSON.parse(text); }
                catch (_) { root.failure("appearanceSaveFailed", "quietline-shell returned no JSON"); return; }
                if (data.error) root.failure("appearanceSaveFailed", data.error);
                else root.applied = data.applied !== false;
            }
        }
        onRunningChanged: {
            if (running) return;
            Qt.callLater(function() {
                if (!writer.answered) root.failure("appearanceSaveFailed", "quietline-shell did not respond");
                var next = root.pending;
                root.pending = null;
                if (next) root.update(next);
                else root.reload();
            });
        }
    }
}
