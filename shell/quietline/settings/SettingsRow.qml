import QtQuick
import QtQuick.Layouts
import ".."

// Строка группы настроек, не ниже 44 px: подпись и пояснение слева, элемент управления
// справа (дочерние элементы), всё по вертикали по центру строки. `fill` — дочерний элемент
// занимает всю ширину строки под подписью (ползунок, список).
Item {
    id: root
    property string label: ""
    property string note: ""
    property bool fill: false
    default property alias trailing: slot.data
    // Ширина, которую может занять элемент справа: подпись сохраняет до 200 px.
    readonly property real trailingWidth: Math.max(0, width - 28 - 12 - Math.min(texts.implicitWidth, 200))
    Layout.fillWidth: true
    implicitHeight: Math.max(44, fill ? column.implicitHeight + 20 : Math.max(texts.implicitHeight, slot.implicitHeight) + 20)
    ColumnLayout {
        id: column
        x: 14; y: root.fill ? 10 : Math.round((root.height - implicitHeight) / 2)
        width: parent.width - 28
        spacing: 8
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
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
                    color: Theme.text
                    font.family: Theme.sans; font.pixelSize: Theme.fontSize
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
    }
    // Линия над строкой — у всех, кроме первой видимой строки группы.
    readonly property bool firstInGroup: {
        var siblings = parent ? parent.children : [];
        for (var i = 0; i < siblings.length; i++) if (siblings[i].visible) return siblings[i] === root;
        return true;
    }
    Rectangle {
        visible: !root.firstInGroup
        x: 14; width: parent.width - 14; height: 1
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
