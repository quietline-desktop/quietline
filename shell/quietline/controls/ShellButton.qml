import QtQuick
import QtQuick.Controls
import Quickshell
import ".."

// Кнопка оболочки: общие цвета, рамка фокуса клавиатуры и подсказка.
Button {
    id: root
    property string hint: text
    property bool emphasized: false
    property bool busy: false
    // Цвет текста доступной кнопки без выделения.
    property color foreground: Theme.text
    // Подсказка показывается общим HintPopup окна кнопки: ToolTip Qt обрезался бы тонкой панелью и доком.
    property bool hintBelow: true
    font.family: Theme.sans
    font.pixelSize: Theme.fontSize
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    implicitHeight: 28
    implicitWidth: Math.max(28, label.implicitWidth + 16)
    padding: 4
    Accessible.name: hint || text
    Accessible.description: busy ? Lang.s.buttonBusy : ""
    function updateHint() {
        var host = QsWindow.window;
        if (!host || !host.hints) return;
        if (hovered && !pressed && hint.length > 0) host.hints.show(root, hint, hintBelow);
        else host.hints.hide(root);
    }
    onHoveredChanged: updateHint()
    onPressedChanged: updateHint()
    onHintChanged: { if (hovered) updateHint(); }
    background: Rectangle {
        radius: Theme.controlRadius
        color: root.emphasized ? Theme.accent : root.down ? Theme.hover : root.hovered ? Theme.raised : "transparent"
        border.width: root.visualFocus ? 2 : 0
        border.color: Theme.accent
        opacity: root.enabled ? 1 : 0.45
    }
    contentItem: Text {
        id: label
        text: root.busy ? "…" : root.text
        font.family: root.font.family
        font.pixelSize: root.font.pixelSize
        font.weight: root.emphasized ? Font.DemiBold : Font.Normal
        color: root.emphasized ? Theme.accentText : root.enabled ? root.foreground : Theme.muted
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    HoverHandler { cursorShape: root.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor }
}
