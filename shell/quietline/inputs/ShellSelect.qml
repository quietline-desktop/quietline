import QtQuick
import QtQuick.Controls
import Quickshell
import "../controls"
import ".."

// Выпадающий список: поле 26 px с подписью выбранного и стрелкой; щелчок, Enter или Space
// открывают список под полем — строки 26 px, галочка у выбранной, прокрутка длинного списка,
// ↑ ↓ Enter Esc. `model` — [{label}], `currentIndex` — выбранная строка (−1 — `placeholder`);
// выбор — сигнал `activated(index)`, значение меняет владелец.
Rectangle {
    id: root
    property var model: []
    property int currentIndex: -1
    property string placeholder: ""
    property string label: ""
    property real minimumWidth: 150
    signal activated(int index)
    readonly property string currentText: currentIndex >= 0 && currentIndex < model.length ? model[currentIndex].label : placeholder
    implicitWidth: Math.max(minimumWidth, valueText.implicitWidth + 44)
    implicitHeight: 26
    radius: Theme.radiusControl
    color: area.pressed || popup.opened ? Theme.fillStrong : area.containsMouse ? Theme.fill2 : Theme.fill
    border.width: activeFocus ? 2 : 0
    border.color: Theme.accent
    opacity: enabled ? 1 : 0.6
    activeFocusOnTab: true
    Accessible.role: Accessible.ComboBox
    Accessible.name: label
    Accessible.description: currentText
    Keys.onReturnPressed: popup.open()
    Keys.onSpacePressed: popup.open()
    Keys.onDownPressed: popup.open()
    // Скрытое поле (другая страница, свёрнутая строка) закрывает свой список.
    onVisibleChanged: { if (!visible) popup.close(); }
    Behavior on color { ColorAnimation { duration: Theme.fastDuration } }

    Text {
        id: valueText
        renderType: Theme.textRenderType(QsWindow.window)
        anchors { left: parent.left; leftMargin: 10; right: arrow.left; rightMargin: 6; verticalCenter: parent.verticalCenter }
        text: root.currentText
        color: root.currentIndex >= 0 ? Theme.text : Theme.text3
        font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
        elide: Text.ElideRight
    }
    Icon {
        id: arrow
        anchors { right: parent.right; rightMargin: 6; verticalCenter: parent.verticalCenter }
        name: "unfold_more"
        size: 16
        color: Theme.text2
    }
    MouseArea {
        id: area
        anchors.fill: parent
        enabled: root.enabled
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: { root.forceActiveFocus(); popup.open(); }
    }

    Popup {
        id: popup
        y: root.height + 4
        width: Math.max(root.width, 180)
        height: Math.min(list.contentHeight + 10, 300)
        margins: 8
        padding: 5
        focus: true
        onOpened: {
            list.currentIndex = Math.max(0, root.currentIndex);
            list.positionViewAtIndex(list.currentIndex, ListView.Center);
            list.forceActiveFocus();
        }
        onClosed: root.forceActiveFocus()
        background: Rectangle {
            radius: Theme.radiusPopup
            color: Theme.windowSurface
            border.width: 1; border.color: Theme.border
        }
        contentItem: ListView {
            id: list
            clip: true
            model: root.model
            boundsBehavior: Flickable.StopAtBounds
            keyNavigationEnabled: true
            ScrollBar.vertical: ShellScrollBar {}
            Keys.onReturnPressed: { root.activated(currentIndex); popup.close(); }
            Keys.onEnterPressed: { root.activated(currentIndex); popup.close(); }
            Keys.onEscapePressed: popup.close()
            delegate: Rectangle {
                id: option
                required property var modelData
                required property int index
                readonly property bool lit: index === list.currentIndex
                width: list.width
                height: Theme.menuRowHeight
                radius: Theme.radiusSmall
                color: lit ? Theme.accent : "transparent"
                Icon {
                    id: check
                    anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                    name: option.index === root.currentIndex ? "check" : ""
                    size: 16
                    color: option.lit ? Theme.accentForeground : Theme.accent
                }
                Text {
                    renderType: Theme.textRenderType(QsWindow.window)
                    anchors { left: check.right; leftMargin: 6; right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter }
                    text: option.modelData.label
                    color: option.lit ? Theme.accentForeground : Theme.text
                    font.family: Theme.sans; font.pixelSize: Theme.fontSize
                    elide: Text.ElideRight
                }
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onEntered: list.currentIndex = option.index
                    onClicked: { root.activated(option.index); popup.close(); }
                }
            }
        }
    }
}
