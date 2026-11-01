import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import ".."
import "../controls"
import "../logic/Models.js" as Models

// Панель поиска `Super+Space`: приложения, системные действия, разделы настроек, вычисления
// и файлы домашнего каталога. ↑/↓ выбирают результат, Enter открывает, Esc закрывает окно.
ColumnLayout {
    id: root
    required property var desktop
    required property var services
    required property var finder
    required property string monitorName
    property int selected: 0
    readonly property var results: Models.searchResults(field.text, desktop.entries, finder.files, finder.home, 40, Lang.s)
    signal done()
    // Выход, перезагрузка и выключение подтверждаются в меню питания.
    signal sessionRequested(string action)
    signal clipboardRequested()
    spacing: 10

    function reset() { field.clear(); selected = 0; field.forceActiveFocus(); }
    function activate(item) {
        if (!item) return;
        switch (item.kind) {
        case "app": root.desktop.launch(item.id, root.monitorName); root.done(); break;
        case "settings": root.done(); root.services.settings.open(item.id); break;
        case "calc": Quickshell.execDetached(["wl-copy", item.value]); root.done(); break;
        case "file": Quickshell.execDetached(["xdg-open", item.path]); root.done(); break;
        case "action":
            if (item.id === "lock") { root.done(); root.services.session.lock(); }
            else if (item.id === "screenshot") { root.done(); Quickshell.execDetached(["quietline-shell", "screenshot", "region"]); }
            else if (item.id === "clipboard") root.clipboardRequested();
            else root.sessionRequested(item.id);
            break;
        }
    }

    Text { text: Lang.s.searchTitle; color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.titleFontSize; font.bold: true }
    TextField {
        id: field
        Layout.fillWidth: true
        placeholderText: Lang.s.searchPlaceholder
        font.family: Theme.sans; font.pixelSize: Theme.fontSize
        color: Theme.text; placeholderTextColor: Theme.muted; selectByMouse: true; rightPadding: 32
        Accessible.name: Lang.s.searchTitle
        background: Rectangle { color: Theme.background; radius: Theme.controlRadius; border.color: field.activeFocus ? Theme.accent : Theme.border; border.width: 1 }
        ShellButton { anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; visible: field.text.length > 0; text: "×"; hint: Lang.s.searchClear; onClicked: root.reset() }
        onTextChanged: { root.selected = 0; root.finder.query = text; }
        onAccepted: root.activate(root.results[Math.min(root.selected, root.results.length - 1)])
        Keys.onDownPressed: root.selected = Math.min(root.selected + 1, root.results.length - 1)
        Keys.onUpPressed: root.selected = Math.max(root.selected - 1, 0)
    }
    ScrollView {
        id: scroll
        Layout.fillWidth: true; Layout.fillHeight: true
        rightPadding: ScrollBar.vertical.visible ? ScrollBar.vertical.width + 4 : 0
        ScrollBar.vertical: ShellScrollBar {}
        Column {
            width: scroll.availableWidth; spacing: 3
            Repeater {
                id: list
                model: root.results
                delegate: ShellButton {
                    id: row
                    required property var modelData
                    required property int index
                    width: scroll.availableWidth
                    implicitHeight: 40
                    hint: modelData.kind === "file" ? modelData.path : modelData.title
                    emphasized: index === Math.min(root.selected, root.results.length - 1)
                    onClicked: root.activate(modelData)
                    contentItem: Column {
                        leftPadding: 6
                        Text {
                            width: row.width - 12
                            text: row.modelData.title
                            color: row.emphasized ? Theme.accentText : Theme.text
                            font.family: Theme.sans; font.pixelSize: Theme.fontSize
                            elide: Text.ElideRight; textFormat: Text.PlainText
                        }
                        Text {
                            width: row.width - 12
                            text: row.modelData.subtitle
                            color: row.emphasized ? Theme.accentText : Theme.muted
                            font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
                            elide: Text.ElideMiddle; textFormat: Text.PlainText
                        }
                    }
                }
            }
            Text { visible: list.count === 0; text: Lang.s.nothingFound; color: Theme.muted; font.family: Theme.sans; topPadding: 12 }
            Text {
                visible: root.finder.errorMessage.length > 0
                width: scroll.availableWidth
                text: root.finder.errorMessage
                color: Theme.danger; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
                wrapMode: Text.Wrap; topPadding: 8
            }
        }
    }
}
