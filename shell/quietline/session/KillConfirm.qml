import QtQuick
import QtQuick.Layouts
import Quickshell
import ".."
import "../controls"
import "../logic/Models.js" as Models

// Содержимое диалога `Super+Shift+Q`: принудительно завершить процесс окна `target`
// (`{appId, className, title, pid}`) через `quietline-shell app kill`. Приложение
// называется и показывается значком по desktop-записи из `entries`, без неё — по окну.
ColumnLayout {
    id: root
    property var target: null
    property var entries: []
    readonly property var entry: target ? Models.desktopFor(target.appId || target.className, entries || []) : null
    readonly property string appName: entry ? entry.name : target ? (target.title || target.appId || target.className) : ""
    readonly property string appIcon: entry && entry.icon ? Quickshell.iconPath(entry.icon, true) : ""
    signal done()
    width: parent ? parent.width : 260
    spacing: 0

    function focusCancel() { cancel.forceActiveFocus(); }

    Rectangle {
        Layout.alignment: Qt.AlignHCenter
        Layout.bottomMargin: 12
        width: 54; height: 54; radius: 14
        color: Theme.fill2
        Icon { anchors.centerIn: parent; visible: root.appIcon.length === 0; name: "dangerous"; size: 30; color: Theme.danger }
        Image {
            anchors.centerIn: parent
            visible: root.appIcon.length > 0
            width: 36; height: 36
            sourceSize.width: 72; sourceSize.height: 72
            source: root.appIcon
            smooth: true
        }
        // Значок приложения с отметкой опасного действия в углу.
        Rectangle {
            visible: root.appIcon.length > 0
            anchors.right: parent.right; anchors.bottom: parent.bottom
            anchors.rightMargin: -4; anchors.bottomMargin: -4
            width: 22; height: 22; radius: 11
            color: Theme.dialogSurface
            Icon { anchors.centerIn: parent; name: "dangerous"; size: 18; color: Theme.danger }
        }
    }
    Text {
        renderType: Theme.textRenderType(QsWindow.window)
        Layout.fillWidth: true
        text: Lang.s.killTitle
        color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.titleFontSize; font.weight: Font.Bold
        horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap
    }
    Text {
        renderType: Theme.textRenderType(QsWindow.window)
        Layout.fillWidth: true
        Layout.topMargin: 6
        Layout.bottomMargin: 16
        textFormat: Text.StyledText
        text: root.target ? Lang.f(Lang.s.killQuestion, "<b>" + Models.escapeMarkup(root.appName) + "</b>")
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
