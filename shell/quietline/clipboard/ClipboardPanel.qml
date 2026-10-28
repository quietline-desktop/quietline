import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
import "../controls"
import "../inputs"
import "../logic/Models.js" as Models

// Панель `Super+V`: поиск по истории буфера; выбранная запись возвращается в буфер.
// Внизу — пауза записи и очистка истории с подтверждением.
ColumnLayout {
    id: root
    required property var clipboard
    property bool confirmWipe: false
    readonly property var matches: Models.clipboardMatches(clipboard.entries, search.text)
    signal done()
    spacing: 10

    function reset() { search.clear(); confirmWipe = false; clipboard.refresh(); search.forceActiveFocus(); }
    Connections { target: root.clipboard; function onRestored() { root.done(); } }

    Text { text: "История буфера"; color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.titleFontSize; font.bold: true }
    ShellTextField {
        id: search
        Layout.fillWidth: true
        placeholderText: "Найти в истории"
        label: "Поиск по истории буфера"
        onAccepted: { if (root.matches.length) root.clipboard.restore(root.matches[0].id); }
    }
    Text {
        visible: root.clipboard.errorMessage.length > 0
        Layout.fillWidth: true
        text: root.clipboard.errorMessage
        color: Theme.danger; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
        wrapMode: Text.Wrap
    }
    ScrollView {
        id: scroll
        Layout.fillWidth: true
        Layout.preferredHeight: Math.min(320, list.implicitHeight)
        ScrollBar.vertical: ShellScrollBar {}
        Column {
            id: list
            width: scroll.availableWidth
            spacing: 3
            Repeater {
                model: root.matches
                delegate: RowLayout {
                    id: row
                    required property var modelData
                    width: list.width
                    spacing: 4
                    ShellButton {
                        Layout.fillWidth: true
                        implicitHeight: row.modelData.kind === "image" ? 56 : 28
                        hint: "Вернуть в буфер"
                        enabled: !root.clipboard.busy
                        onClicked: root.clipboard.restore(row.modelData.id)
                        contentItem: RowLayout {
                            spacing: 8
                            Image {
                                visible: row.modelData.kind === "image"
                                source: root.clipboard.images[row.modelData.id] || ""
                                Layout.preferredWidth: 72; Layout.preferredHeight: 44
                                fillMode: Image.PreserveAspectFit
                                asynchronous: true
                                cache: false
                            }
                            Text {
                                Layout.fillWidth: true
                                text: row.modelData.kind === "image" ? Models.clipboardImageLabel(row.modelData.preview) : row.modelData.preview
                                color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.fontSize
                                elide: Text.ElideRight; textFormat: Text.PlainText
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }
                    ShellButton { text: "×"; hint: "Удалить из истории"; enabled: !root.clipboard.busy; onClicked: root.clipboard.remove(row.modelData.id) }
                }
            }
            Text {
                visible: root.matches.length === 0
                text: root.clipboard.entries.length ? "Ничего не найдено" : "История пуста"
                color: Theme.muted; font.family: Theme.sans; font.pixelSize: Theme.fontSize
                topPadding: 8
            }
        }
    }
    Text {
        visible: root.clipboard.paused
        Layout.fillWidth: true
        text: "Запись приостановлена: новые копирования не попадают в историю."
        color: Theme.muted; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
        wrapMode: Text.Wrap
    }
    RowLayout {
        spacing: 6
        ShellButton {
            text: root.clipboard.paused ? "Возобновить запись" : "Приостановить запись"
            enabled: !root.clipboard.busy
            onClicked: root.clipboard.setPaused(!root.clipboard.paused)
        }
        ShellButton {
            text: root.confirmWipe ? "Точно очистить?" : "Очистить"
            foreground: root.confirmWipe ? Theme.danger : Theme.text
            enabled: !root.clipboard.busy && root.clipboard.entries.length > 0
            onClicked: {
                if (root.confirmWipe) { root.clipboard.wipe(); root.confirmWipe = false; }
                else root.confirmWipe = true;
            }
        }
    }
}
