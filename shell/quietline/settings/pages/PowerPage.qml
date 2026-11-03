import QtQuick
import QtQuick.Layouts
import "../.."
import "../../controls"
import "../../inputs"
import "../../panels"
import "../frame"
import "../../logic/Models.js" as Models

// Страница «Питание»: заряд и профиль питания (`PowerControls`) и сроки блокировки, отключения
// экрана и сна от батареи (`quietline-shell idle settings`).
SettingsPage {
    id: root
    required property var power
    title: Lang.s.settingsPower
    readonly property var values: store.values || {}
    onOpened: store.load()

    SettingsStore {
        id: store
        command: ["quietline-shell", "idle", "settings"]
        failure: Lang.s.idleFailed
    }

    PowerControls { Layout.fillWidth: true; power: root.power }

    SettingsGroup {
        title: Lang.s.idleGroup
        Repeater {
            model: [
                {field: "lock", label: Lang.s.idleLock, note: "", choices: [1, 2, 5, 10, 15, 30, 0]},
                {field: "screenOff", label: Lang.s.idleScreen, note: "", choices: [1, 2, 5, 10, 15, 30, 0]},
                {field: "suspend", label: Lang.s.idleSuspend, note: Lang.s.idleSuspendNote, choices: [10, 15, 30, 60, 0]}
            ]
            delegate: SettingsRow {
                id: idleRow
                required property var modelData
                label: modelData.label
                note: modelData.note
                ShellSelect {
                    label: idleRow.modelData.label
                    minimumWidth: 130
                    model: idleRow.modelData.choices.map(minutes => ({label: Models.idleLabel(minutes, Lang.s)}))
                    currentIndex: idleRow.modelData.choices.indexOf(root.values[idleRow.modelData.field])
                    enabled: store.values !== null
                    onActivated: index => store.set({[idleRow.modelData.field]: idleRow.modelData.choices[index]})
                }
            }
        }
    }
    PageNote { visible: store.error !== ""; color: Theme.danger; text: store.error }
}
