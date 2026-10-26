import QtQuick
import QtQuick.Controls
import ".."

// Полоса прокрутки в цветах оболочки; видна, только когда есть что прокручивать.
ScrollBar {
    id: root
    policy: ScrollBar.AsNeeded
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
