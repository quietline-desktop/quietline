import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import ".."
import "../controls"
import "../logic/Models.js" as Models

// Поиск `Super+Space` по центру экрана: крупное поле сверху. Пустое поле — меню групп
// («Приложения», «Действия», «Питание», «Настройки»): ↑/↓ выбирают, Enter или → открывают
// группу, ←, Backspace на пустом поле и Esc возвращают к группам. Любой ввод — поиск по всем
// источникам с разделами «Лучшее совпадение», приложения, действия и разделы настроек, файлы;
// вычисление — первой строкой. Enter открывает выбранное, Tab переходит к следующему разделу,
// Esc закрывает окно. Высота содержимого `contentHeight` меняется плавно внутри поверхности
// высотой `maxHeight`.
ColumnLayout {
    id: root
    required property var desktop
    required property var services
    required property var finder
    required property string monitorName
    property bool reducedMotion: false
    // Открытая группа меню; пусто — список групп.
    property string group: ""
    // Номер выбранного результата или пункта меню (`index` строки).
    property int selected: 0
    readonly property bool searching: field.text.trim().length > 0
    readonly property var results: searching ? Models.searchResults(field.text, desktop.entries,
        Models.searchFileMatches(finder.files, field.text), finder.home, 40, Lang.s) : []
    readonly property var resultRows: Models.searchSections(results, field.text, Lang.s)
    readonly property var browseRows: Models.searchBrowseRows(group, desktop.entries, Lang.s)
    readonly property var rows: searching ? resultRows : browseRows
    readonly property int count: searching ? results.length : browseRows.length
    readonly property int current: Math.min(selected, count - 1)
    readonly property var currentItem: {
        var row = rows.find(entry => !entry.header && entry.index === current);
        return row ? row.item : null;
    }
    readonly property bool showMessage: searching && results.length === 0
    readonly property real listMax: 420
    readonly property real maxHeight: 54 + 1 + listMax
    readonly property real contentHeight: 54 + (rows.length ? 1 + Models.searchListHeight(rows, listMax) : showMessage ? 49 : 0)
    signal done()
    // Выход, перезагрузка и выключение подтверждаются диалогом сеанса.
    signal sessionRequested(string action)
    signal clipboardRequested()
    spacing: 0

    function reset() { group = ""; field.clear(); selected = 0; field.forceActiveFocus(); }
    function rowOf(list, index) { return list.findIndex(entry => !entry.header && entry.index === index); }
    function openGroup(id) {
        group = id;
        selected = 0;
        browseList.slide(1);
    }
    function closeGroup() {
        var from = group;
        group = "";
        selected = Math.max(0, browseRows.findIndex(entry => entry.item.id === from));
        browseList.slide(-1);
    }
    function activate(item) {
        if (!item) return;
        switch (item.kind) {
        case "group": openGroup(item.id); break;
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
    function select(index) { selected = Math.max(0, Math.min(index, count - 1)); }
    // Tab: первый результат следующего раздела, после последнего — снова первый.
    function nextSection() {
        if (!searching) { select(current + 1 < count ? current + 1 : 0); return; }
        var row = rowOf(rows, current);
        for (var i = row + 1; i < rows.length; i++) {
            if (rows[i].header && i + 1 < rows.length) { selected = rows[i + 1].index; return; }
        }
        selected = 0;
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.preferredHeight: 54
        Layout.leftMargin: 18; Layout.rightMargin: 18
        spacing: 12
        Icon { name: "search"; size: 24; color: Theme.text2 }
        Rectangle {
            id: crumb
            visible: root.group.length > 0 && !root.searching
            implicitWidth: crumbText.implicitWidth + 18
            implicitHeight: 26
            radius: 8
            color: Theme.fill2
            Text {
                id: crumbText
                renderType: Text.CurveRendering
                anchors.centerIn: parent
                text: {
                    var row = Models.searchGroups(Lang.s).find(entry => entry.id === root.group);
                    return row ? row.title : "";
                }
                color: Theme.text
                font.family: Theme.sans; font.pixelSize: Theme.fontSize; font.weight: Font.Medium
            }
        }
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
            onTextChanged: {
                if (root.searching && root.group.length > 0) root.group = "";
                root.selected = 0;
                root.finder.query = text;
            }
            onAccepted: root.activate(root.currentItem)
            Keys.onDownPressed: root.select(root.current + 1)
            Keys.onUpPressed: root.select(root.current - 1)
            Keys.onTabPressed: root.nextSection()
            Keys.onRightPressed: event => {
                if (!root.searching && root.currentItem && root.currentItem.kind === "group") root.openGroup(root.currentItem.id);
                else event.accepted = false;
            }
            Keys.onLeftPressed: event => {
                if (!root.searching && root.group.length > 0) root.closeGroup();
                else event.accepted = false;
            }
            Keys.onPressed: event => {
                if (event.key === Qt.Key_Backspace && text.length === 0 && root.group.length > 0) { root.closeGroup(); event.accepted = true; }
            }
            Keys.onEscapePressed: event => {
                if (!root.searching && root.group.length > 0) root.closeGroup();
                else event.accepted = false;
            }
        }
        Text {
            renderType: Text.CurveRendering
            text: root.searching ? Lang.s.searchOpenHint : root.group.length > 0 ? Lang.s.searchBackHint : Lang.s.searchGroupHint
            color: Theme.text3
            font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
        }
    }
    Rectangle {
        visible: root.contentHeight > 54
        Layout.fillWidth: true
        implicitHeight: 1
        color: Theme.hairline
    }
    // Меню групп и результаты лежат друг на друге и сменяются затуханием со сдвигом.
    Item {
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        SearchList {
            id: browseList
            anchors.fill: parent
            rows: root.browseRows
            currentRow: root.searching ? -1 : root.rowOf(root.browseRows, root.current)
            reducedMotion: root.reducedMotion
            onActivated: item => root.activate(item)
            onPointed: index => { if (!root.searching) root.selected = index; }
            fade: root.searching ? 0 : 1
            offsetY: root.searching ? -8 : 0
            Behavior on fade { enabled: !root.reducedMotion; NumberAnimation { duration: Theme.motionDuration; easing.type: Easing.OutCubic } }
            Behavior on offsetY { enabled: !root.reducedMotion; NumberAnimation { duration: Theme.motionDuration; easing.type: Easing.OutCubic } }
        }
        SearchList {
            id: resultList
            anchors.fill: parent
            rows: root.resultRows
            currentRow: root.searching ? root.rowOf(root.resultRows, root.current) : -1
            animateRows: true
            reducedMotion: root.reducedMotion
            onActivated: item => root.activate(item)
            onPointed: index => { if (root.searching) root.selected = index; }
            fade: root.searching ? 1 : 0
            offsetY: root.searching ? 0 : 8
            Behavior on fade { enabled: !root.reducedMotion; NumberAnimation { duration: Theme.motionDuration; easing.type: Easing.OutCubic } }
            Behavior on offsetY { enabled: !root.reducedMotion; NumberAnimation { duration: Theme.motionDuration; easing.type: Easing.OutCubic } }
        }
        Text {
            renderType: Text.CurveRendering
            visible: root.showMessage
            anchors.horizontalCenter: parent.horizontalCenter
            y: 14
            text: root.finder.errorMessage.length > 0 ? root.finder.errorMessage
                : root.finder.pending ? Lang.s.searchFilesPending : Lang.s.nothingFound
            color: root.finder.errorMessage.length > 0 ? Theme.danger : Theme.text2
            font.family: Theme.sans; font.pixelSize: Theme.fontSize
        }
    }
}
