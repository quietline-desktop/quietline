import QtQuick
import QtQuick.Layouts
import ".."
import "../controls"
import "../inputs"

// Быстрые настройки: звук, яркость, Wi-Fi, Bluetooth и переход в окно «Настройки».
ColumnLayout {
    id: root
    required property var services
    // Яркость предлагает только панель встроенного экрана.
    property bool builtinScreen: false
    signal networkRequested()
    signal settingsRequested()
    spacing: 12
    Text { text: "Быстрые настройки"; color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.titleFontSize; font.bold: true }
    AudioControls { audio: root.services.audio; compact: true; Layout.fillWidth: true }
    Loader {
        active: root.services.brightness.supported && root.builtinScreen
        visible: active
        Layout.fillWidth: true
        sourceComponent: Component { BrightnessControls { brightness: root.services.brightness } }
    }
    RowLayout {
        visible: !!root.services.network.wifiDevice
        Layout.fillWidth: true
        ShellSwitch {
            Layout.fillWidth: true
            text: "Wi-Fi" + (root.services.network.wifiDevice && root.services.network.wifiDevice.profile
                             ? " · " + root.services.network.wifiDevice.profile : "")
            checked: root.services.network.wifi.enabled
            enabled: !root.services.network.busy
            onToggled: root.services.network.setWifi(checked)
        }
        ShellButton { text: "Сеть…"; hint: "Открыть сетевую панель"; onClicked: root.networkRequested() }
    }
    Loader {
        active: root.services.bluetooth.available
        visible: active
        Layout.fillWidth: true
        sourceComponent: Component { BluetoothControls { bluetooth: root.services.bluetooth; compact: true } }
    }
    ShellButton {
        visible: !!root.services.settings
        Layout.fillWidth: true
        text: "Все настройки"
        hint: "Открыть окно «Настройки» · Super+I"
        onClicked: root.settingsRequested()
    }
}
