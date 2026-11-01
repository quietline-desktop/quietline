import QtQuick
import QtQuick.Layouts
import ".."
import "../controls"
import "../inputs"

// Страница «Bluetooth» окна «Настройки»: питание адаптера и устройства — подключение,
// сопряжение, «Забыть» и поиск новых устройств.
ColumnLayout {
    id: root
    required property var bluetooth
    spacing: 18

    SettingsGroup {
        SettingsRow {
            symbol: root.bluetooth.enabled ? "bluetooth" : "bluetooth_disabled"
            symbolBackground: root.bluetooth.enabled ? Theme.accent : Theme.fill2
            symbolColor: root.bluetooth.enabled ? Theme.accentForeground : Theme.text
            label: "Bluetooth"
            note: !root.bluetooth.available ? Lang.s.btNotFound
                : !root.bluetooth.enabled ? Lang.s.btOff
                : root.bluetooth.connected.length ? Lang.f(Lang.s.btConnectedCount, root.bluetooth.connected.length) : Lang.s.btOn
            ShellSwitch {
                visible: root.bluetooth.available
                checked: root.bluetooth.enabled
                onToggled: root.bluetooth.setEnabled(checked)
                Accessible.name: "Bluetooth"
            }
        }
    }

    SettingsGroup {
        visible: root.bluetooth.enabled
        title: Lang.s.btDevices
        Repeater {
            model: root.bluetooth.devices
            delegate: SettingsRow {
                id: deviceRow
                required property var modelData
                symbol: modelData.icon && modelData.icon.indexOf("audio") >= 0 ? "headphones"
                      : modelData.icon && modelData.icon.indexOf("input") >= 0 ? "keyboard" : "bluetooth"
                symbolBackground: modelData.connected ? Theme.accent : Theme.fill2
                symbolColor: modelData.connected ? Theme.accentForeground : Theme.text
                label: root.bluetooth.label(modelData)
                note: (modelData.connected ? Lang.s.btConnected : modelData.paired ? Lang.s.btPaired : "")
                    + (modelData.batteryAvailable ? (modelData.connected || modelData.paired ? " · " : "") + Math.round(modelData.battery * 100) + "%" : "")
                ShellButton {
                    visible: deviceRow.modelData.paired
                    implicitHeight: 26; selected: true
                    text: deviceRow.modelData.connected ? Lang.s.btDisconnect : Lang.s.connect
                    onClicked: root.bluetooth.toggleDevice(deviceRow.modelData)
                }
                ShellButton {
                    visible: !deviceRow.modelData.paired
                    implicitHeight: 26; selected: true
                    text: deviceRow.modelData.pairing ? Lang.s.btPairing : Lang.s.btPair
                    enabled: !deviceRow.modelData.pairing
                    onClicked: root.bluetooth.pair(deviceRow.modelData)
                }
                ShellButton {
                    visible: deviceRow.modelData.paired
                    implicitHeight: 26; selected: true
                    text: Lang.s.btForget
                    onClicked: root.bluetooth.forget(deviceRow.modelData)
                }
            }
        }
        SettingsRow {
            visible: root.bluetooth.devices.length === 0
            note: root.bluetooth.scanning ? Lang.s.btSearching : Lang.s.btNoDevices
        }
        SettingsRow {
            label: root.bluetooth.scanning ? Lang.s.btStopScan : Lang.s.btScan
            clickable: true
            onClicked: root.bluetooth.setScanning(!root.bluetooth.scanning)
            Icon { name: root.bluetooth.scanning ? "stop_circle" : "search"; size: 18; color: Theme.text2 }
        }
    }
}
