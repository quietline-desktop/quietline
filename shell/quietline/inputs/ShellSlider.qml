import QtQuick
import QtQuick.Controls
import ".."

// Ползунок с темой и клавишами со стрелками; доступное имя — `label` и значение в процентах.
Slider {
    id: root
    property string label: ""
    focusPolicy: Qt.StrongFocus
    stepSize: 0.01
    Accessible.name: label + " " + Math.round(value / to * 100) + "%"
    implicitHeight: 28
    background: Rectangle {
        x: root.leftPadding; y: root.topPadding + root.availableHeight / 2 - height / 2
        width: root.availableWidth; height: 4; radius: 2
        color: Theme.raised
        Rectangle { width: root.visualPosition * parent.width; height: parent.height; radius: 2; color: Theme.accent }
    }
    handle: Rectangle {
        x: root.leftPadding + root.visualPosition * (root.availableWidth - width)
        y: root.topPadding + root.availableHeight / 2 - height / 2
        width: 16; height: 16; radius: 8
        color: root.pressed ? Theme.accent : Theme.text
        border.width: root.visualFocus ? 2 : 0
        border.color: Theme.accent
    }
}
