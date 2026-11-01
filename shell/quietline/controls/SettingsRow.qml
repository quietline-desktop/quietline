import QtQuick
import QtQuick.Layouts
import ".."

// Строка группы настроек, не ниже 44 px: подпись и пояснение слева, элемент управления
// справа (дочерние элементы), всё по вертикали по центру строки.
// `symbol` — значок в круге 28 px слева на подложке `symbolBackground`.
// `fill` — дочерний элемент занимает всю ширину строки под подписью (ползунок, список).
// `below` — содержимое во всю ширину под строкой (например, поле пароля), видно при `expanded`.
// `clickable` — строка нажимается мышью, `Enter` и `Space` (сигнал `clicked`), под
// указателем подсвечивается; элементы управления в строке нажимаются отдельно.
Item {
    id: root
    property string label: ""
    property string note: ""
    property bool fill: false
    property string symbol: ""
    property color symbolBackground: Theme.fill2
    property color symbolColor: Theme.text
    property bool labelBold: false
    property bool clickable: false
    property bool expanded: false
    signal clicked()
    default property alias trailing: slot.data
    property alias below: belowColumn.data
    // Ширина, которую может занять элемент справа: подпись сохраняет до 200 px.
    readonly property real trailingWidth: Math.max(0, width - 28 - 12 - Math.min(texts.implicitWidth, 200) - (symbol ? 40 : 0))
    Layout.fillWidth: true
    implicitHeight: Math.max(44, column.implicitHeight + 20)
    activeFocusOnTab: clickable && enabled
    Accessible.role: clickable ? Accessible.Button : Accessible.StaticText
    Accessible.name: label
    Accessible.description: note
    Keys.onReturnPressed: { if (clickable) clicked(); }
    Keys.onSpacePressed: { if (clickable) clicked(); }

    // Подсветка и нажатие — только по основной строке, без содержимого `below`.
    Rectangle {
        x: 4; y: 4
        width: parent.width - 8
        height: (root.expanded ? line.y + line.height + column.y : parent.height) - 8
        radius: Theme.radiusControl
        color: root.clickable && pressArea.pressed ? Theme.fillStrong
             : root.clickable && pressArea.containsMouse ? Theme.fill : "transparent"
        border.width: root.activeFocus ? 2 : 0
        border.color: Theme.accent
        Behavior on color { ColorAnimation { duration: Theme.fastDuration } }
        MouseArea {
            id: pressArea
            anchors.fill: parent; anchors.margins: -4
            enabled: root.clickable && root.enabled
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.clicked()
        }
    }

    ColumnLayout {
        id: column
        x: 14; y: Math.round((root.height - implicitHeight) / 2)
        width: parent.width - 28
        spacing: 8
        RowLayout {
            id: line
            Layout.fillWidth: true
            spacing: 12
            Rectangle {
                visible: root.symbol.length > 0
                implicitWidth: 28; implicitHeight: 28; radius: 14
                color: root.symbolBackground
                Icon { anchors.centerIn: parent; name: root.symbol; filled: true; size: 16; color: root.symbolColor }
            }
            ColumnLayout {
                id: texts
                Layout.fillWidth: true
                visible: root.label.length > 0 || root.note.length > 0
                spacing: 2
                Text {
                    renderType: Text.CurveRendering
                    Layout.fillWidth: true
                    Layout.minimumWidth: Math.min(implicitWidth, 200)
                    visible: root.label.length > 0
                    text: root.label
                    color: root.enabled ? Theme.text : Theme.text3
                    font.family: Theme.sans; font.pixelSize: Theme.fontSize
                    font.weight: root.labelBold ? Font.DemiBold : Font.Normal
                    elide: Text.ElideRight
                }
                Text {
                    renderType: Text.CurveRendering
                    Layout.fillWidth: true
                    visible: root.note.length > 0
                    text: root.note
                    color: Theme.text2
                    font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
                    wrapMode: Text.Wrap
                }
            }
            Row {
                id: slotRow
                visible: !root.fill
                Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                Layout.maximumWidth: root.trailingWidth
                spacing: 8
            }
        }
        Item {
            id: fillHolder
            visible: root.fill
            Layout.fillWidth: true
            implicitHeight: slot.implicitHeight
        }
        ColumnLayout {
            id: belowColumn
            visible: root.expanded
            Layout.fillWidth: true
            spacing: 8
        }
    }
    // Линия над строкой — у всех, кроме первой видимой строки группы. `Repeater` среди
    // соседей не строка: у него нулевая высота.
    readonly property bool firstInGroup: {
        var siblings = parent ? parent.children : [];
        for (var i = 0; i < siblings.length; i++) if (siblings[i].visible && siblings[i].implicitHeight > 0) return siblings[i] === root;
        return true;
    }
    Rectangle {
        visible: !root.firstInGroup
        x: root.symbol ? 54 : 14; width: parent.width - x; height: 1
        color: Theme.hairline
    }
    // Дочерние элементы живут в одном контейнере; он переносится под подпись при `fill`.
    Row {
        id: slot
        // Предел ширины для дочернего текста справа (`Value` в окне «Настройки»).
        readonly property real maxChildWidth: root.fill ? fillHolder.width : root.trailingWidth
        parent: root.fill ? fillHolder : slotRow
        width: root.fill ? fillHolder.width : implicitWidth
        spacing: 8
    }
}
