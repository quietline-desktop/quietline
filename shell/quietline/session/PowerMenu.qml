import QtQuick
import QtQuick.Layouts
import ".."
import "../controls"
import "../logic/Models.js" as Models

// Меню кнопки питания: «Заблокировать» сразу, остальное — после подтверждения второй строкой.
// Пока окна закрываются, меню показывает ход; оставшиеся приложения — списком с повтором.
ColumnLayout {
    id: root
    required property var session
    // Действие, ждущее подтверждения; пусто — подтверждения нет.
    property string confirming: ""
    signal done()
    spacing: 6

    function reset() { confirming = ""; first.forceActiveFocus(); }
    function cancel() { confirming = ""; session.reset(); first.forceActiveFocus(); }

    Text { text: Lang.s.sessionTitle; color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.titleFontSize; font.bold: true }
    component ActionButton: ShellButton {
        required property string action
        Layout.fillWidth: true
        text: Models.sessionLabel(action, Lang.s)
        emphasized: root.confirming === action
        enabled: !root.session.busy
        onClicked: root.confirming = action
    }
    ShellButton {
        id: first
        Layout.fillWidth: true
        text: Lang.s.actionLock
        hint: Lang.s.sessionLockHint
        enabled: !root.session.busy
        KeyNavigation.down: logout
        onClicked: { root.done(); root.session.lock(); }
    }
    ActionButton { id: logout; action: "logout"; KeyNavigation.up: first; KeyNavigation.down: reboot }
    ActionButton { id: reboot; action: "reboot"; KeyNavigation.up: logout; KeyNavigation.down: poweroff }
    ActionButton { id: poweroff; action: "poweroff"; KeyNavigation.up: reboot }

    ColumnLayout {
        visible: root.confirming.length > 0 && !root.session.busy && root.session.remaining.length === 0
        Layout.fillWidth: true
        spacing: 6
        Text {
            Layout.fillWidth: true
            text: Models.sessionQuestion(root.confirming, Lang.s)
            color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
            wrapMode: Text.Wrap
        }
        RowLayout {
            spacing: 6
            ShellButton {
                text: Models.sessionLabel(root.confirming, Lang.s)
                emphasized: true
                onClicked: root.session.end(root.confirming)
            }
            ShellButton { text: Lang.s.cancel; onClicked: root.cancel() }
        }
    }
    Text {
        visible: root.session.busy
        Layout.fillWidth: true
        text: Lang.s.sessionClosingApps
        color: Theme.muted; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
    }
    ColumnLayout {
        visible: root.session.remaining.length > 0 && !root.session.busy
        Layout.fillWidth: true
        spacing: 6
        Text {
            Layout.fillWidth: true
            text: Models.remainingText(root.session.remaining, Lang.s)
            color: Theme.danger; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
            wrapMode: Text.Wrap
        }
        RowLayout {
            spacing: 6
            ShellButton { text: Lang.s.retry; emphasized: true; onClicked: root.session.end(root.session.action) }
            ShellButton { text: Lang.s.cancel; onClicked: root.cancel() }
        }
    }
    Text {
        visible: root.session.errorMessage.length > 0
        Layout.fillWidth: true
        text: root.session.errorMessage
        color: Theme.danger; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
        wrapMode: Text.Wrap
    }
}
