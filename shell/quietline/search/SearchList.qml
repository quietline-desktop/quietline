import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import ".."
import "../controls"
import "../logic/Models.js" as Models

// Список панели поиска: строки `Models.searchSections` или `Models.searchBrowseRows`
// (заголовки разделов и результаты с ключом `key`). Модель — `ScriptModel` по ключу: строка
// с тем же ключом остаётся тем же делегатом, свежие данные берутся по ключу. Выбранная строка
// `currentRow` подсвечивается одной плашкой, которая переезжает к ней. С `animateRows` строки
// появляются и уходят затуханием, соседние сдвигаются плавно; `slide(direction)` сдвигает
// страницу целиком (вперёд — справа, назад — слева). `reducedMotion` выключает все переходы.
ListView {
    id: list
    required property var rows
    property int currentRow: -1
    property bool animateRows: false
    property bool reducedMotion: false
    // Последнее положение указателя на экране: выбор под указателем меняется только при его движении.
    property point pointer: Qt.point(-1, -1)
    property real pageShift: 0
    property real pageOpacity: 1
    // Сдвиг по вертикали и прозрачность при смене меню и результатов задаёт панель.
    property real offsetY: 0
    property real fade: 1
    readonly property var byKey: {
        var map = {};
        rows.forEach(row => map[row.key] = row);
        return map;
    }
    signal activated(var item)
    signal pointed(int index)

    function slide(direction) {
        if (reducedMotion) return;
        pageShiftAnimation.from = 28 * direction;
        page.restart();
    }
    // Номер строки ставится после того, как модель приняла новые строки.
    function syncCurrent() { currentIndex = currentRow; if (currentRow >= 0) positionViewAtIndex(currentRow, ListView.Contain); }
    onCurrentRowChanged: Qt.callLater(syncCurrent)
    onRowsChanged: Qt.callLater(syncCurrent)

    clip: true
    boundsBehavior: Flickable.StopAtBounds
    topMargin: 6; bottomMargin: 8
    leftMargin: 8; rightMargin: 8
    transform: Translate { x: list.pageShift; y: list.offsetY }
    opacity: pageOpacity * fade
    visible: opacity > 0
    model: ScriptModel { values: list.rows; objectProp: "key" }
    ScrollBar.vertical: ShellScrollBar {}
    ParallelAnimation {
        id: page
        NumberAnimation { id: pageShiftAnimation; target: list; property: "pageShift"; to: 0; duration: Theme.motionDuration; easing.type: Easing.OutCubic }
        NumberAnimation { target: list; property: "pageOpacity"; from: 0; to: 1; duration: Theme.motionDuration; easing.type: Easing.OutCubic }
    }

    highlightFollowsCurrentItem: false
    highlight: Rectangle {
        width: list.width - list.leftMargin - list.rightMargin - 6
        y: list.currentItem ? list.currentItem.y : 0
        height: list.currentItem ? list.currentItem.height : 0
        visible: !!list.currentItem
        radius: Theme.radiusRow
        color: Theme.accent
        // При сдвиге страницы подсветка встаёт на место сразу, а не переезжает со строки прежней страницы.
        Behavior on y { enabled: !list.reducedMotion && !page.running; SmoothedAnimation { duration: Theme.fastDuration; velocity: -1 } }
        Behavior on height { enabled: !list.reducedMotion && !page.running; SmoothedAnimation { duration: Theme.fastDuration; velocity: -1 } }
    }

    add: Transition {
        enabled: list.animateRows && !list.reducedMotion
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fastDuration; easing.type: Easing.OutCubic }
        NumberAnimation { property: "scale"; from: 0.97; to: 1; duration: Theme.fastDuration; easing.type: Easing.OutCubic }
    }
    remove: Transition {
        enabled: list.animateRows && !list.reducedMotion
        NumberAnimation { property: "opacity"; to: 0; duration: Theme.fastDuration; easing.type: Easing.OutCubic }
    }
    displaced: Transition {
        enabled: list.animateRows && !list.reducedMotion
        NumberAnimation { property: "y"; duration: Theme.fastDuration; easing.type: Easing.OutCubic }
        NumberAnimation { properties: "opacity,scale"; to: 1; duration: Theme.fastDuration }
    }
    move: Transition {
        enabled: list.animateRows && !list.reducedMotion
        NumberAnimation { property: "y"; duration: Theme.fastDuration; easing.type: Easing.OutCubic }
        NumberAnimation { properties: "opacity,scale"; to: 1; duration: Theme.fastDuration }
    }

    delegate: Item {
        id: entry
        required property var modelData
        required property int index
        readonly property var row: list.byKey[modelData.key] || modelData
        readonly property var item: row.header ? null : row.item
        readonly property bool chosen: !row.header && index === list.currentIndex
        readonly property bool large: !!item && item.kind === "calc"
        readonly property bool twoLines: !!item && (item.kind === "file" || item.kind === "group")
        width: list.width - list.leftMargin - list.rightMargin - 6
        height: row.header ? 26 : large ? 48 : twoLines ? 44 : 40
        Text {
            renderType: Theme.textRenderType(QsWindow.window)
            visible: entry.row.header
            x: 10; anchors.bottom: parent.bottom; anchors.bottomMargin: 4
            text: entry.row.header ? entry.row.title.toUpperCase() : ""
            color: Theme.text3
            font.family: Theme.sans; font.pixelSize: Theme.captionFontSize; font.weight: Font.DemiBold; font.letterSpacing: 0.6
        }
        MouseArea {
            visible: !!entry.item
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onPositionChanged: mouse => {
                var point = mapToGlobal(mouse.x, mouse.y);
                if (Math.abs(point.x - list.pointer.x) < 2 && Math.abs(point.y - list.pointer.y) < 2) return;
                var first = list.pointer.x < 0;
                list.pointer = point;
                if (!first) list.pointed(entry.row.index);
            }
            onClicked: list.activated(entry.item)
        }
        RowLayout {
            visible: !!entry.item
            anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 12
            spacing: 12
            Item {
                implicitWidth: 28; implicitHeight: 28
                Image {
                    id: appIcon
                    anchors.fill: parent
                    visible: !!entry.item && entry.item.kind === "app" && status === Image.Ready
                    source: !!entry.item && entry.item.kind === "app" ? Quickshell.iconPath(entry.item.icon || "", true) : ""
                    asynchronous: true
                    sourceSize.width: 56; sourceSize.height: 56
                    smooth: true; mipmap: true
                }
                Icon {
                    anchors.centerIn: parent
                    visible: !entry.item || entry.item.kind !== "app" || appIcon.status === Image.Error || appIcon.source == ""
                    name: Models.searchSymbol(entry.item)
                    size: 20
                    color: entry.chosen ? Theme.accentForeground : Theme.text2
                    Behavior on color { enabled: !list.reducedMotion; ColorAnimation { duration: Theme.fastDuration } }
                }
            }
            Column {
                Layout.fillWidth: true
                Text {
                    renderType: Theme.textRenderType(QsWindow.window)
                    width: parent.width
                    text: entry.item ? entry.item.title : ""
                    color: entry.chosen ? Theme.accentForeground : Theme.text
                    Behavior on color { enabled: !list.reducedMotion; ColorAnimation { duration: Theme.fastDuration } }
                    font.family: Theme.sans
                    font.pixelSize: entry.large ? 22 : 14
                    font.weight: entry.large ? Font.Light : Font.Normal
                    font.features: entry.large ? {"tnum": 1} : {}
                    elide: Text.ElideRight; textFormat: Text.PlainText
                }
                Text {
                    renderType: Theme.textRenderType(QsWindow.window)
                    visible: entry.twoLines
                    width: parent.width
                    text: entry.item ? entry.item.subtitle : ""
                    color: entry.chosen ? Theme.accentForeground2 : Theme.text2
                    Behavior on color { enabled: !list.reducedMotion; ColorAnimation { duration: Theme.fastDuration } }
                    font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
                    elide: entry.item && entry.item.kind === "file" ? Text.ElideMiddle : Text.ElideRight
                    textFormat: Text.PlainText
                }
            }
            Text {
                renderType: Theme.textRenderType(QsWindow.window)
                visible: entry.large
                text: entry.item ? entry.item.subtitle : ""
                color: entry.chosen ? Theme.accentForeground2 : Theme.text3
                font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
            }
            Icon {
                visible: !!entry.item && entry.item.kind === "group"
                name: "chevron_right"
                size: 20
                color: entry.chosen ? Theme.accentForeground2 : Theme.text3
                Behavior on color { enabled: !list.reducedMotion; ColorAnimation { duration: Theme.fastDuration } }
            }
        }
    }
}
