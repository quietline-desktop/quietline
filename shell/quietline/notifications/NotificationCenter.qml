import QtQuick
import QtQuick.Layouts
import Quickshell
import ".."
import "../controls"
import "../logic/Models.js" as Models

// Центр уведомлений (часы по центру панели, `Super+N`): слева уведомления — «Не беспокоить»,
// история сеанса новыми сверху, справа календарь месяца. Уведомления одного приложения собраны
// в стопку: видна самая новая карточка, «ещё N» раскрывает остальные. Нажатие на карточку выполняет действие по
// умолчанию; не-`resident` уведомление после действия закрывает сам сервер.
RowLayout {
    id: root
    required property var service
    // Раскрытые стопки: имя приложения → true.
    property var expanded: ({})
    readonly property var groups: Models.notificationGroups(service.history, entry => entry.notification.appName || "")
    spacing: 14

    function reset() { expanded = ({}); calendar.reset(); }
    SystemClock { id: clock; precision: SystemClock.Minutes }
    function ageText(received) {
        var age = Models.notificationAge(received, clock.date.getTime());
        var when = new Date(received);
        if (age.kind === "now") return Lang.s.notificationsNow;
        if (age.kind === "minutes") return Lang.f(Lang.s.notificationsMinutes, age.minutes);
        if (age.kind === "today") return Lang.time(when);
        return Lang.shortDate(when) + " " + Lang.time(when);
    }
    function toggleGroup(key) {
        var next = Object.assign({}, expanded);
        next[key] = !next[key];
        expanded = next;
    }

    // Уведомления: заголовок с «Не беспокоить», история, «Очистить всё».
    ColumnLayout {
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignTop
        spacing: 10
        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 4
            Text {
                renderType: Theme.textRenderType(QsWindow.window)
                Layout.fillWidth: true
                text: Lang.s.notificationsTitle
                color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.titleFontSize; font.weight: Font.Bold
            }
            ShellButton {
                implicitHeight: 24
                radius: 12
                symbol: "do_not_disturb_on"
                symbolSize: 15
                symbolFilled: root.service.dnd
                text: Lang.s.notificationsDnd
                font.pixelSize: Theme.smallFontSize
                emphasized: root.service.dnd
                selected: true
                onClicked: root.service.setDnd(!root.service.dnd)
            }
        }
        Text {
            renderType: Theme.textRenderType(QsWindow.window)
            visible: root.service.history.length === 0
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 6; Layout.bottomMargin: 6
            text: Lang.s.notificationsEmpty
            color: Theme.text2; font.family: Theme.sans; font.pixelSize: Theme.fontSize
        }
        Repeater {
            model: root.groups
            delegate: ColumnLayout {
                id: group
                required property var modelData
                readonly property bool open: !!root.expanded[modelData.key]
                readonly property var shownEntries: open ? modelData.entries : modelData.entries.slice(0, 1)
                Layout.fillWidth: true
                // Крестик карточки выступает за её левый верхний угол на 6 px: место под него.
                Layout.leftMargin: 6
                spacing: 6
                Repeater {
                    model: group.shownEntries
                    delegate: Item {
                        id: slot
                        required property var modelData
                        required property int index
                        readonly property bool stacked: !group.open && group.modelData.entries.length > 1
                        Layout.fillWidth: true
                        implicitHeight: card.implicitHeight + (stacked ? 6 : 0)
                        // Край следующей карточки под верхней — признак стопки. Карточка
                        // полупрозрачная, поэтому край виден только ниже неё: полоса 6 px
                        // обрезает скруглённый прямоугольник.
                        Item {
                            visible: slot.stacked
                            x: 10; width: parent.width - 20
                            y: card.implicitHeight; height: 6
                            clip: true
                            Rectangle {
                                width: parent.width
                                y: -10; height: 16
                                radius: Theme.radiusCard
                                color: Theme.stackEdge
                            }
                        }
                        NotificationCard {
                            id: card
                            width: parent.width
                            notification: slot.modelData.notification
                            timeText: root.ageText(slot.modelData.received)
                            surfaceColor: Theme.fill
                            border.color: notification.urgency === 2 ? Theme.danger : Theme.groupBorder
                            onCloseRequested: slot.modelData.notification.dismiss()
                        }
                    }
                }
                ShellButton {
                    visible: group.modelData.entries.length > 1
                    Layout.alignment: Qt.AlignRight
                    implicitHeight: 22
                    text: group.open ? Lang.s.notificationsCollapse : Lang.f(Lang.s.notificationsMore, group.modelData.entries.length - 1)
                    font.pixelSize: Theme.captionFontSize
                    foreground: Theme.text2
                    onClicked: root.toggleGroup(group.modelData.key)
                }
            }
        }
        ShellButton {
            visible: root.service.history.length > 0
            Layout.alignment: Qt.AlignHCenter
            implicitHeight: 26
            text: Lang.s.notificationsClearAll
            foreground: Theme.text2
            onClicked: root.service.clearAll()
        }
    }
    MonthCalendar {
        id: calendar
        Layout.preferredWidth: 264
        Layout.alignment: Qt.AlignTop
    }
}
