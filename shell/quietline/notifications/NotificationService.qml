import QtQuick
import Quickshell
import Quickshell.Services.Notifications
import "../logic/Models.js" as Models

// Сервер уведомлений оболочки (org.freedesktop.Notifications) и история сеанса.
// История — сами отслеживаемые уведомления сервера: уведомление остаётся в ней, пока его не
// закрыли пользователь или приложение, поэтому его действия работают и после того, как
// карточка скрылась по сроку. `transient` в историю не попадает и по сроку закрывается.
// Сведения оболочки об уведомлении (время прихода, прочитано, видна ли карточка) — в `meta`
// по `id`; `revision` растёт при каждой их смене. В истории не больше
// `Models.NOTIFICATION_HISTORY_LIMIT`: при переполнении самое старое закрывается.
Scope {
    id: root
    property bool dnd: false
    property bool centerOpen: false
    property int revision: 0
    property var meta: ({})
    // Модель для сроков карточек: меняется по одному уведомлению, делегаты не пересоздаются.
    readonly property var model: server.trackedNotifications
    readonly property var notifications: server.trackedNotifications.values
    // `[{notification, received, read}]`, новые первыми.
    readonly property var history: {
        revision;
        return notifications.filter(item => !item.transient && !!meta[item.id]).reverse()
            .map(item => ({notification: item, received: meta[item.id].received, read: meta[item.id].read}));
    }
    readonly property var popups: {
        revision;
        return notifications.filter(item => !!meta[item.id] && meta[item.id].popup).reverse().slice(0, Models.NOTIFICATION_LIMIT);
    }
    readonly property int unread: history.filter(entry => !entry.read).length

    function isPopup(notification) { revision; return !!meta[notification.id] && meta[notification.id].popup; }
    function changed() { revision += 1; }
    // Срок карточки вышел: `transient` закрывается, остальные остаются в истории.
    function popupTimedOut(notification) {
        if (notification.transient) { notification.expire(); return; }
        hidePopup(notification);
    }
    // Карточка скрыта по сроку или пользователем (`seen` — он её видел: уведомление прочитано);
    // уведомление остаётся в истории.
    function hidePopup(notification, seen) {
        var info = meta[notification.id];
        if (!info) return;
        info.popup = false;
        if (seen) info.read = true;
        changed();
    }
    function setDnd(on) {
        dnd = on;
        if (on) notifications.forEach(item => { if (meta[item.id] && item.urgency !== NotificationUrgency.Critical) meta[item.id].popup = false; });
        changed();
    }
    // Открытый центр показывает всё сам: уведомления прочитаны, карточки не нужны.
    function setCenterOpen(open) {
        centerOpen = open;
        if (open) notifications.forEach(item => { if (meta[item.id]) { meta[item.id].read = true; meta[item.id].popup = false; } });
        changed();
    }
    function clearAll() { notifications.slice().forEach(item => item.dismiss()); }

    // Закрытые уведомления уходят и из сведений.
    onNotificationsChanged: {
        var alive = {};
        notifications.forEach(item => { alive[item.id] = true; });
        Object.keys(meta).forEach(id => { if (!alive[id]) delete meta[id]; });
        changed();
    }

    NotificationServer {
        id: server
        keepOnReload: false
        actionsSupported: true
        onNotification: notification => {
            notification.tracked = true;
            root.meta[notification.id] = {received: Date.now(), read: root.centerOpen,
                                          popup: Models.popupAllowed(notification.urgency, root.dnd, root.centerOpen)};
            var kept = server.trackedNotifications.values.filter(item => !item.transient);
            kept.slice(0, Models.notificationsToDrop(kept.length)).forEach(item => item.dismiss());
            root.changed();
        }
    }
}
