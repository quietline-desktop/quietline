import QtQuick
import QtQuick.Layouts
import Quickshell
import ".."

// Дата и крупное время экрана блокировки и экрана входа, в формате языка оболочки.
ColumnLayout {
    spacing: 0
    SystemClock { id: clock; precision: SystemClock.Minutes }
    Text {
        renderType: Theme.textRenderType(QsWindow.window, Screen.name)
        Layout.alignment: Qt.AlignHCenter
        text: { var day = Lang.longDate(clock.date); return day.charAt(0).toUpperCase() + day.slice(1); }
        color: Qt.rgba(1, 1, 1, 0.88)
        font.family: Theme.sans; font.pixelSize: 20; font.weight: Font.DemiBold
    }
    Text {
        renderType: Theme.textRenderType(QsWindow.window, Screen.name)
        Layout.alignment: Qt.AlignHCenter
        text: Lang.time(clock.date)
        color: Qt.rgba(1, 1, 1, 0.92)
        font.family: Theme.sans; font.pixelSize: 112; font.weight: Font.DemiBold
        font.letterSpacing: -3
        font.features: { "tnum": 1 }
    }
}
