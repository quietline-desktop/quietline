import QtQuick
import QtQuick.Layouts
import Quickshell
import "../.."
import "../../controls"
import "../../inputs"
import "../frame"
import "../../logic/Models.js" as Models

// Страница «Клавиатура»: задержка и скорость повтора клавиш с полем проверки и NumLock при
// входе (`quietline-shell input`), раскладки и их переключение (`Lang` и `quietline-shell region`).
SettingsPage {
    id: root
    required property var desktop
    title: Lang.s.settingsKeyboard
    readonly property var values: store.values || {}
    onOpened: store.load()

    SettingsStore {
        id: store
        command: ["quietline-shell", "input"]
        failure: Lang.s.inputFailed
        delay: 250
    }

    // Ползунок с подписью значения справа: запись после остановки движения.
    component RepeatLine: RowLayout {
        id: line
        property string field: ""
        property string label: ""
        property string symbol: ""
        property string valueText: ""
        property real from: 0
        property real to: 1
        property real stepSize: 1
        width: parent.width
        spacing: 8
        ShellSlider {
            Layout.fillWidth: true
            label: line.label
            symbol: line.symbol
            from: line.from; to: line.to; stepSize: line.stepSize
            value: root.values[line.field] !== undefined ? root.values[line.field] : line.from
            onMoved: store.set({[line.field]: Math.round(value)})
        }
        Text {
            renderType: Theme.textRenderType(QsWindow.window)
            Layout.preferredWidth: 96
            horizontalAlignment: Text.AlignRight
            text: line.valueText
            color: Theme.text2; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
            font.features: ({ "tnum": 1 })
        }
    }

    SettingsGroup {
        title: Lang.s.keyboardRepeat
        SettingsRow {
            label: Lang.s.keyboardDelay
            fill: true
            RepeatLine {
                field: "repeatDelay"; label: Lang.s.keyboardDelay; symbol: "timer"
                from: 150; to: 1000; stepSize: 50
                valueText: Lang.f(Lang.s.keyboardDelayValue, root.values.repeatDelay || 600)
            }
        }
        SettingsRow {
            label: Lang.s.keyboardRate
            fill: true
            RepeatLine {
                field: "repeatRate"; label: Lang.s.keyboardRate; symbol: "keyboard_double_arrow_right"
                from: 10; to: 60; stepSize: 1
                valueText: Lang.f(Lang.s.keyboardRateValue, root.values.repeatRate || 25)
            }
        }
        SettingsRow {
            fill: true
            ShellTextField { width: parent.width; placeholderText: Lang.s.keyboardTest }
        }
        SettingsRow {
            label: Lang.s.keyboardNumlock
            ShellSwitch {
                checked: root.values.numlock === true
                onToggled: store.set({numlock: checked})
                Accessible.name: Lang.s.keyboardNumlock
            }
        }
    }
    PageNote { visible: store.error !== ""; color: Theme.danger; text: store.error }
    PageNote { visible: !store.applied; text: Lang.s.inputPending }

    SettingsGroup {
        title: Lang.s.settingsLayouts
        SettingsRow {
            label: Lang.f(Lang.s.regionOrder, Lang.layouts.map(code => Models.layoutLabel(code, Lang.s)).join(" → "))
            note: Lang.f(Lang.s.keyboardCurrent, Models.layoutLabel(root.desktop.keyboardLayout, Lang.s))
            fill: true
            ShellButton { implicitHeight: 26; selected: true; text: Lang.s.layoutSwap; onClicked: Lang.update({layouts: Lang.layouts.slice().reverse()}) }
            ShellButton { implicitHeight: 26; selected: true; text: Lang.s.keyboardNext; onClicked: root.desktop.switchLayout() }
        }
        SettingsRow {
            label: Lang.s.settingsLayoutToggle
            note: Lang.layoutsApplied ? Lang.f(Lang.s.keyboardToggleNote, Models.toggleLabel(Lang.toggle, Lang.s)) : Lang.s.regionLayoutsPending
            fill: true
            SegmentedControl {
                readonly property var toggles: ["grp:lalt_lshift_toggle", "grp:alt_shift_toggle", "grp:ctrl_shift_toggle", "grp:caps_toggle"]
                showLabels: true; segmentHeight: 24
                model: toggles.map(toggle => ({label: Models.toggleLabel(toggle, Lang.s)}))
                currentIndex: toggles.indexOf(Lang.toggle)
                onActivated: index => Lang.update({toggle: toggles[index]})
            }
        }
    }
    PageNote { visible: Lang.error !== ""; color: Theme.danger; text: Lang.error }
}
