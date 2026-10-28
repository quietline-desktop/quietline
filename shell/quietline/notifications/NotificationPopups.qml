import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import ".."
import "../controls"
import "../logic/Models.js" as Models

// Всплывающие уведомления справа под панелью на мониторе с фокусом. Обычные исчезают по
// `Models.notificationTimeout`, критические — только по кнопке. Текст показывается без разметки.
PanelWindow {
    id: root
    required property var service
    screen: Quickshell.screens.find(screen => Hyprland.focusedMonitor && screen.name === Hyprland.focusedMonitor.name) || Quickshell.screens[0] || null
    visible: service.visibleNotifications.length > 0
    anchors { top: true; right: true }
    margins.top: Theme.outerMargin + Theme.barHeight + 8
    margins.right: 12
    exclusionMode: ExclusionMode.Ignore
    exclusiveZone: 0
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    implicitWidth: 340
    implicitHeight: Math.max(1, column.implicitHeight)
    color: "transparent"

    // Сроки идут у всех отслеживаемых уведомлений, в том числе не поместившихся на экран.
    Repeater {
        model: root.service.model
        delegate: Item {
            id: holder
            required property var modelData
            Timer {
                interval: Models.notificationTimeout(holder.modelData.expireTimeout, holder.modelData.urgency)
                running: interval > 0
                onTriggered: holder.modelData.expire()
            }
        }
    }

    ColumnLayout {
        id: column
        width: parent.width
        spacing: 8
        Repeater {
            model: root.service.visibleNotifications
            delegate: Rectangle {
                id: card
                required property var modelData
                readonly property var defaultAction: modelData.actions.find(action => action.identifier === "default") || null
                Layout.fillWidth: true
                implicitHeight: body.implicitHeight + 24
                radius: Theme.panelRadius
                color: Theme.surface
                border.width: 1
                border.color: modelData.urgency === 2 ? Theme.danger : Theme.border
                TapHandler {
                    onTapped: { if (card.defaultAction) card.defaultAction.invoke(); else card.modelData.dismiss(); }
                }
                ColumnLayout {
                    id: body
                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: 12 }
                    spacing: 4
                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            Layout.fillWidth: true
                            text: card.modelData.appName || Lang.s.notificationDefaultApp
                            color: Theme.muted; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
                            elide: Text.ElideRight; textFormat: Text.PlainText
                        }
                        ShellButton { text: "×"; hint: Lang.s.notificationDismiss; implicitHeight: 22; onClicked: card.modelData.dismiss() }
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: text.length > 0
                        text: card.modelData.summary
                        color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.fontSize; font.weight: Font.DemiBold
                        wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight; textFormat: Text.PlainText
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: text.length > 0
                        text: card.modelData.body
                        color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
                        wrapMode: Text.Wrap; maximumLineCount: 4; elide: Text.ElideRight; textFormat: Text.PlainText
                    }
                    Flow {
                        Layout.fillWidth: true
                        visible: actionRepeater.count > 0
                        spacing: 6
                        Repeater {
                            id: actionRepeater
                            model: card.modelData.actions.filter(action => action.identifier !== "default")
                            delegate: ShellButton { required property var modelData; text: modelData.text; onClicked: modelData.invoke() }
                        }
                    }
                }
            }
        }
    }
}
