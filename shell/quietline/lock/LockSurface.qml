import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import ".."

// Поверхность экрана блокировки на одном экране: часы, дата, поле пароля и сообщение PAM.
WlSessionLockSurface {
    id: root
    required property var context
    color: Theme.background

    SystemClock { id: clock; precision: SystemClock.Minutes }

    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(360, parent.width - 48)
        spacing: 14
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: Lang.time(clock.date)
            color: Theme.text; font.family: Theme.mono; font.pixelSize: 64
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: Lang.longDate(clock.date)
            color: Theme.muted; font.family: Theme.sans; font.pixelSize: Theme.fontSize
        }
        TextField {
            id: password
            Layout.fillWidth: true
            Layout.topMargin: 18
            echoMode: TextInput.Password
            placeholderText: root.context.checking ? Lang.s.lockChecking : Lang.s.password
            enabled: !root.context.checking
            focus: true
            font.family: Theme.sans; font.pixelSize: Theme.fontSize
            color: Theme.text; placeholderTextColor: Theme.muted
            implicitHeight: 38
            leftPadding: 12; rightPadding: 12
            Accessible.name: Lang.s.lockPasswordLabel
            background: Rectangle {
                color: Theme.surface
                radius: Theme.controlRadius
                border.width: 1
                border.color: password.activeFocus ? Theme.accent : Theme.border
            }
            onAccepted: { var text = password.text; password.clear(); root.context.submit(text); }
            Component.onCompleted: forceActiveFocus()
        }
        Text {
            Layout.fillWidth: true
            visible: text.length > 0
            text: root.context.message
            color: root.context.messageIsError ? Theme.danger : Theme.muted
            font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
        }
    }
}
