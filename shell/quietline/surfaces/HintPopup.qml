import QtQuick
import Quickshell
import ".."

// Одна поверхность подсказок на окно: кнопки просят своё окно показать её, поэтому
// тонкая панель или док не обрезают текст и у кнопок нет собственных всплывающих окон.
PopupWindow {
    id: root
    property Item target: null
    property string hint: ""
    property bool below: true
    function show(item, text, showBelow) {
        if (target !== item) {
            visible = false;
            target = item;
        }
        hint = text;
        below = showBelow;
        delay.restart();
    }
    function hide(item) {
        if (item && target !== item) return;
        delay.stop();
        visible = false;
        target = null;
    }
    Timer {
        id: delay
        interval: 650
        onTriggered: {
            if (!root.target || !root.target.visible) return;
            root.anchor.item = root.target;
            root.anchor.updateAnchor();
            root.visible = true;
        }
    }
    anchor.edges: below ? Edges.Bottom : Edges.Top
    anchor.gravity: below ? Edges.Bottom : Edges.Top
    anchor.margins.top: below ? 0 : -6
    anchor.margins.bottom: below ? -6 : 0
    implicitWidth: label.width + 20
    implicitHeight: label.implicitHeight + 10
    color: "transparent"
    Rectangle {
        anchors.fill: parent
        radius: 7
        color: Theme.tooltipSurface
        border.width: 1; border.color: Theme.border
        Text {
            renderType: Text.CurveRendering
            id: label
            x: 10; y: 5
            width: Math.min(implicitWidth, 320)
            text: root.hint
            color: Theme.text
            font.family: Theme.sans; font.pixelSize: Theme.smallFontSize; font.weight: Font.Medium
            wrapMode: Text.Wrap
        }
    }
}
