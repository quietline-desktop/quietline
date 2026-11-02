import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import ".."
import "../controls"
import "../logic/Models.js" as Models

// Поиск `Super+Space` по центру экрана: крупное поле и результаты по разделам —
// «Лучшее совпадение», приложения (со значками), действия и разделы настроек, файлы
// домашнего каталога; вычисление — первой строкой. ↑/↓ выбирают результат, Enter
// открывает, Esc закрывает окно.
ColumnLayout {
    id: root
    required property var desktop
    required property var services
    required property var finder
    required property string monitorName
    property int selected: 0
    readonly property var results: Models.searchResults(field.text, desktop.entries, finder.files, finder.home, 40, Lang.s)
    readonly property var rows: Models.searchSections(results, field.text, Lang.s)
    readonly property int current: Math.min(selected, results.length - 1)
    // Высота содержимого — по ней окно подстраивает свой размер.
    readonly property real contentHeight: 54 + (results.length ? 1 + Math.min(list.contentHeight + 16, 440) : field.text.length ? 49 : 0)
    signal done()
    // Выход, перезагрузка и выключение подтверждаются диалогом сеанса.
    signal sessionRequested(string action)
    signal clipboardRequested()
    spacing: 0

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
            else if (item.id === "screenshot") { root.done(); Quickshell.execDetached(["sh", "-c", "sleep 0.3; exec quietline-shell screenshot region"]); }
            else if (item.id === "clipboard") root.clipboardRequested();
            else root.sessionRequested(item.id);
            break;
        }
    }
    function select(index) {
        selected = Math.max(0, Math.min(index, results.length - 1));
        var row = rows.findIndex(entry => !entry.header && entry.index === selected);
        if (row >= 0) list.positionViewAtIndex(row, ListView.Contain);
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.preferredHeight: 54
        Layout.leftMargin: 18; Layout.rightMargin: 18
        spacing: 12
        Icon { name: "search"; size: 24; color: Theme.text2 }
        TextField {
            id: field
            Layout.fillWidth: true
            placeholderText: Lang.s.searchPlaceholder
            font.family: Theme.sans; font.pixelSize: 21; font.weight: Font.Normal
            renderType: Text.CurveRendering
            color: Theme.text; placeholderTextColor: Theme.text3
            selectionColor: Theme.accent; selectedTextColor: Theme.accentForeground
            selectByMouse: true
            padding: 0
            background: Item {}
            Accessible.name: Lang.s.searchTitle
            onTextChanged: { root.selected = 0; root.finder.query = text; list.positionViewAtBeginning(); }
            onAccepted: root.activate(root.results[root.current])
            Keys.onDownPressed: root.select(root.selected + 1)
            Keys.onUpPressed: root.select(root.selected - 1)
        }
        Text {
            renderType: Text.CurveRendering
            visible: root.results.length > 0
            text: Lang.s.searchOpenHint
            color: Theme.text3
            font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
        }
    }
    Rectangle {
        visible: root.results.length > 0 || field.text.length > 0
        Layout.fillWidth: true
        implicitHeight: 1
        color: Theme.hairline
    }
    ListView {
        id: list
        visible: root.results.length > 0
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.margins: 8
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        model: root.rows
        ScrollBar.vertical: ShellScrollBar {}
        delegate: Item {
            id: entry
            required property var modelData
            readonly property var item: modelData.header ? null : modelData.item
            readonly property bool chosen: !modelData.header && modelData.index === root.current
            readonly property bool large: !!item && item.kind === "calc"
            width: list.width - 6
            height: modelData.header ? 26 : large ? 48 : 40
            Text {
                renderType: Text.CurveRendering
                visible: entry.modelData.header
                x: 10; anchors.bottom: parent.bottom; anchors.bottomMargin: 4
                text: entry.modelData.header ? entry.modelData.title.toUpperCase() : ""
                color: Theme.text3
                font.family: Theme.sans; font.pixelSize: Theme.captionFontSize; font.weight: Font.DemiBold; font.letterSpacing: 0.6
            }
            Rectangle {
                visible: !!entry.item
                anchors.fill: parent
                radius: Theme.radiusRow
                color: entry.chosen ? Theme.accent : rowArea.containsMouse ? Theme.fill : "transparent"
                MouseArea {
                    id: rowArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.activate(entry.item)
                    onEntered: root.selected = entry.modelData.index
                }
                RowLayout {
                    anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 12
                    spacing: 12
                    Item {
                        implicitWidth: 28; implicitHeight: 28
                        Image {
                            id: appIcon
                            anchors.fill: parent
                            visible: !!entry.item && entry.item.kind === "app"
                            source: visible ? Quickshell.iconPath(entry.item.icon || "", true) : ""
                            sourceSize.width: 56; sourceSize.height: 56
                            smooth: true; mipmap: true
                        }
                        Icon {
                            anchors.centerIn: parent
                            visible: !appIcon.visible || appIcon.status !== Image.Ready
                            name: Models.searchSymbol(entry.item)
                            size: 20
                            color: entry.chosen ? Theme.accentForeground : Theme.text2
                        }
                    }
                    Column {
                        Layout.fillWidth: true
                        Text {
                            renderType: Text.CurveRendering
                            width: parent.width
                            text: entry.item ? entry.item.title : ""
                            color: entry.chosen ? Theme.accentForeground : Theme.text
                            font.family: Theme.sans
                            font.pixelSize: entry.large ? 20 : 14
                            font.weight: entry.large ? Font.Light : Font.Normal
                            elide: Text.ElideRight; textFormat: Text.PlainText
                        }
                        Text {
                            renderType: Text.CurveRendering
                            visible: !!entry.item && entry.item.kind === "file"
                            width: parent.width
                            text: entry.item ? entry.item.subtitle : ""
                            color: entry.chosen ? Theme.accentForeground2 : Theme.text2
                            font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
                            elide: Text.ElideMiddle; textFormat: Text.PlainText
                        }
                    }
                    Text {
                        renderType: Text.CurveRendering
                        visible: entry.large
                        text: entry.item ? entry.item.subtitle : ""
                        color: entry.chosen ? Theme.accentForeground2 : Theme.text3
                        font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
                    }
                }
            }
        }
    }
    Text {
        renderType: Text.CurveRendering
        visible: field.text.length > 0 && root.results.length === 0
        Layout.alignment: Qt.AlignHCenter
        Layout.topMargin: 14; Layout.bottomMargin: 14
        text: root.finder.errorMessage.length > 0 ? root.finder.errorMessage : Lang.s.nothingFound
        color: root.finder.errorMessage.length > 0 ? Theme.danger : Theme.text2
        font.family: Theme.sans; font.pixelSize: Theme.fontSize
    }
}
