import QtQuick
import QtQuick.Controls
import ".."

// Пункт контекстного меню оболочки.
MenuItem {
    id: root
    implicitHeight: 32
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    contentItem: Text {
        text: root.text
        color: root.enabled ? Theme.text : Theme.muted
        font.family: Theme.sans
        font.pixelSize: Theme.fontSize
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    background: Rectangle {
        radius: Theme.controlRadius
        color: root.highlighted || root.hovered || root.activeFocus ? Theme.raised : "transparent"
        border.width: root.visualFocus ? 1 : 0
        border.color: Theme.accent
    }
}
