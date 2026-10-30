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
    // Срок карточки вышел: карточка скрывается, уведомление остаётся в истории (`transient` закрывается).
    function popupTimedOut(notification) { hidePopup(notification, false); }
    // Карточка скрыта по сроку или пользователем (`seen` — он её видел: уведомление прочитано).
    function hidePopup(notification, seen) {
        endCard(notification, seen);
        changed();
    }
    // Убрать карточку без пересчёта; `transient` без карточки закрывается.
    function endCard(notification, seen) {
        var info = meta[notification.id];
        if (!info) return;
        info.popup = false;
        if (seen) info.read = true;
        if (Models.transientExpires(notification.transient, false)) notification.expire();
    }
    function setDnd(on) {
        dnd = on;
        if (on) notifications.slice().forEach(item => { if (item.urgency !== NotificationUrgency.Critical) endCard(item, false); });
        changed();
    }
    // `centerOpen` задаёт shell.qml: открыт ли центр на какой-либо панели. Открытый центр
    // показывает всё сам: уведомления прочитаны, карточки не нужны.
    onCenterOpenChanged: {
        if (centerOpen) notifications.slice().forEach(item => endCard(item, true));
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
            var popup = Models.popupAllowed(notification.urgency, root.dnd, root.centerOpen);
            root.meta[notification.id] = {received: Date.now(), read: root.centerOpen, popup: popup};
            if (Models.transientExpires(notification.transient, popup)) { notification.expire(); return; }
            var kept = server.trackedNotifications.values.filter(item => !item.transient);
            kept.slice(0, Models.notificationsToDrop(kept.length)).forEach(item => item.dismiss());
            root.changed();
        }
    }
}
