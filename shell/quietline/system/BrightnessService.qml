import QtQuick
import Quickshell
import Quickshell.Io
import "../logic/Models.js" as Models

// Яркость встроенного экрана через brightnessctl (logind разрешает это активному сеансу).
// Внешние мониторы без устройства подсветки управления не получают.
Scope {
    id: root
    property bool supported: false
    property string device: ""
    property int percent: 0
    // Последнее запрошенное значение; -1 — запросов нет.
    property int target: -1
    // Значение записи в процессе или последней записанной.
    property int sent: -1
    function set(value) {
        if (!supported) return;
        target = Math.max(1, Math.min(100, Math.round(value)));
        percent = target;
        flush();
        throttle.start();
    }
    // Не больше одной записи за раз и одной за 150 мс: яркость меняется прямо при перетаскивании.
    function flush() {
        if (writer.running || target < 1 || target === sent) return;
        var args = Models.brightnessArgs(device, target);
        if (!args) return;
        sent = target;
        writer.command = args;
        writer.running = true;
    }
    Process {
        id: reader
        command: ["brightnessctl", "-m", "-c", "backlight"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                var value = Models.parseBrightness(text);
                root.supported = !!value;
                if (!value) return;
                root.device = value.device;
                if (root.target < 0) root.percent = value.percent;
            }
        }
    }
    Process {
        id: writer
        onRunningChanged: {
            if (running) return;
            if (root.target === root.sent) { root.target = -1; root.sent = -1; reader.running = true; }
            else root.flush();
        }
    }
    Timer {
        id: throttle
        interval: 150; repeat: true
        onTriggered: { root.flush(); if (root.target < 0) stop(); }
    }
    Timer { interval: 10000; repeat: true; running: true; onTriggered: { if (!reader.running && root.target < 0) reader.running = true; } }
}
