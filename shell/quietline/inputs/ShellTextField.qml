import QtQuick
import Quickshell
import QtQuick.Controls
import ".."

// Текстовое поле формы на подложке `fill`: рамка акцента при фокусе, доступное имя `label`.
TextField {
    id: root
    property string label: placeholderText
    font.family: Theme.sans
    font.pixelSize: Theme.fontSize
    color: Theme.text
    placeholderTextColor: Theme.text3
    selectionColor: Theme.accent
    selectedTextColor: Theme.accentForeground
    selectByMouse: true
    renderType: Theme.textRenderType(QsWindow.window)
    implicitHeight: 30
    leftPadding: 10; rightPadding: 10
    Accessible.name: label
    background: Rectangle {
        color: Theme.fill
        radius: Theme.radiusControl
        border.width: root.activeFocus ? 2 : 1
        border.color: root.activeFocus ? Theme.focusRing : Theme.hairline
    }
}
