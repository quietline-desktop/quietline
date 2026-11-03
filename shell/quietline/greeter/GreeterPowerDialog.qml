import QtQuick
import Quickshell
import QtQuick.Layouts
import ".."
import "../controls"

// Подтверждение питания экрана входа: отмена получает фокус, Escape закрывает вопрос.
FocusScope {
    id: root
    required property var context
    focus: visible
    onVisibleChanged: if (visible) Qt.callLater(function() { cancelButton.forceActiveFocus(); })
    Keys.onEscapePressed: context.powerAction = ""
    Rectangle { anchors.fill: parent; color: Qt.rgba(0, 0, 0, 0.55) }
    MouseArea { anchors.fill: parent }
    Rectangle {
        anchors.centerIn: parent
        width: 300; height: content.implicitHeight + 40
        radius: Theme.radiusPopup; color: Theme.solidSurface
        ColumnLayout {
            id: content
            anchors { fill: parent; margins: 20 }
            spacing: 18
            Text {
                renderType: Theme.textRenderType(QsWindow.window)
                Layout.fillWidth: true
                text: root.context.powerAction === "reboot" ? Lang.s.sessionRebootQuestion : Lang.s.sessionPoweroffQuestion
                color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.titleFontSize
                wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter
            }
            RowLayout {
                Layout.fillWidth: true; spacing: 8
                ShellButton {
                    id: cancelButton
                    Layout.fillWidth: true
                    text: Lang.s.cancel; selected: true
                    KeyNavigation.tab: confirmButton
                    KeyNavigation.backtab: confirmButton
                    KeyNavigation.right: confirmButton
                    onClicked: root.context.powerAction = ""
                }
                ShellButton {
                    id: confirmButton
                    Layout.fillWidth: true
                    text: root.context.powerAction === "reboot" ? Lang.s.sessionReboot : Lang.s.sessionPoweroff
                    emphasized: true
                    KeyNavigation.tab: cancelButton
                    KeyNavigation.backtab: cancelButton
                    KeyNavigation.left: cancelButton
                    onClicked: root.context.confirmPower()
                }
            }
        }
    }
}
