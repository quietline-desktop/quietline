import QtQuick
import Quickshell
import QtQuick.Layouts
import ".."
import "../controls"

// Список выбора поверх формы входа (пользователи или сеансы) в виде всплывающего меню
// оболочки: строки 26 px, выбранная — акцентом. `chosen(id)` — щелчок или Enter по строке.
Rectangle {
    id: root
    // [{id, label, initial}] — `initial` рисует кружок с буквой, без него — галочка у выбранной.
    property var items: []
    property string current: ""
    property bool avatars: false
    property int highlighted: 0
    signal chosen(string id)
    signal dismissed()

    implicitWidth: 240
    implicitHeight: column.implicitHeight + 10
    radius: 14
    color: Theme.popupSurface
    border.width: 1; border.color: Theme.border
    focus: visible
    onVisibleChanged: if (visible) highlighted = Math.max(0, items.findIndex(item => item.id === current))
    Keys.onUpPressed: highlighted = (highlighted + items.length - 1) % items.length
    Keys.onDownPressed: highlighted = (highlighted + 1) % items.length
    Keys.onReturnPressed: if (items.length) chosen(items[highlighted].id)
    Keys.onEnterPressed: if (items.length) chosen(items[highlighted].id)
    Keys.onEscapePressed: dismissed()

    ColumnLayout {
        id: column
        anchors { fill: parent; margins: 5 }
        spacing: 0
        Repeater {
            model: root.items
            Rectangle {
                required property var modelData
                required property int index
                Layout.fillWidth: true
                implicitHeight: 26
                radius: 8
                color: index === root.highlighted ? Theme.accent : "transparent"
                RowLayout {
                    anchors { fill: parent; leftMargin: 9; rightMargin: 9 }
                    spacing: 8
                    Icon {
                        visible: !root.avatars
                        name: modelData.id === root.current ? "check" : ""
                        size: 16
                        color: "#ffffff"
                        Layout.preferredWidth: 16
                    }
                    Rectangle {
                        visible: root.avatars
                        implicitWidth: 18; implicitHeight: 18; radius: 9
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0; color: "#6a8cff" }
                            GradientStop { position: 1; color: "#b06aff" }
                        }
                        Text {
                            anchors.centerIn: parent
                            renderType: Theme.textRenderType(QsWindow.window)
                            text: String(modelData.label).charAt(0).toUpperCase()
                            color: "#ffffff"
                            font.family: Theme.sans; font.pixelSize: 10; font.weight: Font.Bold
                        }
                    }
                    Text {
                        Layout.fillWidth: true
                        renderType: Theme.textRenderType(QsWindow.window)
                        text: modelData.label
                        elide: Text.ElideRight
                        color: index === root.highlighted ? Theme.accentForeground : "#f2f2f5"
                        font.family: Theme.sans; font.pixelSize: Theme.fontSize
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onEntered: root.highlighted = index
                    onClicked: root.chosen(modelData.id)
                }
            }
        }
    }
}
