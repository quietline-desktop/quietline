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
        renderType: Text.CurveRendering
        text: root.power.hasBattery
            ? Lang.f(Lang.s.powerBattery, root.power.percent) + (root.power.timeText ? " · " + root.power.timeText : "")
            : Lang.s.powerOnMains
        color: root.power.hasBattery ? Theme.text : Theme.muted
        font.family: Theme.sans; font.pixelSize: Theme.fontSize
    }
    Text {
        renderType: Text.CurveRendering
        text: root.power.profilesAvailable ? Lang.s.powerMode : Lang.s.powerDaemonMissing
        color: Theme.muted; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
    }
    Flow {
        visible: root.power.profilesAvailable
        Layout.fillWidth: true
        spacing: 6
        Repeater {
            model: [
                {value: PowerProfile.PowerSaver, label: Lang.s.powerSaver},
                {value: PowerProfile.Balanced, label: Lang.s.powerBalanced},
                {value: PowerProfile.Performance, label: Lang.s.powerPerformance}
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
