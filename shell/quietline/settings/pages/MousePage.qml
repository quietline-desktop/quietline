import QtQuick
import QtQuick.Layouts
import "../.."
import "../../controls"
import "../../inputs"
import "../frame"

// Страница «Мышь и тачпад»: скорость указателя, ускорение, прокрутка и основная кнопка мыши;
// касание, прокрутка и отключение при наборе — для тачпада, если он есть. Значения —
// `quietline-shell input`, применяются сразу.
SettingsPage {
    id: root
    title: Lang.s.settingsMouse
    readonly property var values: store.values || {}
    onOpened: store.load()

    SettingsStore {
        id: store
        command: ["quietline-shell", "input"]
        failure: Lang.s.inputFailed
        delay: 250
    }

    // Ползунок со значением из настроек: запись после остановки движения.
    component ValueSlider: ShellSlider {
        property string field: ""
        width: parent.width
        value: root.values[field] !== undefined ? root.values[field] : from
        onMoved: store.set({[field]: Math.round(value * 100) / 100})
    }

    SettingsGroup {
        title: Lang.s.mouseGroup
        SettingsRow {
            label: Lang.s.mouseSpeed
            note: Lang.s.mouseSpeedNote
            fill: true
            ValueSlider { field: "pointerSpeed"; label: Lang.s.mouseSpeed; symbol: "speed"; from: -1; to: 1; stepSize: 0.1 }
        }
        SettingsRow {
            label: Lang.s.mouseAcceleration
            note: Lang.s.mouseAccelerationNote
            ShellSwitch {
                checked: root.values.acceleration !== false
                onToggled: store.set({acceleration: checked})
                Accessible.name: Lang.s.mouseAcceleration
            }
        }
        SettingsRow {
            label: Lang.s.mouseNaturalScroll
            note: Lang.s.mouseNaturalNote
            ShellSwitch {
                checked: root.values.naturalScroll === true
                onToggled: store.set({naturalScroll: checked})
                Accessible.name: Lang.s.mouseNaturalScroll
            }
        }
        SettingsRow {
            label: Lang.s.mouseScrollSpeed
            fill: true
            ValueSlider { field: "scrollSpeed"; label: Lang.s.mouseScrollSpeed; symbol: "swap_vert"; from: 0.25; to: 3; stepSize: 0.05 }
        }
        SettingsRow {
            label: Lang.s.mousePrimary
            SegmentedControl {
                showLabels: true; segmentHeight: 22
                model: [{label: Lang.s.mouseLeft}, {label: Lang.s.mouseRight}]
                currentIndex: root.values.leftHanded ? 1 : 0
                onActivated: index => store.set({leftHanded: index === 1})
            }
        }
    }

    SettingsGroup {
        visible: root.values.touchpad === true
        title: Lang.s.touchpadGroup
        SettingsRow {
            label: Lang.s.touchpadTap
            ShellSwitch {
                checked: root.values.tapToClick !== false
                onToggled: store.set({tapToClick: checked})
                Accessible.name: Lang.s.touchpadTap
            }
        }
        SettingsRow {
            label: Lang.s.mouseNaturalScroll
            note: Lang.s.mouseNaturalNote
            ShellSwitch {
                checked: root.values.touchpadNaturalScroll === true
                onToggled: store.set({touchpadNaturalScroll: checked})
                Accessible.name: Lang.s.mouseNaturalScroll
            }
        }
        SettingsRow {
            label: Lang.s.touchpadTyping
            ShellSwitch {
                checked: root.values.disableWhileTyping !== false
                onToggled: store.set({disableWhileTyping: checked})
                Accessible.name: Lang.s.touchpadTyping
            }
        }
        SettingsRow {
            label: Lang.s.mouseScrollSpeed
            fill: true
            ValueSlider { field: "touchpadScrollSpeed"; label: Lang.s.mouseScrollSpeed; symbol: "swap_vert"; from: 0.25; to: 3; stepSize: 0.05 }
        }
    }
    PageNote { visible: store.error !== ""; color: Theme.danger; text: store.error }
    PageNote { visible: !store.applied; text: Lang.s.inputPending }
}
