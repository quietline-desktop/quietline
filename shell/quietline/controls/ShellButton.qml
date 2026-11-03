import QtQuick
import QtQuick.Controls
import Quickshell
import ".."

// Плоская кнопка оболочки: значок `symbol` и/или текст, подсветка при наведении, рамка
// фокуса клавиатуры и подсказка. `emphasized` — основная кнопка (заливка акцентом),
// `selected` — нажатое состояние панели (светлая подложка).
Button {
    id: root
    property string hint: text
    property bool emphasized: false
    property bool selected: false
    property bool busy: false
    property string symbol: ""
    property bool symbolFilled: true
    property real symbolSize: Theme.iconSize
    property real radius: Theme.radiusSmall
    // Цвет текста и значка доступной кнопки без выделения.
    property color foreground: Theme.text
    // Подсказка показывается общим HintPopup окна кнопки: ToolTip Qt обрезался бы тонкой панелью и доком.
    property bool hintBelow: true
    font.family: Theme.sans
    font.pixelSize: Theme.fontSize
    font.weight: Font.Medium
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    implicitHeight: 28
    implicitWidth: Math.max(implicitHeight, implicitContentWidth + (text.length > 0 ? 16 : 8))
    padding: 0
    Accessible.name: hint || text
    Accessible.description: busy ? Lang.s.buttonBusy : ""
    function updateHint() {
        var host = QsWindow.window;
        if (!host || !host.hints) return;
        if (hovered && !pressed && hint.length > 0 && hint !== text) host.hints.show(root, hint, hintBelow);
        else host.hints.hide(root);
    }
    onHoveredChanged: updateHint()
    onPressedChanged: updateHint()
    onHintChanged: { if (hovered) updateHint(); }
    readonly property color contentColor: !enabled ? Theme.text3 : emphasized ? Theme.accentForeground : foreground
    background: Rectangle {
        radius: root.radius
        color: root.emphasized ? (root.down ? Qt.darker(Theme.accent, 1.15) : Theme.accent)
             : root.down ? Theme.fillStrong : root.selected || root.hovered ? Theme.fillHover : "transparent"
        border.width: root.visualFocus ? 2 : 0
        border.color: Theme.accent
        opacity: root.enabled ? 1 : 0.6
        Behavior on color { ColorAnimation { duration: Theme.fastDuration } }
    }
    // Ширина содержимого не зависит от ширины кнопки: подпись сокращается многоточием,
    // только если владелец задал кнопке ширину меньше содержимого.
    readonly property real symbolPart: symbol.length > 0 && !busy ? symbolSize + (label.text.length > 0 ? 6 : 0) : 0
    contentItem: Item {
        id: content
        implicitWidth: root.symbolPart + (label.text.length > 0 ? label.implicitWidth : 0)
        implicitHeight: Math.max(root.symbolSize, label.implicitHeight)
        Row {
            anchors.centerIn: parent
            spacing: 6
            Icon {
                visible: root.symbol.length > 0 && !root.busy
                anchors.verticalCenter: parent.verticalCenter
                name: root.symbol
                filled: root.symbolFilled
                size: root.symbolSize
                color: root.contentColor
            }
            Text {
                renderType: Theme.textRenderType(QsWindow.window)
                id: label
                visible: text.length > 0
                anchors.verticalCenter: parent.verticalCenter
                width: Math.min(implicitWidth, Math.max(0, content.width - root.symbolPart))
                text: root.busy ? "…" : root.text
                font: root.font
                color: root.contentColor
                elide: Text.ElideRight
            }
        }
    }
    HoverHandler { cursorShape: root.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor }
}
