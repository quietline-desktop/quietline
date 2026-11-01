import QtQuick
import QtQuick.Controls
import "../controls"
import ".."

// Толстый ползунок 24 px: светлая заливка до значения с кружком на конце, значок `symbol`
// внутри у левого края; клавиши со стрелками. Доступное имя — `label` и значение в процентах.
Slider {
    id: root
    property string label: ""
    property string symbol: ""
    // Значок внутри ползунка нажимается (например, выключает звук): сигнал `symbolClicked`.
    property bool symbolClickable: false
    signal symbolClicked()
    focusPolicy: Qt.StrongFocus
    stepSize: 0.01
    hoverEnabled: true
    Accessible.name: label + " " + Math.round(value / to * 100) + "%"
    implicitHeight: 24
    padding: 0
    background: Rectangle {
        x: root.leftPadding; y: root.topPadding + root.availableHeight / 2 - height / 2
        width: root.availableWidth; height: 24; radius: 12
        color: Qt.rgba(1, 1, 1, 0.12)
        border.width: root.visualFocus ? 2 : 0
        border.color: Theme.accent
        Rectangle {
            readonly property real knob: 24
            width: Math.max(knob, knob + root.visualPosition * (parent.width - knob))
            height: parent.height; radius: 12
            color: "#eef0f4"
        }
        Icon {
            visible: root.symbol.length > 0
            x: 6; anchors.verticalCenter: parent.verticalCenter
            name: root.symbol
            filled: true
            size: 16
            color: "#3a3a40"
            MouseArea {
                anchors.fill: parent; anchors.margins: -4
                enabled: root.symbolClickable
                cursorShape: Qt.PointingHandCursor
                onClicked: root.symbolClicked()
            }
        }
    }
    handle: Rectangle {
        x: root.leftPadding + 2 + root.visualPosition * (root.availableWidth - 24)
        y: root.topPadding + root.availableHeight / 2 - height / 2
        width: 20; height: 20; radius: 10
        color: "#ffffff"
        border.width: 1; border.color: Qt.rgba(0, 0, 0, 0.12)
    }
}
