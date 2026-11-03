import QtQuick
import QtQuick.Layouts
import Quickshell
import "../.."

// Пояснение под группами страницы «Настроек»: мелкий вторичный текст во всю ширину колонки.
Text {
    renderType: Theme.textRenderType(QsWindow.window)
    Layout.fillWidth: true
    Layout.leftMargin: 4
    color: Theme.text2; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
    wrapMode: Text.Wrap
}
