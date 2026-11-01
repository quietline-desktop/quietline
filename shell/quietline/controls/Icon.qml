import QtQuick
import ".."

// Значок Material Symbols Rounded по имени лигатуры (`wifi`, `bluetooth`, `close`…):
// `filled` — залитый вариант, `weight` — толщина линии.
Text {
    id: root
    property string name: ""
    property bool filled: false
    property int weight: 400
    property real size: Theme.iconSize
    text: name
    renderType: Text.CurveRendering
    color: Theme.text
    font.family: Theme.symbols
    font.pixelSize: size
    font.variableAxes: ({ "FILL": filled ? 1 : 0, "wght": weight, "GRAD": -25, "opsz": Math.max(20, Math.min(48, size)) })
    horizontalAlignment: Text.AlignHCenter
    verticalAlignment: Text.AlignVCenter
    Accessible.ignored: true
}
