import QtQuick
import Quickshell
import ".."

// Сегменты в одной подложке: `model` — [{symbol, label, hint}], `currentIndex` — выбранный.
// Выбранный сегмент — светлая подложка, которая переезжает между сегментами за `Theme.motionDuration`.
// Щелчок по сегменту — сигнал `activated(index)`; выбор меняет владелец.
Rectangle {
    id: root
    property var model: []
    property int currentIndex: -1
    property real segmentWidth: 26
    property real segmentHeight: 18
    property bool showLabels: false
    property bool reducedMotion: false
    property bool busy: false
    signal activated(int index)
    implicitWidth: row.implicitWidth + 4
    implicitHeight: segmentHeight + 4
    radius: Theme.radiusSmall
    color: Theme.fill
    opacity: enabled ? 1 : 0.6
    Rectangle {
        visible: root.currentIndex >= 0 && root.currentIndex < repeater.count
        readonly property Item target: repeater.count > 0 && root.currentIndex >= 0 ? repeater.itemAt(Math.min(root.currentIndex, repeater.count - 1)) : null
        x: target ? row.x + target.x : 2
        y: 2
        width: target ? target.width : 0
        height: root.segmentHeight
        radius: Theme.radiusSmall - 2
        color: Theme.fillStrong
        Behavior on x { NumberAnimation { duration: root.reducedMotion ? 0 : Theme.motionDuration; easing.type: Easing.OutCubic } }
        Behavior on width { NumberAnimation { duration: root.reducedMotion ? 0 : Theme.motionDuration; easing.type: Easing.OutCubic } }
    }
    Row {
        id: row
        x: 2; y: 2
        Repeater {
            id: repeater
            model: root.model
            delegate: Item {
                id: segment
                required property var modelData
                required property int index
                readonly property bool current: index === root.currentIndex
                width: root.showLabels ? Math.max(root.segmentWidth, segmentContent.implicitWidth + 16) : root.segmentWidth
                height: root.segmentHeight
                Accessible.role: Accessible.RadioButton
                Accessible.name: modelData.hint || modelData.label || ""
                Accessible.checked: current
                Row {
                    id: segmentContent
                    anchors.centerIn: parent
                    spacing: 6
                    Icon {
                        visible: !!segment.modelData.symbol
                        anchors.verticalCenter: parent.verticalCenter
                        name: segment.modelData.symbol || ""
                        size: 15
                        filled: segment.current
                        color: segment.current ? Theme.text : Theme.text2
                    }
                    Text {
                        renderType: Text.CurveRendering
                        visible: root.showLabels && !!segment.modelData.label
                        anchors.verticalCenter: parent.verticalCenter
                        text: segment.modelData.label || ""
                        color: segment.current ? Theme.text : Theme.text2
                        font.family: Theme.sans; font.pixelSize: Theme.smallFontSize; font.weight: Font.Medium
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    enabled: root.enabled && !root.busy
                    cursorShape: Qt.PointingHandCursor
                    hoverEnabled: true
                    onClicked: root.activated(segment.index)
                    // Подсказка — общим HintPopup окна, как у ShellButton.
                    onContainsMouseChanged: {
                        var host = QsWindow.window;
                        if (!host || !host.hints) return;
                        if (containsMouse && segment.modelData.hint) host.hints.show(segment, segment.modelData.hint, true);
                        else host.hints.hide(segment);
                    }
                }
            }
        }
    }
}
