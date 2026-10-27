import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Bluetooth
import Quickshell.Services.UPower
import Quickshell.Networking
import "../logic/Models.js" as Models

// Показатели панели: CPU, RAM, сеть, Bluetooth, батарея и ограничение анимаций.
Scope {
    id: root
    property var previousCpu: null
    property var cpu: null
    property var memory: null
    property var networkDetails: []
    property string networkError: ""
    // Анимации включены, пока система не попросит иного; недоступный quietline-shell их не выключает.
    property bool reducedMotion: false
    readonly property var bluetoothAdapter: Bluetooth.defaultAdapter
    readonly property bool hasBluetooth: Bluetooth.adapters.values.length > 0
    readonly property bool bluetoothEnabled: hasBluetooth && bluetoothAdapter && bluetoothAdapter.enabled
    readonly property var battery: UPower.displayDevice
    readonly property bool hasBattery: battery.ready && battery.isPresent
    readonly property var networkDevices: Networking.devices.values
    readonly property string networkSummary: networkDetails.filter(device => device.device !== "lo").map(device => device.device + (device.profile ? " · " + device.profile : "") + (device.addresses.length ? " · " + device.addresses.join(", ") : " · Нет адреса")).join("\n") || networkError || "Нет доступных сетевых интерфейсов"
    readonly property string cpuText: cpu === null ? "—" : Math.round(cpu) + "%"
    readonly property string memoryText: memory ? (memory.used / 1073741824).toFixed(1) + "/" + Math.round(memory.total / 1073741824) : "—"

    Process {
        id: network
        property bool answered: false
        command: ["quietline-shell", "network", "status"]
        running: true
        onRunningChanged: {
            if (running) { answered = false; return; }
            Qt.callLater(function() {
                if (!network.answered) { root.networkDetails = []; root.networkError = "Сводка сети недоступна: quietline-shell не ответил"; }
            });
        }
        stdout: StdioCollector {
            onStreamFinished: {
                network.answered = true;
                try {
                    var data = JSON.parse(text);
                    root.networkDetails = data.devices || [];
                    root.networkError = data.error || "";
                } catch (_) { root.networkDetails = []; root.networkError = text.length ? "Не удалось прочитать состояние сети" : "Сводка сети недоступна: quietline-shell не ответил"; }
            }
        }
    }
    Timer { interval: 5000; repeat: true; running: true; onTriggered: { if (!network.running) network.running = true; } }
    Process {
        id: metrics
        command: ["cat", "/proc/stat", "/proc/meminfo"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                var current = Models.parseCpu(text);
                root.cpu = Models.cpuUsage(root.previousCpu, current, root.cpu);
                root.previousCpu = current;
                root.memory = Models.parseMemory(text);
            }
        }
    }
    Process {
        id: motion
        command: ["quietline-shell", "motion"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                try { root.reducedMotion = JSON.parse(text).reducedMotion; }
                catch (_) { root.reducedMotion = false; }
            }
        }
    }
    Timer { interval: 2000; repeat: true; running: true; onTriggered: { if (!metrics.running) metrics.running = true; } }
    Timer { interval: 5000; repeat: true; running: true; onTriggered: { if (!motion.running) motion.running = true; } }
}
