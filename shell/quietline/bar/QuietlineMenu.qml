import QtQuick
import Quickshell
import ".."
import "../controls"

// Меню значка Quietline: «О системе», «Настройки», сон, перезагрузка, выключение,
// блокировка и выход. Действия с многоточием просят подтверждение (`sessionRequested`).
// При открытии фокус получает само меню, строка не подсвечивается; стрелка вниз выбирает первую
// строку, вверх — последнюю, дальше стрелки переходят между строками.
Column {
    id: root
    required property var services
    signal done()
    signal sessionRequested(string action)
    spacing: 0
    function takeFocus() { root.forceActiveFocus(); }
    Keys.onDownPressed: about.forceActiveFocus(Qt.TabFocusReason)
    Keys.onUpPressed: logout.forceActiveFocus(Qt.TabFocusReason)

    component Row_: ShellMenuItem {
        width: root.width
        Keys.onDownPressed: nextItemInFocusChain(true).forceActiveFocus(Qt.TabFocusReason)
        Keys.onUpPressed: nextItemInFocusChain(false).forceActiveFocus(Qt.TabFocusReason)
    }
    component Separator: Item {
        width: root.width; height: 11
        Rectangle { anchors.centerIn: parent; width: parent.width - 20; height: 1; color: Theme.hairline }
    }

    Row_ { id: about; symbol: "info"; text: Lang.s.menuAbout; onTriggered: { root.done(); root.services.settings.open("about"); } }
    Row_ { symbol: "settings"; text: Lang.s.menuSettings; shortcut: "Super+I"; onTriggered: { root.done(); root.services.settings.open(""); } }
    Separator {}
    Row_ { symbol: "bedtime"; text: Lang.s.menuSleep; onTriggered: { root.done(); Quickshell.execDetached(["systemctl", "suspend"]); } }
    Row_ { symbol: "restart_alt"; text: Lang.s.menuReboot; onTriggered: { root.done(); root.sessionRequested("reboot"); } }
    Row_ { symbol: "power_settings_new"; text: Lang.s.menuPoweroff; onTriggered: { root.done(); root.sessionRequested("poweroff"); } }
    Separator {}
    Row_ { symbol: "lock"; text: Lang.s.menuLock; shortcut: "Super+L"; onTriggered: { root.done(); root.services.session.lock(); } }
    Row_ { id: logout; symbol: "logout"; text: Lang.s.menuLogout; onTriggered: { root.done(); root.sessionRequested("logout"); } }
}
