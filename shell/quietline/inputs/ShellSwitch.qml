import QtQuick
import QtQuick.Controls
import ".."

// Переключатель 38×22 с подписью слева: включён — зелёная подложка, кружок справа.
Switch {
    id: root
    font.family: Theme.sans
    font.pixelSize: Theme.fontSize
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    Accessible.name: text
    indicator: Rectangle {
        implicitWidth: 38; implicitHeight: 22
        x: root.width - width - root.rightPadding
        y: (root.height - height) / 2
        radius: 11
        color: root.checked ? Theme.success : Theme.fillStrong
        border.width: root.visualFocus ? 2 : 0
        border.color: Theme.accent
        opacity: root.enabled ? 1 : 0.45
        Behavior on color { ColorAnimation { duration: Theme.fastDuration } }
        Rectangle {
            width: 18; height: 18; radius: 9
            y: 2; x: root.checked ? parent.width - width - 2 : 2
            color: "#ffffff"
            Behavior on x { NumberAnimation { duration: Theme.fastDuration; easing.type: Easing.OutCubic } }
        }
    }
    contentItem: Text {
        text: root.text
        rightPadding: root.indicator.width + 8
        color: root.enabled ? Theme.text : Theme.text3
        font: root.font
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
}
