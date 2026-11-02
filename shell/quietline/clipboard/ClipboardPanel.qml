import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
import "../controls"
import "../logic/Models.js" as Models

// История буфера `Super+V` по центру экрана: сверху поиск, слева записи (текст, ссылка,
// картинка), справа предпросмотр выбранной. ↑/↓ выбирают, Enter возвращает запись в буфер,
// Delete удаляет её; внизу — пауза записи и очистка истории с подтверждением.
ColumnLayout {
    id: root
    required property var clipboard
    property bool confirmWipe: false
    property int selected: 0
    readonly property var matches: Models.clipboardMatches(clipboard.entries, search.text, Lang.s)
    readonly property var current: matches.length ? matches[Math.min(selected, matches.length - 1)] : null
    readonly property real contentHeight: 54 + 1 + 330 + 1 + 40
    signal done()
    spacing: 0

    function reset() { search.clear(); confirmWipe = false; selected = 0; clipboard.refresh(); search.forceActiveFocus(); }
    function select(index) {
        selected = Math.max(0, Math.min(index, matches.length - 1));
        list.positionViewAtIndex(selected, ListView.Contain);
    }
    Connections { target: root.clipboard; function onRestored() { root.done(); } }

    RowLayout {
        Layout.fillWidth: true
        Layout.preferredHeight: 54
        Layout.leftMargin: 18; Layout.rightMargin: 18
        spacing: 12
        Icon { name: "content_paste"; size: 22; color: Theme.text2 }
        TextField {
            id: search
            Layout.fillWidth: true
            placeholderText: Lang.s.clipboardSearchPlaceholder
            font.family: Theme.sans; font.pixelSize: 19
            renderType: Text.CurveRendering
            color: Theme.text; placeholderTextColor: Theme.text3
            selectionColor: Theme.accent; selectedTextColor: Theme.accentForeground
            selectByMouse: true
            padding: 0
            background: Item {}
            Accessible.name: Lang.s.clipboardSearchLabel
            onTextChanged: root.selected = 0
            onAccepted: { if (root.current) root.clipboard.restore(root.current.id); }
            Keys.onDownPressed: root.select(root.selected + 1)
            Keys.onUpPressed: root.select(root.selected - 1)
            Keys.onDeletePressed: event => {
                if (search.text.length === 0 && root.current) { root.clipboard.remove(root.current.id); event.accepted = true; }
                else event.accepted = false;
            }
        }
        Text {
            renderType: Text.CurveRendering
            text: Lang.s.clipboardHint
            color: Theme.text3
            font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
        }
    }
    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.hairline }
    RowLayout {
        Layout.fillWidth: true
        Layout.preferredHeight: 330
        spacing: 0
        ListView {
            id: list
            Layout.preferredWidth: 280
            Layout.fillHeight: true
            Layout.margins: 6
            clip: true
            spacing: 2
            boundsBehavior: Flickable.StopAtBounds
            model: root.matches
            ScrollBar.vertical: ShellScrollBar {}
            delegate: Rectangle {
                id: row
                required property var modelData
                required property int index
                readonly property bool chosen: index === Math.min(root.selected, root.matches.length - 1)
                width: list.width - 4
                height: 44
                radius: Theme.radiusRow
                color: chosen ? Theme.accent : rowArea.containsMouse ? Theme.fill : "transparent"
                MouseArea {
                    id: rowArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    enabled: !root.clipboard.busy
                    onEntered: root.selected = row.index
                    onClicked: root.clipboard.restore(row.modelData.id)
                }
                RowLayout {
                    anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 6
                    spacing: 10
                    Icon { name: Models.clipboardSymbol(row.modelData); size: 17; color: row.chosen ? Theme.accentForeground : Theme.text2 }
                    Column {
                        Layout.fillWidth: true
                        Text {
                            renderType: Text.CurveRendering
                            width: parent.width
                            text: row.modelData.kind === "image" ? Models.clipboardImageLabel(row.modelData.preview, Lang.s) : row.modelData.preview
                            color: row.chosen ? Theme.accentForeground : Theme.text
                            font.family: Theme.sans; font.pixelSize: Theme.fontSize
                            elide: Text.ElideRight; textFormat: Text.PlainText; maximumLineCount: 1
                        }
                        Text {
                            renderType: Text.CurveRendering
                            text: Models.clipboardKindLabel(row.modelData, Lang.s)
                            color: row.chosen ? Theme.accentForeground2 : Theme.text3
                            font.family: Theme.sans; font.pixelSize: Theme.captionFontSize
                        }
                    }
                    ShellButton {
                        visible: rowArea.containsMouse || row.chosen
                        implicitHeight: 22; implicitWidth: 22
                        symbol: "close"; symbolSize: 14
                        foreground: row.chosen ? Theme.accentForeground : Theme.text2
                        hint: Lang.s.clipboardRemove
                        enabled: !root.clipboard.busy
                        onClicked: root.clipboard.remove(row.modelData.id)
                    }
                }
            }
            Text {
                renderType: Text.CurveRendering
                visible: root.matches.length === 0
                anchors.centerIn: parent
                text: root.clipboard.entries.length ? Lang.s.nothingFound : Lang.s.clipboardEmpty
                color: Theme.text2; font.family: Theme.sans; font.pixelSize: Theme.fontSize
            }
        }
        Rectangle { Layout.fillHeight: true; implicitWidth: 1; color: Theme.hairline }
        // Предпросмотр выбранной записи.
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Image {
                visible: !!root.current && root.current.kind === "image"
                anchors.fill: parent; anchors.margins: 14; anchors.bottomMargin: 34
                source: visible ? (root.clipboard.images[root.current.id] || "") : ""
                fillMode: Image.PreserveAspectFit
                asynchronous: true
                cache: false
            }
            Text {
                renderType: Text.CurveRendering
                visible: !!root.current && root.current.kind !== "image"
                anchors.fill: parent; anchors.margins: 14; anchors.bottomMargin: 34
                text: root.current ? root.current.preview : ""
                color: Theme.text
                font.family: Theme.mono; font.pixelSize: Theme.smallFontSize
                wrapMode: Text.WrapAnywhere; elide: Text.ElideRight
                textFormat: Text.PlainText
            }
            Text {
                renderType: Text.CurveRendering
                visible: !!root.current
                anchors.left: parent.left; anchors.bottom: parent.bottom; anchors.margins: 14
                text: !root.current ? "" : root.current.kind === "image" ? Models.clipboardKindLabel(root.current, Lang.s)
                    : Models.clipboardKindLabel(root.current, Lang.s) + " · " + Lang.f(Lang.s.clipboardChars, root.current.preview.length)
                color: Theme.text3
                font.family: Theme.sans; font.pixelSize: Theme.captionFontSize
            }
        }
    }
    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.hairline }
    RowLayout {
        Layout.fillWidth: true
        Layout.preferredHeight: 40
        Layout.leftMargin: 10; Layout.rightMargin: 10
        spacing: 6
        Text {
            renderType: Text.CurveRendering
            Layout.fillWidth: true
            text: root.clipboard.errorMessage.length > 0 ? root.clipboard.errorMessage : root.clipboard.paused ? Lang.s.clipboardPausedNote : ""
            color: root.clipboard.errorMessage.length > 0 ? Theme.danger : Theme.text2
            font.family: Theme.sans; font.pixelSize: Theme.captionFontSize
            elide: Text.ElideRight
        }
        ShellButton {
            implicitHeight: 26
            symbol: root.clipboard.paused ? "play_arrow" : "pause"
            symbolSize: 15
            text: root.clipboard.paused ? Lang.s.clipboardResume : Lang.s.clipboardPause
            font.pixelSize: Theme.smallFontSize
            enabled: !root.clipboard.busy
            onClicked: root.clipboard.setPaused(!root.clipboard.paused)
        }
        ShellButton {
            implicitHeight: 26
            symbol: "delete"
            symbolSize: 15
            text: root.confirmWipe ? Lang.s.clipboardWipeConfirm : Lang.s.clipboardWipe
            font.pixelSize: Theme.smallFontSize
            foreground: root.confirmWipe ? Theme.danger : Theme.text
            enabled: !root.clipboard.busy && root.clipboard.entries.length > 0
            onClicked: {
                if (root.confirmWipe) { root.clipboard.wipe(); root.confirmWipe = false; }
                else root.confirmWipe = true;
            }
        }
    }
}
