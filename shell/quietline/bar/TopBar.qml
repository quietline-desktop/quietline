import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import Quickshell.Services.SystemTray
import ".."
import "../controls"
import "../surfaces"
import "../panels"
import "../session"
import "../clipboard"
import "../search"
import "../notifications"
import "../logic/Models.js" as Models

// Верхняя панель экрана, 30 px вплотную к краю: слева меню Quietline, активное приложение и
// пространства; справа режим «Окна / Тайлы», трей, раскладка, сеть, Bluetooth, батарея,
// пункт управления и дата со временем (открывает центр уведомлений).
PanelWindow {
    id: root
    required property var engine
    required property var desktop
    required property var indicators
    // Общие системные сервисы оболочки (`shell.qml`): один экземпляр на все экраны.
    required property var services
    readonly property var network: services.network
    readonly property string monitorName: screen ? screen.name : ""
    readonly property var workspace: engine.ready ? Models.activeWorkspace(engine.state, monitorName) : null
    readonly property var monitor: engine.ready ? Models.monitorFor(engine.state, monitorName) : null
    readonly property bool applicationsOpen: popout.opened && popout.currentName === "applications"
    readonly property bool summaryOpen: popout.opened && popout.currentName === "quick"
    readonly property var hints: hintPopup
    // Узкий экран: сначала уходит трей, затем название приложения, затем дата.
    readonly property bool compact: width < 1000
    readonly property bool narrow: width < 820
    readonly property bool tiny: width < 640
    readonly property bool reducedMotion: indicators.reducedMotion
    readonly property string modeLabel: !engine.ready ? Lang.s.barNoConnection : workspace ? workspace.mode === "tiles" ? Lang.s.modeTiles : Lang.s.modeWindows : "—"
    readonly property var buttons: engine.ready ? Models.barWorkspaces(Models.workspaceItems(engine.state, monitorName, Lang.s)) : []
    readonly property var buttonsByKey: Models.keyed(buttons, Models.workspaceKey)
    readonly property string activeApp: Models.activeAppName(desktop.windows, monitorName, desktop.entries)
    readonly property string errorText: engine.message || desktop.errorMessage
    readonly property string message: errorText || desktop.notice
    anchors { top: true; left: true; right: true }
    function openApplications() { popout.open("applications"); }
    function openSummary() { popout.open("quick"); }
    function openClipboard() { popout.open("clipboard"); }
    function toggleApplications() { popout.toggle("applications"); }
    function toggleClipboard() { popout.toggle("clipboard"); }
    function toggleNotifications() { popout.toggle("notifications"); }
    // Открыт ли здесь центр уведомлений (shell.qml собирает это со всех панелей).
    readonly property bool notificationsOpen: popout.opened && popout.showingNotifications
    // Диалог подтверждения выхода, перезагрузки или выключения по центру экрана.
    function openSession(action) {
        popout.close();
        sessionContent.action = action;
        sessionDialog.open();
        Qt.callLater(function() { sessionContent.reset(); });
    }
    // Подтверждение принудительного завершения процесса окна `window`.
    function confirmKill(window) {
        popout.close();
        killContent.target = window;
        killDialog.open();
        Qt.callLater(function() { killContent.focusCancel(); });
    }
    implicitHeight: Theme.barHeight + (message.length > 0 ? 30 : 0)
    exclusiveZone: Theme.barHeight
    color: "transparent"
    focusable: true
    WlrLayershell.namespace: "quietline-bar"

    Rectangle {
        id: bar
        width: parent.width; height: Theme.barHeight
        color: Theme.barSurface
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.hairline }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 6; anchors.rightMargin: 6
            spacing: 2
            ShellButton {
                id: menuButton
                implicitHeight: Theme.barItemHeight; implicitWidth: 32
                hint: Lang.s.barMenuHint
                selected: popout.opened && popout.showingMenu
                onClicked: popout.toggle("menu")
                // Знак Quietline: кольцо с «хвостом».
                Rectangle {
                    anchors.centerIn: parent
                    width: 15; height: 15; radius: 7.5
                    color: "transparent"
                    border.width: 2; border.color: Theme.text
                    Rectangle {
                        x: 8; y: 10; width: 7; height: 2; radius: 1
                        color: Theme.text
                        rotation: 40
                    }
                }
            }
            Text {
                renderType: Text.CurveRendering
                visible: !root.narrow && root.activeApp.length > 0
                Layout.maximumWidth: Math.max(0, root.width * 0.22)
                leftPadding: 6; rightPadding: 6
                text: root.activeApp
                color: Theme.text
                font.family: Theme.sans; font.pixelSize: Theme.fontSize; font.weight: Font.Bold
                elide: Text.ElideRight
                Accessible.name: root.activeApp
            }
            Row {
                Layout.leftMargin: 4
                spacing: 2
                Repeater {
                    model: ScriptModel { values: root.buttons.map(Models.workspaceKey) }
                    delegate: ShellButton {
                        id: workspaceButton
                        required property string modelData
                        readonly property var item: root.buttonsByKey[modelData] || ({number: 0, monitor: "", label: "", migrated: false, active: false})
                        implicitHeight: 20
                        implicitWidth: Math.max(20, implicitContentWidth + 12)
                        text: item.migrated ? "↪" + item.number : String(item.number)
                        hint: Lang.f(Lang.s.barWorkspaceHint, item.number) + (item.migrated ? " · " + Models.monitorLabel(item.monitor) : "")
                        font.pixelSize: Theme.smallFontSize; font.weight: Font.DemiBold
                        foreground: item.active ? Theme.text : Theme.text2
                        selected: item.active
                        enabled: root.engine.ready && !root.engine.busy
                        // Перенесённое пространство открывается на мониторе этой панели:
                        // фокус переходит на её монитор до команды движку.
                        onClicked: {
                            if (item.migrated) root.desktop.focusMonitor(root.monitorName);
                            root.engine.switchWorkspace(item.number, item.monitor);
                        }
                    }
                }
            }
            Item { Layout.fillWidth: true; Layout.minimumWidth: 0 }
            // Режим активного пространства; меняется только после подтверждения движком.
            SegmentedControl {
                id: modeControl
                Layout.rightMargin: 6
                visible: root.engine.ready && !!root.workspace
                model: [{symbol: "filter_none", hint: Lang.f(Lang.s.barModeHint, Lang.s.modeWindows)},
                        {symbol: "view_week", hint: Lang.f(Lang.s.barModeHint, Lang.s.modeTiles)}]
                currentIndex: root.workspace && root.workspace.mode === "tiles" ? 1 : 0
                reducedMotion: root.reducedMotion
                enabled: root.engine.ready && !!root.monitor && !root.engine.busy
                busy: root.engine.busy && root.engine.pendingMonitor === (root.monitor ? root.monitor.key : "")
                Accessible.name: Lang.f(Lang.s.barModeHint, root.modeLabel)
                onActivated: index => {
                    if (index !== currentIndex) root.engine.toggle(root.monitor.key);
                }
            }
            ShellButton {
                visible: !root.engine.ready
                implicitHeight: Theme.barItemHeight
                text: Lang.s.barNoConnection
                hint: Lang.s.barEngineUnavailable
                foreground: Theme.text2
                onClicked: root.engine.retry()
            }
            Row {
                visible: !root.compact
                spacing: 0
                Repeater {
                    model: SystemTray.items
                    delegate: ShellButton {
                        required property var modelData
                        hint: modelData.tooltipTitle || modelData.title || modelData.id
                        implicitHeight: Theme.barItemHeight; implicitWidth: 28
                        function showMenu() {
                            var point = mapToItem(root.contentItem, 0, height);
                            modelData.display(root, point.x, point.y);
                        }
                        onClicked: {
                            if (modelData.onlyMenu) showMenu();
                            else modelData.activate();
                        }
                        // Значки трея обесцвечены: на панели они одного тона, детали сохраняются.
                        Image {
                            id: trayIcon
                            anchors.centerIn: parent
                            width: 16; height: 16
                            source: parent.modelData.icon
                            sourceSize.width: 32; sourceSize.height: 32
                            visible: false
                        }
                        MultiEffect {
                            anchors.fill: trayIcon
                            source: trayIcon
                            saturation: -1
                            brightness: 0.15
                            opacity: 0.9
                        }
                        TapHandler { acceptedButtons: Qt.RightButton; onTapped: parent.showMenu() }
                    }
                }
            }
            ShellButton {
                implicitHeight: Theme.barItemHeight
                hint: (root.desktop.keyboardLayoutName ? root.desktop.keyboardLayoutName + " · " : "") + Lang.f(Lang.s.barLayoutHint, Models.toggleLabel(Lang.toggle, Lang.s))
                Accessible.name: root.desktop.keyboardLayout
                onClicked: root.desktop.switchLayout()
                contentItem: Item {
                    implicitWidth: layoutBadge.width; implicitHeight: layoutBadge.height
                    Rectangle {
                        id: layoutBadge
                        anchors.centerIn: parent
                        width: layoutText.implicitWidth + 8; height: 16
                        radius: 4
                        color: "transparent"
                        border.width: 1.5; border.color: Theme.text
                        // Заглавные Inter стоят выше середины строки: подпись опущена до центра рамки.
                        Text {
                            renderType: Text.CurveRendering
                            id: layoutText
                            anchors.centerIn: parent
                            anchors.verticalCenterOffset: 0.75
                            text: root.desktop.keyboardLayout
                            color: Theme.text
                            font.family: Theme.sans; font.pixelSize: 10; font.weight: Font.Bold
                        }
                    }
                }
            }
            ShellButton {
                id: networkButton
                implicitHeight: Theme.barItemHeight
                symbol: root.network.wifiConnected ? "wifi" : root.network.connected ? "lan" : "wifi_off"
                hint: Lang.f(Lang.s.barNetworkHint, root.network.summary)
                selected: popout.opened && popout.showingNetwork
                onClicked: popout.toggle("network")
            }
            ShellButton {
                visible: root.services.bluetooth.available && root.services.bluetooth.enabled && !root.narrow
                implicitHeight: Theme.barItemHeight
                symbol: "bluetooth"
                hint: Lang.s.barBluetoothOn
                onClicked: popout.toggle("quick")
            }
            // Батарея: ячейка с заливкой по проценту, молния — при зарядке.
            ShellButton {
                visible: root.services.power.hasBattery
                implicitHeight: Theme.barItemHeight
                hint: Lang.f(root.services.power.charging ? Lang.s.barBatteryChargingName : Lang.s.barBatteryName, root.services.power.percent)
                    + (root.services.power.timeText ? " · " + root.services.power.timeText : "")
                onClicked: popout.toggle("quick")
                contentItem: Item {
                    implicitWidth: batteryRow.implicitWidth; implicitHeight: 14
                    Row {
                        id: batteryRow
                        anchors.centerIn: parent
                        spacing: 1
                        Rectangle {
                            id: batteryCell
                            anchors.verticalCenter: parent.verticalCenter
                            width: 25; height: 12; radius: 3.5
                            color: "transparent"
                            border.width: 1.2; border.color: Qt.rgba(1, 1, 1, 0.5)
                            Rectangle {
                                x: 2; y: 2
                                height: parent.height - 4
                                width: Math.max(2, (parent.width - 4) * root.services.power.percent / 100)
                                radius: 1.5
                                color: root.services.power.percent <= 10 && !root.services.power.charging ? Theme.danger : Theme.text
                            }
                            // При зарядке молния — внутри ячейки, тёмная на светлой заливке.
                            Icon {
                                visible: root.services.power.charging
                                anchors.centerIn: parent
                                name: "bolt"; filled: true; weight: 600; size: 12
                                color: root.services.power.percent > 45 ? "#1c1c20" : Theme.text
                            }
                        }
                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            width: 1.5; height: 4; radius: 1
                            color: Qt.rgba(1, 1, 1, 0.5)
                        }
                    }
                }
            }
            // «Не засыпать» включено: нажатие выключает режим.
            ShellButton {
                visible: root.services.keepAwake.active
                implicitHeight: Theme.barItemHeight
                symbol: "coffee"
                hint: Lang.s.barKeepAwakeOn
                onClicked: root.services.keepAwake.active = false
            }
            // «Не беспокоить» включено: нажатие выключает режим.
            ShellButton {
                visible: root.services.notifications.dnd
                implicitHeight: Theme.barItemHeight
                symbol: "do_not_disturb_on"
                hint: Lang.s.barDndOn
                onClicked: root.services.notifications.setDnd(false)
            }
            ShellButton {
                id: details
                implicitHeight: Theme.barItemHeight
                symbol: "tune"
                hint: Lang.s.quickSettingsTitle
                selected: popout.opened && popout.showingQuick
                onClicked: popout.toggle("quick")
            }
            // Дата и время открывают центр уведомлений; точка — есть непрочитанные.
            ShellButton {
                id: clockButton
                implicitHeight: Theme.barItemHeight
                text: root.tiny ? Lang.time(clock.date) : Lang.barClock(clock.date)
                hint: Lang.longDate(clock.date) + (root.services.notifications.unread > 0
                      ? " · " + Lang.f(Lang.s.barNotificationsUnread, root.services.notifications.unread) : "")
                Accessible.name: Lang.longDate(clock.date) + ", " + Lang.time(clock.date)
                selected: popout.opened && popout.showingNotifications
                onClicked: popout.toggle("notifications")
                Rectangle {
                    visible: root.services.notifications.unread > 0
                    width: 6; height: 6; radius: 3
                    color: Theme.accent
                    anchors { top: parent.top; right: parent.right; topMargin: 2; rightMargin: 1 }
                }
            }
        }
    }
    SystemClock { id: clock; precision: SystemClock.Minutes }
    HintPopup { id: hintPopup }
    // Одно всплывающее окно на панель; содержимое выбирает открывшая его кнопка.
    ShellPopup {
        id: popout
        readonly property bool showingMenu: currentName === "menu"
        readonly property bool showingApplications: currentName === "applications"
        readonly property bool showingNetwork: currentName === "network"
        readonly property bool showingQuick: currentName === "quick"
        readonly property bool showingClipboard: currentName === "clipboard"
        readonly property bool showingNotifications: currentName === "notifications"
        parentPanel: root
        reducedMotion: root.reducedMotion
        // Сетевая панель держит формы: щелчок в другом окне её не закрывает.
        persistent: showingNetwork
        // Поиск и буфер — окна по центру экрана; остальное выпадает из панели.
        readonly property bool centered: showingApplications || showingClipboard
        padding: showingMenu ? 5 : centered ? 0 : 10
        radius: centered ? Theme.radiusLarge : Theme.radiusPopup
        surfaceColor: centered ? Theme.solidSurface : Theme.popupSurface
        popupX: centered ? Math.round((root.width - panelWidth) / 2)
              : showingMenu ? Theme.screenMargin : Math.max(Theme.screenMargin, root.width - panelWidth - Theme.screenMargin)
        popupY: centered ? Math.round((root.screen ? root.screen.height : 800) * 0.19) : Theme.barHeight + Theme.popupGap
        panelWidth: showingMenu ? 248 : showingApplications ? Math.min(640, root.width - 24) : showingClipboard ? Math.min(600, root.width - 24)
                  : Math.min(showingNetwork || showingNotifications ? 376 : 336, root.width - 12)
        panelHeight: showingMenu ? quietlineMenu.implicitHeight + 10
                   : showingApplications ? searchPanel.contentHeight
                   : showingClipboard ? clipboardPanel.contentHeight
                   : Math.min(content.implicitHeight + 20, root.screen ? root.screen.height - 80 : 500)
        onPresented: { if (showingApplications) searchPanel.reset(); else if (showingClipboard) clipboardPanel.reset(); else if (showingMenu) quietlineMenu.focusFirst(); else if (showingNotifications) notificationCenter.reset(); }
        onDismissed: searchPanel.reset()
        QuietlineMenu {
            id: quietlineMenu
            visible: popout.showingMenu
            width: parent.width
            services: root.services
            onDone: popout.close()
            onSessionRequested: action => root.openSession(action)
        }
        SearchPanel {
            id: searchPanel
            visible: popout.showingApplications
            anchors.fill: parent
            desktop: root.desktop
            services: root.services
            finder: root.services.search
            monitorName: root.monitorName
            onDone: popout.close()
            onSessionRequested: action => root.openSession(action)
            onClipboardRequested: popout.open("clipboard")
        }
        ClipboardPanel {
            id: clipboardPanel
            visible: popout.showingClipboard
            anchors.fill: parent
            clipboard: root.services.clipboard
            onDone: popout.close()
        }
        ScrollView {
            id: summaryScroll
            visible: !popout.showingApplications && !popout.showingMenu && !popout.showingClipboard
            anchors.fill: parent
            rightPadding: ScrollBar.vertical.visible ? ScrollBar.vertical.width + 4 : 0
            ScrollBar.vertical: ShellScrollBar {}
            ColumnLayout {
                id: content
                width: summaryScroll.availableWidth; spacing: 12
                NotificationCenter {
                    id: notificationCenter
                    visible: popout.showingNotifications
                    Layout.fillWidth: true
                    service: root.services.notifications
                }
                Text { renderType: Text.CurveRendering; visible: popout.showingNetwork; text: Lang.s.settingsNetwork; color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.titleFontSize; font.weight: Font.Bold }
                Loader {
                    active: popout.showingNetwork && popout.opened
                    visible: active
                    Layout.fillWidth: true
                    sourceComponent: Component { NetworkControls { network: root.network; compact: true } }
                }
                QuickSettings {
                    visible: popout.showingQuick
                    Layout.fillWidth: true
                    services: root.services
                    indicators: root.indicators
                    builtinScreen: Models.isBuiltinOutput(root.monitorName)
                    onNetworkRequested: popout.open("network")
                    onSettingsRequested: section => { popout.close(); root.services.settings.open(section); }
                    onCloseRequested: popout.close()
                }
                // Трей, скрытый с узкой панели, остаётся доступным здесь.
                Text { renderType: Text.CurveRendering; visible: popout.showingQuick && root.compact && SystemTray.items.values.length > 0; text: Lang.s.barBackgroundApps; color: Theme.text2; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize }
                Repeater {
                    model: popout.showingQuick && root.compact ? SystemTray.items : null
                    delegate: ShellButton { required property var modelData; Layout.fillWidth: true; text: modelData.title || modelData.id; onClicked: { modelData.onlyMenu ? modelData.display(root, root.width - 300, 70) : modelData.activate(); } }
                }
            }
        }
    }
    CenterDialog {
        id: sessionDialog
        parentPanel: root
        cardWidth: 340
        reducedMotion: root.reducedMotion
        locked: root.services.session.busy
        onDismissed: root.services.session.reset()
        SessionDialog {
            id: sessionContent
            session: root.services.session
            entries: root.desktop.entries
            onDone: sessionDialog.close()
        }
    }
    CenterDialog {
        id: killDialog
        parentPanel: root
        cardWidth: 360
        reducedMotion: root.reducedMotion
        KillConfirm {
            id: killContent
            onDone: killDialog.close()
        }
    }
    // Сообщение об ошибке движка или оболочки — полоса под панелью.
    ShellButton {
        id: messageBar
        visible: root.message.length > 0
        x: Theme.screenMargin; y: Theme.barHeight + 2
        width: parent.width - Theme.screenMargin * 2; height: 26
        radius: Theme.radiusControl
        text: root.message
        hint: root.message + " · " + (root.engine.ready ? Lang.s.barDismissMessage : Lang.s.barRetryConnection)
        background: Rectangle {
            color: parent.hovered ? Qt.rgba(48 / 255, 48 / 255, 54 / 255, 0.92) : Theme.solidSurface
            radius: Theme.radiusControl
            border.width: parent.visualFocus ? 2 : 1
            border.color: parent.visualFocus ? Theme.accent : Theme.border
        }
        contentItem: Text {
            renderType: Text.CurveRendering
            text: root.message; color: root.errorText ? Theme.danger : Theme.text; font.family: Theme.sans
            font.pixelSize: Theme.smallFontSize; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter
            leftPadding: 10; rightPadding: 10
        }
        onClicked: {
            root.desktop.errorMessage = "";
            root.desktop.notice = "";
            if (!root.engine.ready) root.engine.retry();
            root.engine.dismiss();
        }
    }
}
