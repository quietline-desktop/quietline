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
        color: Theme.muted; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
    }
    Text {
        renderType: Text.CurveRendering
        visible: root.brightness.supported
        text: ""
        font.family: Theme.icons; font.pixelSize: Theme.iconFontSize
        color: Theme.muted
        Layout.preferredWidth: 28
        horizontalAlignment: Text.AlignHCenter
    }
    ShellSlider {
        visible: root.brightness.supported
        Layout.fillWidth: true
        label: Lang.s.brightnessLabel
        from: 1; to: 100; stepSize: 1
        value: root.brightness.percent
        onMoved: root.brightness.set(value)
    }
}
