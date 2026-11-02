import QtQuick
import QtQuick.Controls
import ".."

// Строка меню 26 px: значок `symbol`, текст, сочетание клавиш `shortcut` справа;
// под указателем или фокусом с клавиатуры (Tab, стрелки) — заливка акцентом; фокус, выданный
// при открытии меню мышью, строку не подсвечивает.
MenuItem {
    id: root
    property string symbol: ""
    property string shortcut: ""
    readonly property bool lit: enabled && (highlighted || hovered || visualFocus)
    implicitHeight: Theme.menuRowHeight
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    leftPadding: 10; rightPadding: 10
    contentItem: Row {
        spacing: 10
        Icon {
            visible: root.symbol.length > 0
            anchors.verticalCenter: parent.verticalCenter
            name: root.symbol
            size: 16
            color: root.lit ? Theme.accentForeground : Theme.text2
        }
        Text {
            renderType: Text.CurveRendering
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - (root.symbol.length > 0 ? 26 : 0) - shortcutLabel.implicitWidth - 10
            text: root.text
            color: !root.enabled ? Theme.text3 : root.lit ? Theme.accentForeground : Theme.text
            font.family: Theme.sans
            font.pixelSize: Theme.fontSize
            elide: Text.ElideRight
        }
        Text {
            renderType: Text.CurveRendering
            id: shortcutLabel
            anchors.verticalCenter: parent.verticalCenter
            text: root.shortcut
            color: root.lit ? Theme.accentForeground : Theme.text3
            font.family: Theme.sans
            font.pixelSize: Theme.smallFontSize
        }
    }
    background: Rectangle {
        radius: Theme.radiusSmall
        color: root.lit ? Theme.accent : "transparent"
    }
}
