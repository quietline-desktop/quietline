import QtQuick
import Quickshell
import QtQuick.Layouts
import ".."
import "../inputs"

// Ползунок яркости встроенного экрана с процентом справа или сообщение, что яркость не управляется.
RowLayout {
    id: root
    required property var brightness
    spacing: 8
    Text {
        renderType: Theme.textRenderType(QsWindow.window)
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
    Text {
        renderType: Theme.textRenderType(QsWindow.window)
        visible: root.brightness.supported
        Layout.preferredWidth: 40
        horizontalAlignment: Text.AlignRight
        text: Math.round(root.brightness.percent) + "%"
        color: Theme.text2; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
        font.features: ({ "tnum": 1 })
    }
}
