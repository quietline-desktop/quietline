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

    Text { text: "Принудительное завершение"; color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.titleFontSize; font.bold: true }
    Text {
        Layout.fillWidth: true
        text: root.target ? "Завершить «" + (root.target.title || root.target.appId || root.target.className) + "» без сохранения? Несохранённые данные будут потеряны."
                          : "Нет активного окна."
        color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
        wrapMode: Text.Wrap
    }
    RowLayout {
        spacing: 6
        ShellButton {
            text: "Завершить принудительно"
            foreground: Theme.danger
            enabled: !!root.target && root.target.pid > 1
            KeyNavigation.right: cancel
            onClicked: {
                Quickshell.execDetached(["quietline-shell", "app", "kill", "--pid", String(root.target.pid)]);
                root.done();
            }
        }
        ShellButton { id: cancel; text: "Отмена"; onClicked: root.done() }
    }
}
