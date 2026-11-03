import QtQuick
import QtQuick.Layouts
import Quickshell
import "../.."
import "../../controls"
import "../../inputs"
import "../frame"

// Страница «Панель и док»: процент заряда на панели, автоскрытие дока (`Appearance`) и
// закреплённые приложения дока по порядку — сдвиг влево и вправо и открепление
// (`desktop.movePin`, `desktop.togglePin`).
SettingsPage {
    id: root
    required property var desktop
    title: Lang.s.settingsDock

    PageNote { visible: Appearance.error !== ""; color: Theme.danger; text: Appearance.error }
    SettingsGroup {
        title: Lang.s.appearancePanel
        SettingsRow {
            label: Lang.s.appearanceBatteryPercent
            SegmentedControl {
                readonly property var modes: ["off", "beside", "inside"]
                showLabels: true; segmentHeight: 22
                model: [{label: Lang.s.batteryPercentOff}, {label: Lang.s.batteryPercentBeside}, {label: Lang.s.batteryPercentInside}]
                currentIndex: modes.indexOf(Appearance.batteryPercent)
                onActivated: index => Appearance.update({batteryPercent: modes[index]})
            }
        }
    }
    SettingsGroup {
        title: Lang.s.dockGroup
        SettingsRow {
            label: Lang.s.dockAutohide
            note: Lang.s.dockAutohideNote
            ShellSwitch {
                checked: Appearance.dockAutohide
                onToggled: Appearance.update({dockAutohide: checked})
                Accessible.name: Lang.s.dockAutohide
            }
        }
    }
    SettingsGroup {
        title: Lang.s.dockPinnedGroup
        SettingsRow {
            visible: root.desktop.pinned.length === 0
            note: Lang.s.dockPinnedEmpty
        }
        Repeater {
            model: root.desktop.pinned
            delegate: SettingsRow {
                id: pinRow
                required property var modelData
                required property int index
                readonly property var entry: root.desktop.entryFor(modelData)
                label: entry ? entry.name : modelData
                enabled: !root.desktop.saving
                Image {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 22; height: 22
                    source: pinRow.entry ? Quickshell.iconPath(pinRow.entry.icon, true) : ""
                    sourceSize.width: 44; sourceSize.height: 44
                    smooth: true; mipmap: true
                }
                ShellButton {
                    symbol: "chevron_left"; hint: Lang.s.dockMoveUp
                    enabled: pinRow.index > 0
                    onClicked: root.desktop.movePin(pinRow.index, pinRow.index - 1)
                }
                ShellButton {
                    symbol: "chevron_right"; hint: Lang.s.dockMoveDown
                    enabled: pinRow.index < root.desktop.pinned.length - 1
                    onClicked: root.desktop.movePin(pinRow.index, pinRow.index + 1)
                }
                ShellButton {
                    implicitHeight: 26; selected: true
                    text: Lang.s.dockUnpin
                    onClicked: root.desktop.togglePin(pinRow.modelData)
                }
            }
        }
    }
    PageNote { visible: !Appearance.applied; text: Lang.s.appearancePending }
}
