import QtQuick
import Quickshell
import Quickshell.Services.Notifications
import "../logic/Models.js" as Models

// Сервер уведомлений оболочки (org.freedesktop.Notifications). Все пришедшие уведомления
// отслеживаются; `visibleNotifications` — новые первыми, не больше `Models.NOTIFICATION_LIMIT`.
Scope {
    id: root
    readonly property var notifications: server.trackedNotifications.values
    readonly property var visibleNotifications: notifications.slice().reverse().slice(0, Models.NOTIFICATION_LIMIT)

    NotificationServer {
        id: server
        keepOnReload: false
        actionsSupported: true
        onNotification: notification => { notification.tracked = true; }
    }
}
