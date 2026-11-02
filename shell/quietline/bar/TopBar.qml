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

// Верхняя панель экрана, 30 px вплотную к краю: слева меню Quietline, активное приложение (меню
// окна) и пространства (колесо мыши листает их); справа группами — режим «Окна / Тайлы»; трей;
// приватность (микрофон, запись экрана), раскладка, сеть и VPN, Bluetooth, звук (колесо —
// громкость), батарея, «Не засыпать», «Не беспокоить»; пункт управления и дата со временем.
// Значки состояния открывают свои окна: сеть, Bluetooth, звук, батарея.
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
    readonly property var activeWindow: desktop.windows.find(window => window.monitor === monitorName && window.activated) || null
    readonly property var audio: services.audio
    readonly property var power: services.power
    readonly property string batteryLevel: Models.batteryLevel(power.percent, power.charging)
    // Меню окна берёт окно и номера при открытии: фокус меню не меняет цель.
    function openWindowMenu() {
        if (popout.opened && popout.showingWindow) { popout.close(); return; }
        if (!activeWindow) return;
        windowMenu.window = activeWindow;
        windowMenu.appName = activeApp;
        windowMenu.targets = Models.moveTargets(buttons);
        windowMenu.currentNumber = workspace ? workspace.number : 0;
        popout.windowX = appButton.mapToItem(bar, 0, 0).x;
        popout.open("window");
    }
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
            ShellButton {
                id: appButton
                visible: !root.narrow && root.activeApp.length > 0
                Layout.maximumWidth: Math.max(0, root.width * 0.22)
                implicitHeight: Theme.barItemHeight
                text: root.activeApp
                hint: Lang.s.barWindowMenuHint
                font.weight: Font.Bold
                selected: popout.opened && popout.showingWindow
                onClicked: root.openWindowMenu()
                Accessible.name: root.activeApp
            }
            Row {
                Layout.leftMargin: 4
                spacing: 2
                WheelSteps {
                    onStep: direction => {
                        if (!root.engine.ready || root.engine.busy) return;
                        var target = Models.wheelWorkspace(root.buttons, direction);
                        if (target) root.engine.switchWorkspace(target.number, target.monitor);
                    }
                }
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
            // Правая часть — группы: режим окон | запущенные программы (трей) | системное (приватность,
            // раскладка, сеть, VPN, Bluetooth, звук, батарея, режимы) | пункт управления и часы. Каждая группа,
            // кроме первой, начинается разделителем и прячется вместе с ним.
            RowLayout {
                spacing: 0
                // Режим активного пространства; меняется только после подтверждения движком.
                RowLayout {
                    spacing: 0
                    SegmentedControl {
                        id: modeControl
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
                }
                RowLayout {
                    spacing: 0
                    GroupDivider {}
                    visible: !root.compact && SystemTray.items.values.length > 0
                    Repeater {
                        model: SystemTray.items
                        delegate: BarIcon {
                            required property var modelData
                            hint: modelData.tooltipTitle || modelData.title || modelData.id
                            function showMenu() {
                                var point = mapToItem(root.contentItem, 0, height);
                                modelData.display(root, point.x, point.y);
                            }
                            onClicked: {
                                if (modelData.onlyMenu) showMenu();
                                else modelData.activate();
                            }
                            // Значки трея обесцвечены и приведены к тону текста панели: в тёмной теме
                            // слегка осветлены, в светлой затемнены почти до чёрного; детали сохраняются.
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
                                brightness: Theme.light ? -0.8 : 0.15
                                opacity: 0.9
                            }
                            TapHandler { acceptedButtons: Qt.RightButton; onTapped: parent.showMenu() }
                        }
                    }
                }
                RowLayout {
                    spacing: 0
                    GroupDivider {}
                    // Приватность: оранжевая капсула, пока приложение пишет микрофон или идёт запись экрана.
                    Rectangle {
                        id: privacy
                        readonly property var micUsers: root.audio.micUsers
                        readonly property bool screen: root.desktop.screencast
                        visible: micUsers.length > 0 || screen
                        Layout.leftMargin: 4; Layout.rightMargin: 4
                        implicitWidth: privacyRow.implicitWidth + 10; implicitHeight: 18
                        radius: 9
                        color: Theme.warning
                        Row {
                            id: privacyRow
                            anchors.centerIn: parent
                            spacing: 2
                            Icon { visible: privacy.micUsers.length > 0; name: "mic"; filled: true; size: 13; color: Theme.accentForeground }
                            Icon { visible: privacy.screen; name: "screen_share"; filled: true; size: 13; color: Theme.accentForeground }
                        }
                        HoverHandler {
                            onHoveredChanged: {
                                var text = [privacy.micUsers.length > 0 ? Lang.f(Lang.s.barPrivacyMic, privacy.micUsers.join(", ")) : "",
                                            privacy.screen ? Lang.s.barPrivacyScreen : ""].filter(Boolean).join(" · ");
                                if (hovered) root.hints.show(privacy, text, true);
                                else root.hints.hide(privacy);
                            }
                        }
                        Accessible.role: Accessible.StaticText
                        Accessible.name: Lang.s.barPrivacyScreen
                    }
                    ShellButton {
                        implicitHeight: Theme.barItemHeight
                        hint: (root.desktop.keyboardLayoutName ? root.desktop.keyboardLayoutName + " · " : "") + Lang.f(Lang.s.barLayoutHint, Models.toggleLabel(Lang.toggle, Lang.s))
                        Accessible.name: root.desktop.keyboardLayout
                        onClicked: root.desktop.switchLayout()
                        contentItem: Item {
                            implicitWidth: layoutBadge.width + 4; implicitHeight: layoutBadge.height
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
                    BarIcon {
                        id: networkButton
                        symbol: root.network.wifiConnected ? Models.barWifiSymbol(root.network.wifiSignal) : root.network.connected ? "lan" : "wifi_off"
                        hint: Lang.f(Lang.s.barNetworkHint, root.network.summary)
                        selected: popout.opened && popout.showingNetwork
                        onClicked: popout.toggle("network")
                    }
                    BarIcon {
                        visible: root.network.vpn && !root.narrow
                        symbol: "vpn_key"
                        hint: Lang.s.barVpnOn
                        onClicked: popout.toggle("network")
                    }
                    BarIcon {
                        visible: root.services.bluetooth.available && root.services.bluetooth.enabled && !root.narrow
                        symbol: root.services.bluetooth.connected.length > 0 ? "bluetooth_connected" : "bluetooth"
                        hint: root.services.bluetooth.connected.length > 0
                            ? Lang.f(Lang.s.barBluetoothConnected, root.services.bluetooth.connected.map(device => root.services.bluetooth.label(device)).join(", "))
                            : Lang.s.barBluetoothOn
                        selected: popout.opened && popout.showingBluetooth
                        onClicked: popout.toggle("bluetooth")
                    }
                    // Звук: колесо — громкость по 5 %, средняя кнопка — без звука, щелчок — окно звука.
                    BarIcon {
                        visible: root.audio.available && !root.narrow
                        readonly property var sinkAudio: root.audio.available ? root.audio.sink.audio : null
                        symbol: sinkAudio ? Models.volumeSymbol(sinkAudio.volume, sinkAudio.muted) : "volume_up"
                        hint: sinkAudio && sinkAudio.muted ? Lang.s.barSoundMuted : Lang.f(Lang.s.barSoundHint, Math.round((sinkAudio ? sinkAudio.volume : 0) * 100))
                        selected: popout.opened && popout.showingSound
                        onClicked: popout.toggle("sound")
                        TapHandler { acceptedButtons: Qt.MiddleButton; onTapped: root.audio.toggleMute() }
                        WheelSteps { onStep: direction => root.audio.stepVolume(-direction * 0.05) }
                    }
                    // Батарея: ячейка с заливкой по проценту (оранжевая при 20 % и ниже, красная при 10 %),
                    // молния — при зарядке, процент рядом — по настройке «Оформления».
                    ShellButton {
                        visible: root.power.hasBattery
                        implicitHeight: Theme.barItemHeight
                        hint: Lang.f(root.power.charging ? Lang.s.barBatteryChargingName : Lang.s.barBatteryName, root.power.percent)
                            + (root.power.timeText ? " · " + root.power.timeText : "")
                        selected: popout.opened && popout.showingBattery
                        onClicked: popout.toggle("battery")
                        contentItem: Item {
                            implicitWidth: batteryRow.implicitWidth + 4; implicitHeight: 14
                            Row {
                                id: batteryRow
                                anchors.centerIn: parent
                                spacing: 1
                                Text {
                                    renderType: Text.CurveRendering
                                    visible: Appearance.batteryPercent
                                    anchors.verticalCenter: parent.verticalCenter
                                    rightPadding: 4
                                    text: root.power.percent + "%"
                                    color: Theme.text
                                    font.family: Theme.sans; font.pixelSize: Theme.smallFontSize; font.weight: Font.Medium
                                    font.features: { "tnum": 1 }
                                }
                                Rectangle {
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 25; height: 12; radius: 3.5
                                    color: "transparent"
                                    border.width: 1.2; border.color: Theme.batteryOutline
                                    Rectangle {
                                        x: 2; y: 2
                                        height: parent.height - 4
                                        width: Math.max(2, (parent.width - 4) * root.power.percent / 100)
                                        radius: 1.5
                                        color: root.batteryLevel === "critical" ? Theme.danger : root.batteryLevel === "low" ? Theme.warning : Theme.text
                                    }
                                    // При зарядке молния — внутри ячейки, контрастная заливке.
                                    Icon {
                                        visible: root.power.charging
                                        anchors.centerIn: parent
                                        name: "bolt"; filled: true; weight: 600; size: 12
                                        color: root.power.percent > 45 ? Theme.textInverse : Theme.text
                                    }
                                }
                                Rectangle {
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 1.5; height: 4; radius: 1
                                    color: Theme.batteryOutline
                                }
                            }
                        }
                    }
                    // «Не засыпать» включено: нажатие выключает режим.
                    BarIcon {
                        visible: root.services.keepAwake.active
                        symbol: "coffee"
                        hint: Lang.s.barKeepAwakeOn
                        onClicked: root.services.keepAwake.active = false
                    }
                    // «Не беспокоить» включено: нажатие выключает режим.
                    BarIcon {
                        visible: root.services.notifications.dnd
                        symbol: "do_not_disturb_on"
                        hint: Lang.s.barDndOn
                        onClicked: root.services.notifications.setDnd(false)
                    }
                }
                RowLayout {
                    spacing: 0
                    GroupDivider {}
                    BarIcon {
                        id: details
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
        readonly property bool showingBattery: currentName === "battery"
        readonly property bool showingBluetooth: currentName === "bluetooth"
        readonly property bool showingSound: currentName === "sound"
        readonly property bool showingWindow: currentName === "window"
        // Левый край меню окна — под названием приложения; задаётся при открытии.
        property real windowX: Theme.screenMargin
        parentPanel: root
        reducedMotion: root.reducedMotion
        // Сетевая панель не закрывается щелчком мимо, только пока в ней вводят пароль, заполняют
        // форму профиля, подключаются или решают «Оставить / Вернуть»; иначе — как остальные окна.
        persistent: showingNetwork && !!networkLoader.item && networkLoader.item.holding
        // Поиск и буфер — окна по центру экрана; остальное выпадает из панели.
        readonly property bool centered: showingApplications || showingClipboard
        padding: showingMenu || showingWindow ? 5 : centered ? 0 : 10
        radius: centered ? Theme.radiusLarge : Theme.radiusPopup
        surfaceColor: centered ? Theme.solidSurface : Theme.popupSurface
        popupX: centered ? Math.round((root.width - panelWidth) / 2)
              : showingMenu ? Theme.screenMargin
              : showingWindow ? Math.max(Theme.screenMargin, Math.min(windowX, root.width - panelWidth - Theme.screenMargin))
              : Math.max(Theme.screenMargin, root.width - panelWidth - Theme.screenMargin)
        popupY: centered ? Math.round((root.screen ? root.screen.height : 800) * 0.19) : Theme.barHeight + Theme.popupGap
        panelWidth: showingMenu || showingWindow ? 248 : showingApplications ? Math.min(640, root.width - 24) : showingClipboard ? Math.min(600, root.width - 24)
                  : Math.min(showingNetwork || showingNotifications ? 376 : showingBattery ? 300 : 336, root.width - 12)
        panelHeight: showingMenu ? quietlineMenu.implicitHeight + 10
                   : showingWindow ? windowMenu.implicitHeight + 10
                   : showingApplications ? searchPanel.contentHeight
                   : showingClipboard ? clipboardPanel.contentHeight
                   : Math.min(content.implicitHeight + 20, root.screen ? root.screen.height - 80 : 500)
        onPresented: { if (showingApplications) searchPanel.reset(); else if (showingClipboard) clipboardPanel.reset(); else if (showingMenu) quietlineMenu.takeFocus(); else if (showingWindow) windowMenu.takeFocus(); else if (showingNotifications) notificationCenter.reset(); }
        onDismissed: searchPanel.reset()
        QuietlineMenu {
            id: quietlineMenu
            visible: popout.showingMenu
            width: parent.width
            services: root.services
            onDone: popout.close()
            onSessionRequested: action => root.openSession(action)
        }
        WindowMenu {
            id: windowMenu
            visible: popout.showingWindow
            width: parent.width
            desktop: root.desktop
            engine: root.engine
            onDone: popout.close()
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
            visible: !popout.showingApplications && !popout.showingMenu && !popout.showingClipboard && !popout.showingWindow
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
                    id: networkLoader
                    active: popout.showingNetwork && popout.opened
                    visible: active
                    Layout.fillWidth: true
                    sourceComponent: Component { NetworkControls { network: root.network; compact: true } }
                }
                Text { renderType: Text.CurveRendering; visible: popout.showingBluetooth; text: "Bluetooth"; color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.titleFontSize; font.weight: Font.Bold }
                Loader {
                    active: popout.showingBluetooth && popout.opened
                    visible: active
                    Layout.fillWidth: true
                    sourceComponent: Component { BluetoothControls { bluetooth: root.services.bluetooth } }
                }
                Text { renderType: Text.CurveRendering; visible: popout.showingSound; text: Lang.s.quickSound; color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.titleFontSize; font.weight: Font.Bold }
                Loader {
                    active: popout.showingSound && popout.opened
                    visible: active
                    Layout.fillWidth: true
                    sourceComponent: Component { AudioControls { audio: root.services.audio } }
                }
                BatteryPanel {
                    visible: popout.showingBattery
                    Layout.fillWidth: true
                    power: root.power
                    reducedMotion: root.reducedMotion
                    onSettingsRequested: { popout.close(); root.services.settings.open("power"); }
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
            color: parent.hovered ? Theme.solidSurfaceHover : Theme.solidSurface
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
