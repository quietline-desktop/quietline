import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Services.UPower
import ".."
import "../controls"
import "../inputs"

// Пункт управления: плитки Wi‑Fi, Bluetooth, «Не беспокоить», «Не засыпать», «Снимок экрана»;
// ползунки яркости, громкости и микрофона; профиль питания; нагрузка CPU и RAM; строка
// батареи и переход в окно «Настройки». Модули — скруглённые блоки на светлой подложке.
ColumnLayout {
    id: root
    required property var services
    required property var indicators
    // Яркость предлагает только панель встроенного экрана.
    property bool builtinScreen: false
    // Сеть: сетевая панель с формами; раздел окна «Настройки»; закрыть пункт управления.
    signal networkRequested()
    signal settingsRequested(string section)
    signal closeRequested()
    spacing: 8
    readonly property var network: services.network
    readonly property var bluetooth: services.bluetooth
    readonly property var audio: services.audio
    readonly property var power: services.power

    component Module: Rectangle {
        radius: Theme.radiusModule
        color: Theme.fill
        border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.04)
    }
    component Caption: Text {
        renderType: Text.CurveRendering
        color: Theme.text
        font.family: Theme.sans; font.pixelSize: 12; font.weight: Font.DemiBold
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 8
        ColumnLayout {
            Layout.fillWidth: true; Layout.preferredWidth: 1
            Layout.alignment: Qt.AlignTop
            spacing: 8
            ControlTile {
                visible: !!root.network.wifiDevice
                Layout.fillWidth: true
                symbol: root.network.wifi.enabled ? "wifi" : "wifi_off"
                title: "Wi‑Fi"
                subtitle: !root.network.wifi.enabled ? Lang.s.quickOff
                        : root.network.wifiDevice && root.network.wifiDevice.profile ? root.network.wifiDevice.profile : Lang.s.quickNoNetwork
                checked: root.network.wifi.enabled
                expandable: true
                hint: Lang.s.quickNetworkMore
                enabled: !root.network.busy
                onToggled: root.network.setWifi(!root.network.wifi.enabled)
                onExpandRequested: root.networkRequested()
            }
            ControlTile {
                visible: !root.network.wifiDevice
                Layout.fillWidth: true
                symbol: root.network.connected ? "lan" : "wifi_off"
                title: Lang.s.settingsNetwork
                subtitle: root.network.summary
                checked: root.network.connected
                expandable: true
                hint: Lang.s.quickNetworkMore
                onToggled: root.networkRequested()
                onExpandRequested: root.networkRequested()
            }
            ControlTile {
                visible: root.bluetooth.available
                Layout.fillWidth: true
                symbol: "bluetooth"
                title: "Bluetooth"
                subtitle: !root.bluetooth.enabled ? Lang.s.quickOff
                        : root.bluetooth.connected.length ? root.bluetooth.label(root.bluetooth.connected[0]) : Lang.s.quickOn
                checked: root.bluetooth.enabled
                expandable: true
                hint: Lang.s.quickBluetoothMore
                onToggled: root.bluetooth.setEnabled(!root.bluetooth.enabled)
                onExpandRequested: root.settingsRequested("bluetooth")
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; Layout.preferredWidth: 1
            Layout.alignment: Qt.AlignTop
            spacing: 8
            ControlTile {
                Layout.fillWidth: true
                small: true
                symbol: "do_not_disturb_on"
                title: Lang.s.notificationsDnd
                checked: root.services.notifications.dnd
                onToggled: root.services.notifications.setDnd(!root.services.notifications.dnd)
            }
            ControlTile {
                Layout.fillWidth: true
                small: true
                symbol: "coffee"
                title: Lang.s.quickKeepAwake
                checked: root.services.keepAwake.active
                onToggled: root.services.keepAwake.active = !root.services.keepAwake.active
            }
            // Снимок области: пункт управления закрывается до выбора области.
            ControlTile {
                Layout.fillWidth: true
                small: true
                symbol: "screenshot_region"
                title: Lang.s.quickScreenshot
                onToggled: {
                    root.closeRequested();
                    Quickshell.execDetached(["sh", "-c", "sleep 0.3; exec quietline-shell screenshot region"]);
                }
            }
        }
    }
    Module {
        visible: root.services.brightness.supported && root.builtinScreen
        Layout.fillWidth: true
        implicitHeight: brightnessColumn.implicitHeight + 22
        ColumnLayout {
            id: brightnessColumn
            x: 12; y: 10; width: parent.width - 24
            spacing: 8
            Caption { text: Lang.s.quickDisplay }
            ShellSlider {
                Layout.fillWidth: true
                symbol: "light_mode"
                label: Lang.s.brightnessLabel
                from: 1; to: 100; stepSize: 1
                value: root.services.brightness.percent
                onMoved: root.services.brightness.set(value)
            }
        }
    }
    Module {
        visible: root.audio.available || root.audio.micAvailable
        Layout.fillWidth: true
        implicitHeight: soundColumn.implicitHeight + 22
        ColumnLayout {
            id: soundColumn
            x: 12; y: 10; width: parent.width - 24
            spacing: 8
            RowLayout {
                Layout.fillWidth: true
                Caption { text: Lang.s.quickSound }
                Text {
                    renderType: Text.CurveRendering
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignRight
                    text: root.audio.available ? (root.audio.sink.description || root.audio.sink.nickname || root.audio.sink.name) : ""
                    color: Theme.text2
                    font.family: Theme.sans; font.pixelSize: 12
                    elide: Text.ElideRight
                }
            }
            ShellSlider {
                visible: root.audio.available
                Layout.fillWidth: true
                symbol: root.audio.available && root.audio.sink.audio.muted ? "volume_off" : "volume_up"
                symbolClickable: true
                label: Lang.s.audioVolume
                to: 1.0
                value: root.audio.available ? root.audio.sink.audio.volume : 0
                opacity: root.audio.available && root.audio.sink.audio.muted ? 0.55 : 1
                onMoved: root.audio.setVolume(value)
                onSymbolClicked: root.audio.toggleMute()
            }
            ShellSlider {
                visible: root.audio.micAvailable
                Layout.fillWidth: true
                symbol: root.audio.micAvailable && root.audio.source.audio.muted ? "mic_off" : "mic"
                symbolClickable: true
                label: Lang.s.audioMic
                to: 1.0
                value: root.audio.micAvailable ? root.audio.source.audio.volume : 0
                opacity: root.audio.micAvailable && root.audio.source.audio.muted ? 0.55 : 1
                onMoved: root.audio.setMicVolume(value)
                onSymbolClicked: root.audio.toggleMicMute()
            }
        }
    }
    Module {
        visible: root.power.profilesAvailable
        Layout.fillWidth: true
        implicitHeight: 36
        SegmentedControl {
            anchors.fill: parent; anchors.margins: 3
            color: "transparent"
            showLabels: true
            segmentHeight: 30
            segmentWidth: (width - 4) / model.length
            reducedMotion: root.indicators.reducedMotion
            readonly property var values: [PowerProfile.PowerSaver, PowerProfile.Balanced, PowerProfile.Performance]
                .filter(value => value !== PowerProfile.Performance || root.power.hasPerformance)
            model: values.map(value => value === PowerProfile.PowerSaver ? {symbol: "eco", label: Lang.s.powerSaverShort, hint: Lang.s.powerSaver}
                                     : value === PowerProfile.Balanced ? {symbol: "balance", label: Lang.s.powerBalanced, hint: Lang.s.powerBalanced}
                                     : {symbol: "bolt", label: Lang.s.powerPerformanceShort, hint: Lang.s.powerPerformance})
            currentIndex: values.indexOf(root.power.profile)
            onActivated: index => root.power.setProfile(values[index])
        }
    }
    Module {
        Layout.fillWidth: true
        implicitHeight: 46
        RowLayout {
            x: 12; width: parent.width - 24
            anchors.verticalCenter: parent.verticalCenter
            spacing: 14
            component Meter: ColumnLayout {
                property string label: ""
                property string value: ""
                property real fraction: 0
                Layout.fillWidth: true; Layout.preferredWidth: 1
                spacing: 5
                Text {
                    renderType: Text.CurveRendering
                    textFormat: Text.StyledText
                    text: parent.label + "  <b>" + parent.value + "</b>"
                    color: Theme.text2
                    font.family: Theme.sans; font.pixelSize: 12
                }
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 4; radius: 2
                    color: Qt.rgba(1, 1, 1, 0.12)
                    Rectangle { width: parent.width * Math.max(0, Math.min(1, parent.parent.fraction)); height: parent.height; radius: 2; color: Theme.text2 }
                }
            }
            Meter {
                label: Lang.s.quickCpu
                value: root.indicators.cpuText
                fraction: root.indicators.cpu === null ? 0 : root.indicators.cpu / 100
            }
            Meter {
                label: Lang.s.quickMemory
                value: root.indicators.memory ? (root.indicators.memory.used / 1073741824).toFixed(1) + " " + Lang.s.unitGb : "—"
                fraction: root.indicators.memory ? root.indicators.memory.used / root.indicators.memory.total : 0
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: 4
        Text {
            renderType: Text.CurveRendering
            Layout.fillWidth: true
            text: !root.power.hasBattery ? Lang.s.powerOnMains
                : root.power.charging ? (root.power.percent >= 100 ? Lang.s.quickCharged : Lang.s.quickCharging + " · " + root.power.percent + "%")
                : Lang.s.quickOnBattery + " · " + root.power.percent + "%"
            color: Theme.text2
            font.family: Theme.sans; font.pixelSize: 12
            elide: Text.ElideRight
        }
        ShellButton {
            visible: !!root.services.settings
            implicitHeight: 24
            text: Lang.s.menuSettings
            hint: Lang.s.quickOpenSettings
            onClicked: root.settingsRequested("")
        }
    }
}
