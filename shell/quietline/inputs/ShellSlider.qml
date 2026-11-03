import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import "../controls"
import ".."

// Тонкий ползунок: дорожка 6 px, заливка до значения и белый кружок 14 px с тенью; значок
// `symbol` — слева от дорожки. Клавиши со стрелками, колесо мыши — 5 % диапазона за деление
// (сигнал `moved`, как при перетаскивании). Доступное имя — `label` и значение в процентах.
Slider {
    id: root
    property string label: ""
    property string symbol: ""
    // Значок слева нажимается (например, выключает звук): сигнал `symbolClicked`.
    property bool symbolClickable: false
    signal symbolClicked()
    readonly property real knobSize: 14
    focusPolicy: Qt.StrongFocus
    stepSize: 0.01
    hoverEnabled: true
    Accessible.name: label + " " + Math.round(value / to * 100) + "%"
    implicitHeight: 24
    padding: 0
    leftPadding: symbol.length > 0 ? 26 : 0
    WheelSteps {
        onStep: direction => {
            var steps = Math.max(1, Math.round((root.to - root.from) * 0.05 / root.stepSize));
            for (var i = 0; i < steps; i++) {
                if (direction < 0) root.increase(); else root.decrease();
            }
            root.moved();
        }
    }
    background: Item {
        Icon {
            visible: root.symbol.length > 0
            anchors.verticalCenter: parent.verticalCenter
            name: root.symbol
            filled: true
            size: 17
            color: Theme.text
            MouseArea {
                anchors.fill: parent; anchors.margins: -4
                enabled: root.symbolClickable
                cursorShape: Qt.PointingHandCursor
                onClicked: root.symbolClicked()
            }
        }
        Rectangle {
            x: root.leftPadding; y: root.topPadding + Math.round((root.availableHeight - height) / 2)
            width: root.availableWidth; height: 6; radius: 3
            color: Theme.track
            Rectangle {
                width: Math.max(parent.height, root.knobSize / 2 + root.visualPosition * (parent.width - root.knobSize))
                height: parent.height; radius: parent.radius
                color: Theme.sliderFill
            }
        }
    }
    handle: Rectangle {
        x: root.leftPadding + Math.round(root.visualPosition * (root.availableWidth - width))
        y: root.topPadding + Math.round((root.availableHeight - height) / 2)
        width: root.knobSize; height: root.knobSize; radius: root.knobSize / 2
        color: Theme.knob
        scale: root.pressed ? 1.15 : 1
        border.width: root.visualFocus ? 2 : 0
        border.color: Theme.accent
        layer.enabled: true
        layer.effect: MultiEffect { shadowEnabled: true; shadowColor: Theme.shadow; shadowBlur: 0.4; shadowVerticalOffset: 1 }
        Behavior on scale { NumberAnimation { duration: Theme.fastDuration } }
    }
}
