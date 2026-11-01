import QtQuick
import QtQuick.Controls
import ".."

// Полоса прокрутки в цветах оболочки; видна, только когда есть что прокручивать.
// Вертикальная прижата к правому краю родителя, горизонтальная — к нижнему: `ScrollView`
// не задаёт положение подставленной полосы. Чтобы полоса не закрывала содержимое,
// `ScrollView` задаёт `rightPadding: ScrollBar.vertical.visible ? ScrollBar.vertical.width + 4 : 0`.
ScrollBar {
    id: root
    policy: ScrollBar.AsNeeded
    x: orientation === Qt.Vertical && parent ? parent.width - width : 0
    y: orientation === Qt.Horizontal && parent ? parent.height - height : 0
    padding: 2
    implicitWidth: 8
    contentItem: Rectangle {
        implicitWidth: 4
        implicitHeight: 36
        radius: 3
        color: root.pressed ? Theme.accent : root.hovered ? Theme.text : Theme.border
        opacity: root.size < 1 ? 1 : 0
    }
    background: Rectangle { color: Theme.background; radius: 3; opacity: root.size < 1 ? 0.5 : 0 }
}
