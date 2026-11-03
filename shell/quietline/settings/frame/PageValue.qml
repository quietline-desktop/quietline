import QtQuick
import Quickshell
import "../.."

// Значение справа в строке «Настроек»: вторичный текст, обрезается многоточием по ширине,
// которую оставляет строка (`maxChildWidth` её контейнера).
Text {
    renderType: Theme.textRenderType(QsWindow.window)
    width: Math.min(implicitWidth, parent && parent.maxChildWidth !== undefined ? parent.maxChildWidth : 300)
    color: Theme.text2; font.family: Theme.sans; font.pixelSize: Theme.fontSize
    horizontalAlignment: Text.AlignRight
    elide: Text.ElideRight
}
