pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "logic/Strings.js" as Strings

// Язык и регион оболочки из `quietline-shell region`: таблица строк текущего языка `s`,
// форматы времени и даты, раскладки. Читает настройки при старте и после `update`; пока
// ответа нет — язык по `LANG` окружения и форматы по умолчанию для этого языка.
Singleton {
    id: root
    property string language: String(Quickshell.env("LANG") || "").indexOf("ru") === 0 ? "ru" : "en"
    // `24h` | `12h`
    property string clock: language === "ru" ? "24h" : "12h"
    // `dmy` | `ymd` | `mdy`
    property string date: language === "ru" ? "dmy" : "mdy"
    property var layouts: ["us", "ru"]
    property string toggle: "grp:lalt_lshift_toggle"
    // Текст последней ошибки чтения или записи настроек; пусто — ошибок нет.
    property string error: ""
    readonly property var s: Strings.table(language)
    readonly property var locale: Qt.locale(Strings.localeName(language))
    // Изменения, пришедшие во время записи: отправляются следующей записью.
    property var pending: null

    // Строка таблицы с подстановкой остальных аргументов: `f(s.bindMove, 3)`.
    function f(template) { return Strings.format(template, Array.prototype.slice.call(arguments, 1)); }
    function time(value) { return value.toLocaleTimeString(locale, Strings.timeFormat(clock)); }
    function shortDate(value) { return value.toLocaleDateString(locale, Strings.dateFormat(date)); }
    function longDate(value) { return value.toLocaleDateString(locale, "dddd, d MMMM"); }

    // Сохраняет часть настроек (`{language, clock, date, layouts, toggle}`) и перечитывает их.
    function update(changes) {
        if (writer.running) {
            pending = Object.assign({}, pending || {}, changes);
            return;
        }
        error = "";
        writer.answered = false;
        writer.command = ["quietline-shell", "region", "--set", JSON.stringify(changes)];
        writer.running = true;
    }
    function reload() {
        if (reader.running) return;
        reader.answered = false;
        reader.running = true;
    }
    function apply(data) {
        if (typeof data.language === "string") language = data.language === "ru" ? "ru" : "en";
        if (typeof data.clock === "string") clock = data.clock;
        if (typeof data.date === "string") date = data.date;
        if (Array.isArray(data.layouts)) layouts = data.layouts;
        if (typeof data.toggle === "string") toggle = data.toggle;
    }
    function failure(key, detail) { error = s[key] + (detail ? ": " + detail : ""); }

    Process {
        id: reader
        property bool answered: false
        command: ["quietline-shell", "region"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                reader.answered = true;
                var data;
                try { data = JSON.parse(text); }
                catch (_) { root.failure("regionReadFailed", "quietline-shell returned no JSON"); return; }
                if (data.error) root.failure("regionReadFailed", data.error);
                else root.apply(data);
            }
        }
        // Незапустившийся процесс не даёт сигнала завершения, поэтому итог подводится по `running`.
        onRunningChanged: {
            if (running) return;
            Qt.callLater(function() {
                if (!reader.answered) root.failure("regionReadFailed", "quietline-shell did not respond");
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
                catch (_) { root.failure("regionSaveFailed", "quietline-shell returned no JSON"); return; }
                if (data.error) root.failure("regionSaveFailed", data.error);
            }
        }
        onRunningChanged: {
            if (running) return;
            Qt.callLater(function() {
                if (!writer.answered) root.failure("regionSaveFailed", "quietline-shell did not respond");
                var next = root.pending;
                root.pending = null;
                if (next) root.update(next);
                else root.reload();
            });
        }
    }
}
