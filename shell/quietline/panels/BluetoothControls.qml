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
        visible: !root.bluetooth.available
        text: "Bluetooth-адаптер не найден"
        color: Theme.muted; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
    }
    ShellSwitch {
        visible: root.bluetooth.available
        Layout.fillWidth: true
        text: "Bluetooth" + (root.bluetooth.connected.length ? " · подключено: " + root.bluetooth.connected.length : "")
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
                Layout.fillWidth: true
                text: root.bluetooth.label(deviceRow.modelData)
                    + (deviceRow.modelData.connected ? " · подключено" : deviceRow.modelData.paired ? " · сопряжено" : "")
                    + (deviceRow.modelData.batteryAvailable ? " · " + Math.round(deviceRow.modelData.battery * 100) + "%" : "")
                color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.fontSize
                elide: Text.ElideRight
            }
            ShellButton {
                visible: deviceRow.modelData.paired
                text: deviceRow.modelData.connected ? "Отключить" : "Подключить"
                onClicked: root.bluetooth.toggleDevice(deviceRow.modelData)
            }
            ShellButton {
                visible: !root.compact && !deviceRow.modelData.paired
                text: deviceRow.modelData.pairing ? "Сопряжение…" : "Сопрячь"
                enabled: !deviceRow.modelData.pairing
                onClicked: root.bluetooth.pair(deviceRow.modelData)
            }
            ShellButton {
                visible: !root.compact && deviceRow.modelData.paired
                text: "Забыть"
                onClicked: root.bluetooth.forget(deviceRow.modelData)
            }
        }
    }
    ShellButton {
        visible: !root.compact && root.bluetooth.enabled
        text: root.bluetooth.scanning ? "Остановить поиск" : "Найти устройства"
        onClicked: root.bluetooth.setScanning(!root.bluetooth.scanning)
    }
}
