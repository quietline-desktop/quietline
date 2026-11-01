import QtQuick
import Quickshell
import ".."
import "../controls"

// Плитка пункта управления: кружок со значком (синий, когда `checked`), название и
// состояние; щелчок — `toggled()`, стрелка справа (если `expandable`) — `expandRequested()`.
// `small` — плитка в одну строку без состояния.
Rectangle {
    id: root
    property string symbol: ""
    property string title: ""
    property string subtitle: ""
    property bool checked: false
    property bool expandable: false
    property bool small: false
    property string hint: ""
    signal toggled()
    signal expandRequested()
    implicitHeight: small ? 40 : 52
    radius: Theme.radiusModule
    color: tileArea.containsMouse ? Theme.fill2 : Theme.fill
    border.width: activeFocus ? 2 : 0
    border.color: Theme.accent
    activeFocusOnTab: true
    Accessible.role: Accessible.CheckBox
    Accessible.name: title
    Accessible.checked: checked
    Keys.onSpacePressed: toggled()
    Keys.onReturnPressed: toggled()
    Behavior on color { ColorAnimation { duration: Theme.fastDuration } }
    MouseArea {
        id: tileArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.toggled()
    }
    Rectangle {
        id: badge
        x: 10; anchors.verticalCenter: parent.verticalCenter
        width: root.small ? 26 : 30; height: width; radius: width / 2
        color: root.checked ? Theme.accent : Theme.fill2
        Behavior on color { ColorAnimation { duration: Theme.fastDuration } }
        Icon { anchors.centerIn: parent; name: root.symbol; filled: true; size: root.small ? 15 : 17; color: Theme.text }
    }
    Column {
        anchors.left: badge.right; anchors.leftMargin: 9
        anchors.right: chevron.visible ? chevron.left : parent.right; anchors.rightMargin: 6
        anchors.verticalCenter: parent.verticalCenter
        spacing: 1
        Text {
            renderType: Text.CurveRendering
            width: parent.width
            text: root.title
            color: Theme.text
            font.family: Theme.sans; font.pixelSize: root.small ? 12 : Theme.fontSize; font.weight: root.small ? Font.Medium : Font.DemiBold
            elide: Text.ElideRight
        }
        Text {
            renderType: Text.CurveRendering
            visible: !root.small && root.subtitle.length > 0
            width: parent.width
            text: root.subtitle
            color: Theme.text2
            font.family: Theme.sans; font.pixelSize: 11
            elide: Text.ElideRight
        }
    }
    // Стрелка разворачивает подробности; у неё своя зона нажатия.
    Item {
        id: chevron
        visible: root.expandable
        anchors.right: parent.right; anchors.rightMargin: 2
        anchors.verticalCenter: parent.verticalCenter
        width: 28; height: parent.height
        Rectangle {
            anchors.centerIn: parent
            width: 22; height: 22; radius: 11
            color: chevronArea.containsMouse ? Theme.fillHover : "transparent"
        }
        Icon { anchors.centerIn: parent; name: "chevron_right"; size: 18; color: Theme.text3 }
        MouseArea {
            id: chevronArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.expandRequested()
            onContainsMouseChanged: {
                var host = QsWindow.window;
                if (!host || !host.hints) return;
                if (containsMouse && root.hint) host.hints.show(chevron, root.hint, true);
                else host.hints.hide(chevron);
            }
        }
    }
}
