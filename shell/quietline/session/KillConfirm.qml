import QtQuick
import QtQuick.Layouts
import Quickshell
import ".."
import "../controls"

// Подтверждение `Super+Shift+Q`: принудительно завершить процесс окна `target`
// (`{appId, className, title, pid}`) через `quietline-shell app kill`.
ColumnLayout {
    id: root
    property var target: null
    signal done()
    spacing: 8

    function focusCancel() { cancel.forceActiveFocus(); }

    Text { text: Lang.s.killTitle; color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.titleFontSize; font.bold: true }
    Text {
        Layout.fillWidth: true
        text: root.target ? Lang.f(Lang.s.killQuestion, root.target.title || root.target.appId || root.target.className)
                          : Lang.s.killNoWindow
        color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
        wrapMode: Text.Wrap
    }
    RowLayout {
        spacing: 6
        ShellButton {
            text: Lang.s.killConfirm
            foreground: Theme.danger
            enabled: !!root.target && root.target.pid > 1
            KeyNavigation.right: cancel
            onClicked: {
                Quickshell.execDetached(["quietline-shell", "app", "kill", "--pid", String(root.target.pid)]);
                root.done();
            }
        }
        ShellButton { id: cancel; text: Lang.s.cancel; onClicked: root.done() }
    }
}
