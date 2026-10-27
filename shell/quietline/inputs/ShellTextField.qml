import QtQuick
import QtQuick.Controls
import ".."

// Текстовое поле формы: общие цвета, рамка фокуса и доступное имя `label`.
TextField {
    id: root
    property string label: placeholderText
    font.family: Theme.sans
    font.pixelSize: Theme.fontSize
    color: Theme.text
    placeholderTextColor: Theme.muted
    selectByMouse: true
    implicitHeight: 32
    leftPadding: 10; rightPadding: 10
    Accessible.name: label
    background: Rectangle {
        color: Theme.background
        radius: Theme.controlRadius
        border.width: 1
        border.color: root.activeFocus ? Theme.accent : Theme.border
    }
}
