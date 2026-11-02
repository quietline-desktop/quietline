import QtQuick
import QtQuick.Layouts
import Quickshell.Io
import Quickshell.Hyprland
import Quickshell.Services.UPower
import ".."
import "../controls"
import "../logic/Models.js" as Models

// Раскладка основной клавиатуры и батарея в правом верхнем углу экрана блокировки и экрана
// входа: белым поверх обоев. Раскладка обновляется при её смене.
RowLayout {
    id: root
    property string layout: ""
    property bool capsLocked: false
    spacing: 14

    Process {
        id: devices
        command: ["hyprctl", "-j", "devices"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var keyboards = JSON.parse(text).keyboards || [];
                    var main = keyboards.find(keyboard => keyboard.main) || keyboards[0] || null;
                    root.layout = main ? Models.layoutCode(main, {}, Lang.s) : "";
                    root.capsLocked = !!main && main.capsLock === true;
                } catch (_) { root.layout = ""; }
            }
        }
    }
    Connections {
        target: Hyprland
        function onRawEvent(event) { if (event.name === "activelayout" && !devices.running) devices.running = true; }
    }
    Timer {
        interval: 1000; repeat: true; running: root.visible
        onTriggered: if (!devices.running) devices.running = true
    }

    Rectangle {
        visible: root.layout.length > 0
        implicitWidth: layoutText.implicitWidth + 8; implicitHeight: 16
        radius: 4
        color: "transparent"
        border.width: 1.5; border.color: "#ffffff"
        Text {
            id: layoutText
            renderType: Text.CurveRendering
            anchors.centerIn: parent
            anchors.verticalCenterOffset: 0.75
            text: root.layout
            color: "#ffffff"
            font.family: Theme.sans; font.pixelSize: 10; font.weight: Font.Bold
        }
    }
    Icon {
        visible: !!UPower.displayDevice && UPower.displayDevice.isPresent
        name: UPower.onBattery ? "battery_full" : "battery_charging_full"
        filled: true
        size: 18
        color: "#ffffff"
    }
}
