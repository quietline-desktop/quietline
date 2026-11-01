import QtQuick
import QtQuick.Layouts
import ".."
import "../controls"
import "../logic/Models.js" as Models

// Содержимое диалога выхода, перезагрузки и выключения: вопрос, пояснение, «Отменить» и
// действие. Пока приложения закрываются — ход; оставшиеся приложения — списком с повтором.
ColumnLayout {
    id: root
    required property var session
    // Действие сеанса: `logout`, `reboot` или `poweroff`.
    property string action: ""
    signal done()
    width: parent ? parent.width : 260
    spacing: 0

    function reset() { session.reset(); confirm.forceActiveFocus(); }
    function cancel() { session.reset(); done(); }
    readonly property string symbol: action === "reboot" ? "restart_alt" : action === "logout" ? "logout" : "power_settings_new"

    Rectangle {
        Layout.alignment: Qt.AlignHCenter
        Layout.bottomMargin: 12
        width: 54; height: 54; radius: 14
        color: Theme.fill2
        Icon { anchors.centerIn: parent; name: root.symbol; size: 30; color: Theme.text }
    }
    Text {
        renderType: Text.CurveRendering
        Layout.fillWidth: true
        text: Models.sessionQuestion(root.action, Lang.s)
        color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.titleFontSize; font.weight: Font.Bold
        horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap
    }
    Text {
        renderType: Text.CurveRendering
        Layout.fillWidth: true
        Layout.topMargin: 6
        Layout.bottomMargin: 16
        text: root.session.busy ? Lang.s.sessionClosingApps
            : root.session.remaining.length > 0 ? Models.remainingText(root.session.remaining, Lang.s)
            : root.session.errorMessage.length > 0 ? root.session.errorMessage
            : Lang.s.sessionDialogBody
        color: root.session.remaining.length > 0 || root.session.errorMessage.length > 0 ? Theme.danger : Theme.text2
        font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
        horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap
    }
    RowLayout {
        Layout.fillWidth: true
        spacing: 8
        ShellButton {
            id: cancelButton
            Layout.fillWidth: true; Layout.preferredWidth: 1
            implicitHeight: 30; radius: Theme.radiusControl
            text: Lang.s.cancel
            selected: true
            enabled: !root.session.busy
            KeyNavigation.right: confirm
            onClicked: root.cancel()
        }
        ShellButton {
            id: confirm
            Layout.fillWidth: true; Layout.preferredWidth: 1
            implicitHeight: 30; radius: Theme.radiusControl
            text: root.session.remaining.length > 0 ? Lang.s.retry : Models.sessionLabel(root.action, Lang.s)
            emphasized: true
            busy: root.session.busy
            enabled: !root.session.busy
            KeyNavigation.left: cancelButton
            onClicked: root.session.end(root.action)
        }
    }
}
