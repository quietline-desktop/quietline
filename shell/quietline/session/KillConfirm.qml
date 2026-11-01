import QtQuick
import QtQuick.Layouts
import Quickshell
import ".."
import "../controls"

// Содержимое диалога `Super+Shift+Q`: принудительно завершить процесс окна `target`
// (`{appId, className, title, pid}`) через `quietline-shell app kill`.
ColumnLayout {
    id: root
    property var target: null
    signal done()
    width: parent ? parent.width : 260
    spacing: 0

    function focusCancel() { cancel.forceActiveFocus(); }

    Rectangle {
        Layout.alignment: Qt.AlignHCenter
        Layout.bottomMargin: 12
        width: 54; height: 54; radius: 14
        color: Theme.fill2
        Icon { anchors.centerIn: parent; name: "dangerous"; size: 30; color: Theme.danger }
    }
    Text {
        renderType: Text.CurveRendering
        Layout.fillWidth: true
        text: Lang.s.killTitle
        color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.titleFontSize; font.weight: Font.Bold
        horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap
    }
    Text {
        renderType: Text.CurveRendering
        Layout.fillWidth: true
        Layout.topMargin: 6
        Layout.bottomMargin: 16
        text: root.target ? Lang.f(Lang.s.killQuestion, root.target.title || root.target.appId || root.target.className)
                          : Lang.s.killNoWindow
        color: Theme.text2; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
        horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap
    }
    RowLayout {
        Layout.fillWidth: true
        spacing: 8
        ShellButton {
            id: cancel
            Layout.fillWidth: true; Layout.preferredWidth: 1
            implicitHeight: 30; radius: Theme.radiusControl
            text: Lang.s.cancel
            selected: true
            KeyNavigation.right: kill
            onClicked: root.done()
        }
        ShellButton {
            id: kill
            Layout.fillWidth: true; Layout.preferredWidth: 1
            implicitHeight: 30; radius: Theme.radiusControl
            text: Lang.s.killConfirm
            foreground: Theme.danger
            selected: true
            enabled: !!root.target && root.target.pid > 1
            KeyNavigation.left: cancel
            onClicked: {
                Quickshell.execDetached(["quietline-shell", "app", "kill", "--pid", String(root.target.pid)]);
                root.done();
            }
        }
    }
}
