import QtQuick
import QtQuick.Layouts
import Quickshell.Services.UPower
import ".."
import "../controls"

// Страница «Питание» окна «Настройки»: заряд батареи и профиль питания сегментами.
// Без батареи — «питание от сети», без службы профилей — пояснение вместо сегментов.
ColumnLayout {
    id: root
    required property var power
    spacing: 18
    readonly property var profiles: [
        {value: PowerProfile.PowerSaver, label: Lang.s.powerSaver},
        {value: PowerProfile.Balanced, label: Lang.s.powerBalanced},
        {value: PowerProfile.Performance, label: Lang.s.powerPerformance}
    ].filter(item => item.value !== PowerProfile.Performance || root.power.hasPerformance)

    SettingsGroup {
        SettingsRow {
            symbol: !root.power.hasBattery ? "power" : root.power.charging ? "battery_charging_full" : "battery_full"
            symbolBackground: root.power.hasBattery ? Theme.success : Theme.fill2
            symbolColor: root.power.hasBattery ? Theme.accentForeground : Theme.text
            label: root.power.hasBattery ? Lang.f(Lang.s.powerBattery, root.power.percent) : Lang.s.powerOnMains
            note: root.power.timeText
        }
    }

    SettingsGroup {
        title: Lang.s.powerMode
        SettingsRow {
            visible: !root.power.profilesAvailable
            note: Lang.s.powerDaemonMissing
        }
        SettingsRow {
            visible: root.power.profilesAvailable
            label: Lang.s.powerProfile
            SegmentedControl {
                showLabels: true; segmentHeight: 24
                model: root.profiles
                currentIndex: root.profiles.findIndex(item => item.value === root.power.profile)
                onActivated: index => root.power.setProfile(root.profiles[index].value)
            }
        }
    }
}
