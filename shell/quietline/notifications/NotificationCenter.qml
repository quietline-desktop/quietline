import QtQuick
import QtQuick.Layouts
import Quickshell
import ".."
import "../controls"
import "../inputs"
import "../logic/Models.js" as Models

// Центр уведомлений во всплывающем окне панели: «Не беспокоить», история сеанса новыми сверху,
// действия уведомлений, закрытие по одному и всех сразу. Нажатие на строку выполняет действие
// по умолчанию; не-`resident` уведомление после действия закрывает сам сервер.
ColumnLayout {
    id: root
    required property var service
    spacing: 10

    SystemClock { id: clock; precision: SystemClock.Minutes }
    function ageText(received) {
        var age = Models.notificationAge(received, clock.date.getTime());
        var when = new Date(received);
        if (age.kind === "now") return Lang.s.notificationsNow;
        if (age.kind === "minutes") return Lang.f(Lang.s.notificationsMinutes, age.minutes);
        if (age.kind === "today") return Lang.time(when);
        return Lang.shortDate(when) + " " + Lang.time(when);
    }

    RowLayout {
        Layout.fillWidth: true
        Text {
            renderType: Text.CurveRendering
            Layout.fillWidth: true
            text: Lang.s.notificationsTitle
            color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.titleFontSize; font.bold: true
        }
        ShellSwitch {
            text: Lang.s.notificationsDnd
            checked: root.service.dnd
            onToggled: root.service.setDnd(checked)
        }
    }
    Text {
        renderType: Text.CurveRendering
        visible: root.service.history.length === 0
        text: Lang.s.notificationsEmpty
        color: Theme.muted; font.family: Theme.sans; font.pixelSize: Theme.fontSize
    }
    Repeater {
        model: root.service.history
        delegate: Rectangle {
            id: row
            required property var modelData
            readonly property var notification: modelData.notification
            readonly property var defaultAction: notification.actions.find(action => action.identifier === "default") || null
            Layout.fillWidth: true
            implicitHeight: body.implicitHeight + 20
            radius: Theme.controlRadius
            color: hover.hovered && defaultAction ? Theme.raised : Theme.background
            border.width: 1
            border.color: notification.urgency === 2 ? Theme.danger : Theme.border
            HoverHandler { id: hover }
            TapHandler { onTapped: { if (row.defaultAction) row.defaultAction.invoke(); } }
            ColumnLayout {
                id: body
                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 10 }
                spacing: 3
                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        renderType: Text.CurveRendering
                        Layout.fillWidth: true
                        text: (row.notification.appName || Lang.s.notificationDefaultApp) + " · " + root.ageText(row.modelData.received)
                        color: Theme.muted; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
                        elide: Text.ElideRight; textFormat: Text.PlainText
                    }
                    ShellButton { text: "×"; hint: Lang.s.notificationDismiss; implicitHeight: 22; onClicked: row.notification.dismiss() }
                }
                Text {
                    renderType: Text.CurveRendering
                    Layout.fillWidth: true
                    visible: text.length > 0
                    text: row.notification.summary
                    color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.fontSize; font.weight: Font.DemiBold
                    wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight; textFormat: Text.PlainText
                }
                Text {
                    renderType: Text.CurveRendering
                    Layout.fillWidth: true
                    visible: text.length > 0
                    text: row.notification.body
                    color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
                    wrapMode: Text.Wrap; maximumLineCount: 4; elide: Text.ElideRight; textFormat: Text.PlainText
                }
                Flow {
                    Layout.fillWidth: true
                    visible: actions.count > 0
                    spacing: 6
                    Repeater {
                        id: actions
                        model: row.notification.actions.filter(action => action.identifier !== "default")
                        delegate: ShellButton { required property var modelData; text: modelData.text; onClicked: modelData.invoke() }
                    }
                }
            }
        }
    }
    ShellButton {
        visible: root.service.history.length > 0
        Layout.alignment: Qt.AlignRight
        text: Lang.s.notificationsClearAll
        onClicked: root.service.clearAll()
    }
}
