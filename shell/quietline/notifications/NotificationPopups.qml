import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import ".."
import "../logic/Models.js" as Models

// Всплывающие карточки уведомлений справа под панелью на мониторе с фокусом. Обычные
// скрываются по `Models.notificationTimeout`, критические — только по кнопке; скрытая карточка
// оставляет уведомление в истории. Текст показывается без разметки. Слева, сверху и снизу от
// карточек — поле под тень, щелчки в нём проходят насквозь.
PanelWindow {
    id: root
    required property var service
    readonly property int shadowMargin: 20
    screen: Quickshell.screens.find(screen => Hyprland.focusedMonitor && screen.name === Hyprland.focusedMonitor.name) || Quickshell.screens[0] || null
    visible: service.popups.length > 0
    anchors { top: true; right: true }
    margins.top: Theme.barHeight + Theme.popupGap - shadowMargin
    margins.right: 0
    exclusionMode: ExclusionMode.Ignore
    exclusiveZone: 0
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "quietline-notifications"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    implicitWidth: 352 + shadowMargin + Theme.screenMargin
    implicitHeight: Math.max(1, column.implicitHeight + shadowMargin * 2)
    color: "transparent"
    mask: Region { item: column }

    // Сроки идут у всех видимых карточек, в том числе не поместившихся на экран.
    Repeater {
        model: root.service.model
        delegate: Item {
            id: holder
            required property var modelData
            Timer {
                interval: Models.notificationTimeout(holder.modelData.expireTimeout, holder.modelData.urgency)
                running: interval > 0 && root.service.isPopup(holder.modelData)
                onTriggered: root.service.popupTimedOut(holder.modelData)
            }
        }
    }

    ColumnLayout {
        id: column
        x: root.shadowMargin; y: root.shadowMargin
        width: 352
        spacing: 8
        Repeater {
            model: root.service.popups
            delegate: Item {
                id: slot
                required property var modelData
                Layout.fillWidth: true
                implicitHeight: card.implicitHeight
                RectangularShadow {
                    anchors.fill: card
                    radius: card.radius
                    blur: 30; offset.y: 10; spread: -4
                    color: Theme.shadow
                }
                NotificationCard {
                    id: card
                    width: parent.width
                    notification: slot.modelData
                    timeText: Lang.s.notificationsNow
                    closeHint: Lang.s.notificationHide
                    onCloseRequested: root.service.hidePopup(slot.modelData, true)
                    onActivated: { if (!defaultAction) root.service.hidePopup(slot.modelData, true); }
                }
            }
        }
    }
}
