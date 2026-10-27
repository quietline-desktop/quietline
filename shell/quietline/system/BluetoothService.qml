import QtQuick
import Quickshell
import Quickshell.Bluetooth

// Bluetooth адаптера по умолчанию: питание, поиск, устройства (подключённые и сопряжённые — первыми).
Scope {
    id: root
    readonly property var adapter: Bluetooth.defaultAdapter
    readonly property bool available: !!adapter
    readonly property bool enabled: available && adapter.enabled
    readonly property bool scanning: available && adapter.discovering
    readonly property var devices: !available ? [] : Bluetooth.devices.values.filter(device => device.adapter === adapter)
        .sort((a, b) => (b.connected - a.connected) || (b.paired - a.paired) || root.label(a).localeCompare(root.label(b)))
    readonly property var connected: devices.filter(device => device.connected)
    function label(device) { return device.name || device.deviceName || device.address; }
    function setEnabled(on) { if (available) adapter.enabled = on; }
    function setScanning(on) { if (enabled) adapter.discovering = on; }
    function toggleDevice(device) { if (device.connected) device.disconnect(); else device.connect(); }
    function pair(device) { device.trusted = true; device.pair(); }
    function forget(device) { device.forget(); }
}
