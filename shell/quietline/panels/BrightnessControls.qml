import QtQuick
import QtQuick.Layouts
import ".."
import "../inputs"

// Ползунок яркости встроенного экрана или сообщение, что яркость не управляется.
RowLayout {
    id: root
    required property var brightness
    Text {
        renderType: Text.CurveRendering
        visible: !root.brightness.supported
        Layout.fillWidth: true
        text: Lang.s.brightnessUnavailable
        color: Theme.text2; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
    }
    ShellSlider {
        visible: root.brightness.supported
        Layout.fillWidth: true
        label: Lang.s.brightnessLabel
        symbol: "light_mode"
        from: 1; to: 100; stepSize: 1
        value: root.brightness.percent
        onMoved: root.brightness.set(value)
    }
}
