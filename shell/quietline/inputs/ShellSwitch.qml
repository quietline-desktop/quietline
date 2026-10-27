import QtQuick
import QtQuick.Controls
import ".."

// Переключатель с подписью слева; ползунок переключается без анимации.
Switch {
    id: root
    font.family: Theme.sans
    font.pixelSize: Theme.fontSize
    focusPolicy: Qt.StrongFocus
    Accessible.name: text
    indicator: Rectangle {
        implicitWidth: 36; implicitHeight: 20
        x: root.width - width - root.rightPadding
        y: (root.height - height) / 2
        radius: 10
        color: root.checked ? Theme.accent : Theme.raised
        border.width: root.visualFocus ? 2 : 1
        border.color: root.visualFocus ? Theme.accent : Theme.border
        opacity: root.enabled ? 1 : 0.45
        Rectangle {
            width: 14; height: 14; radius: 7
            y: 3; x: root.checked ? parent.width - width - 3 : 3
            color: root.checked ? Theme.accentText : Theme.text
        }
    }
    contentItem: Text {
        text: root.text
        rightPadding: root.indicator.width + 8
        color: root.enabled ? Theme.text : Theme.muted
        font: root.font
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
}
