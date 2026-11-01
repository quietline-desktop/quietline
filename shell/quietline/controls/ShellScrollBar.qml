import QtQuick
import QtQuick.Controls
import ".."

// Тонкая полоса прокрутки: видна, только когда есть что прокручивать, и ярче под указателем.
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
    implicitHeight: 8
    contentItem: Rectangle {
        implicitWidth: 4
        implicitHeight: 4
        radius: 2
        color: root.pressed || root.hovered ? Qt.rgba(1, 1, 1, 0.45) : Qt.rgba(1, 1, 1, 0.22)
        opacity: root.size < 1 ? 1 : 0
        Behavior on color { ColorAnimation { duration: Theme.fastDuration } }
    }
    background: Item {}
}
