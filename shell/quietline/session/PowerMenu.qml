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

    Text { text: "Сеанс"; color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.titleFontSize; font.bold: true }
    component ActionButton: ShellButton {
        required property string action
        Layout.fillWidth: true
        text: Models.SESSION_LABELS[action]
        emphasized: root.confirming === action
        enabled: !root.session.busy
        onClicked: root.confirming = action
    }
    ShellButton {
        id: first
        Layout.fillWidth: true
        text: "Заблокировать"
        hint: "Заблокировать сеанс · Super+L"
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
            text: Models.SESSION_QUESTIONS[root.confirming] || ""
            color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
            wrapMode: Text.Wrap
        }
        RowLayout {
            spacing: 6
            ShellButton {
                text: Models.SESSION_LABELS[root.confirming] || ""
                emphasized: true
                onClicked: root.session.end(root.confirming)
            }
            ShellButton { text: "Отмена"; onClicked: root.cancel() }
        }
    }
    Text {
        visible: root.session.busy
        Layout.fillWidth: true
        text: "Закрываем приложения…"
        color: Theme.muted; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
    }
    ColumnLayout {
        visible: root.session.remaining.length > 0 && !root.session.busy
        Layout.fillWidth: true
        spacing: 6
        Text {
            Layout.fillWidth: true
            text: Models.remainingText(root.session.remaining)
            color: Theme.danger; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
            wrapMode: Text.Wrap
        }
        RowLayout {
            spacing: 6
            ShellButton { text: "Повторить"; emphasized: true; onClicked: root.session.end(root.session.action) }
            ShellButton { text: "Отмена"; onClicked: root.cancel() }
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
