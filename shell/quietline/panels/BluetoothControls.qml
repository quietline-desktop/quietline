import QtQuick
import QtQuick.Layouts
import ".."
import "../controls"
import "../inputs"

// Bluetooth: питание и подключённые устройства; в полном виде — поиск, сопряжение и «Забыть».
ColumnLayout {
    id: root
    required property var bluetooth
    property bool compact: true
    spacing: 6
    Text {
        renderType: Text.CurveRendering
        visible: !root.bluetooth.available
        text: Lang.s.btNotFound
        color: Theme.text2; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
    }
    ShellSwitch {
        visible: root.bluetooth.available
        Layout.fillWidth: true
        text: "Bluetooth" + (root.bluetooth.connected.length ? " · " + Lang.f(Lang.s.btConnectedCount, root.bluetooth.connected.length) : "")
        checked: root.bluetooth.enabled
        onToggled: root.bluetooth.setEnabled(checked)
    }
    Repeater {
        model: !root.bluetooth.enabled ? [] : root.compact ? root.bluetooth.connected : root.bluetooth.devices
        delegate: RowLayout {
            id: deviceRow
            required property var modelData
            Layout.fillWidth: true
            Text {
                renderType: Text.CurveRendering
                Layout.fillWidth: true
                text: root.bluetooth.label(deviceRow.modelData)
                    + (deviceRow.modelData.connected ? " · " + Lang.s.btConnected : deviceRow.modelData.paired ? " · " + Lang.s.btPaired : "")
                    + (deviceRow.modelData.batteryAvailable ? " · " + Math.round(deviceRow.modelData.battery * 100) + "%" : "")
                color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.fontSize
                elide: Text.ElideRight
            }
            ShellButton {
                visible: deviceRow.modelData.paired
                text: deviceRow.modelData.connected ? Lang.s.btDisconnect : Lang.s.connect
                onClicked: root.bluetooth.toggleDevice(deviceRow.modelData)
            }
            ShellButton {
                visible: !root.compact && !deviceRow.modelData.paired
                text: deviceRow.modelData.pairing ? Lang.s.btPairing : Lang.s.btPair
                enabled: !deviceRow.modelData.pairing
                onClicked: root.bluetooth.pair(deviceRow.modelData)
            }
            ShellButton {
                visible: !root.compact && deviceRow.modelData.paired
                text: Lang.s.btForget
                onClicked: root.bluetooth.forget(deviceRow.modelData)
            }
        }
    }
    ShellButton {
        visible: !root.compact && root.bluetooth.enabled
        text: root.bluetooth.scanning ? Lang.s.btStopScan : Lang.s.btScan
        onClicked: root.bluetooth.setScanning(!root.bluetooth.scanning)
    }
}
