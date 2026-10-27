import QtQuick
import QtQuick.Layouts
import Quickshell.Services.UPower
import ".."
import "../controls"

// Заряд батареи и профиль питания; без батареи или службы профилей — строка состояния.
ColumnLayout {
    id: root
    required property var power
    spacing: 8
    Text {
        text: root.power.hasBattery
            ? "Батарея " + root.power.percent + "%" + (root.power.timeText ? " · " + root.power.timeText : "")
            : "Батареи нет: питание от сети"
        color: root.power.hasBattery ? Theme.text : Theme.muted
        font.family: Theme.sans; font.pixelSize: Theme.fontSize
    }
    Text {
        text: root.power.profilesAvailable ? "Режим питания" : "Служба профилей питания (power-profiles-daemon) не запущена"
        color: Theme.muted; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
    }
    Flow {
        visible: root.power.profilesAvailable
        Layout.fillWidth: true
        spacing: 6
        Repeater {
            model: [
                {value: PowerProfile.PowerSaver, label: "Энергосбережение"},
                {value: PowerProfile.Balanced, label: "Баланс"},
                {value: PowerProfile.Performance, label: "Производительность"}
            ].filter(item => item.value !== PowerProfile.Performance || root.power.hasPerformance)
            delegate: ShellButton {
                required property var modelData
                text: modelData.label
                emphasized: root.power.profile === modelData.value
                onClicked: root.power.setProfile(modelData.value)
            }
        }
    }
}
