import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
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

// Верхняя панель экрана: поиск, пространства, заголовок окна, режим, показатели, трей, часы и кнопка питания.
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
    readonly property bool compact: width < 1100
    readonly property bool narrow: width < 820
    // Уже этой ширины справа остаются только главные элементы, остальное — в быстрых настройках.
    readonly property bool tiny: width < 640
    // 0 — «Окна», 1 — «Тайлы»; анимируется только после подтверждения движком.
    property real modeProgress: workspace && workspace.mode === "tiles" ? 1 : 0
    Behavior on modeProgress { NumberAnimation { duration: root.indicators.reducedMotion ? 0 : Theme.modeDuration; easing.type: Easing.OutCubic } }
    readonly property string modeLabel: !engine.ready ? Lang.s.barNoConnection : workspace ? workspace.mode === "tiles" ? Lang.s.modeTiles : Lang.s.modeWindows : "—"
    readonly property var buttons: engine.ready ? Models.workspaceItems(engine.state, monitorName, Lang.s) : []
    readonly property var buttonsByKey: Models.keyed(buttons, Models.workspaceKey)
    readonly property string activeTitle: {
        var active = desktop.windows.find(window => window.monitor === monitorName && window.activated);
        return active ? active.title : "";
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
    // Меню питания с ожидающим подтверждения действием сеанса.
    function openSession(action) { popout.open("power"); Qt.callLater(function() { powerMenu.confirming = action; }); }
    // Подтверждение принудительного завершения процесса окна `window`.
    function confirmKill(window) { killConfirm.target = window; popout.open("kill"); }
    implicitHeight: Theme.outerMargin + Theme.barHeight + (message.length > 0 ? 28 : 0)
    exclusiveZone: Theme.outerMargin + Theme.barHeight + 12
    color: "transparent"
    focusable: true

    Rectangle {
        id: bar
        x: Theme.outerMargin; y: Theme.outerMargin
        width: parent.width - Theme.outerMargin * 2; height: Theme.barHeight
        color: Theme.surface
        radius: Theme.panelRadius
        clip: true
        border.width: 1; border.color: Theme.border
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 8; anchors.rightMargin: 8
            spacing: root.narrow ? 3 : 7
            ShellButton {
                id: launcher
                font.family: Theme.icons; text: "\uf009"; hint: Lang.s.barSearchHint; implicitWidth: 28
                onClicked: popout.toggle("applications")
            }
            Rectangle { width: 1; height: 15; color: Theme.border }
            Row {
                spacing: 2
                Repeater {
                    model: ScriptModel { values: root.buttons.map(Models.workspaceKey) }
                    delegate: ShellButton {
                        id: workspaceButton
                        required property string modelData
                        readonly property var item: root.buttonsByKey[modelData] || ({number: 0, monitor: "", label: "", migrated: false, active: false})
                        text: item.migrated ? root.tiny ? "↪" + item.number : item.label : ""
                        hint: Lang.f(Lang.s.barWorkspaceHint, item.number) + (item.migrated ? " · " + Models.monitorLabel(item.monitor) : "")
                        implicitWidth: item.migrated ? root.tiny ? 28 : Math.min(110, implicitContentWidth + 12) : root.tiny ? 14 : root.narrow ? 20 : 24
                        enabled: root.engine.ready && !root.engine.busy
                        // Перенесённое пространство открывается на мониторе этой панели:
                        // фокус переходит на её монитор до команды движку.
                        onClicked: {
                            if (item.migrated) root.desktop.focusMonitor(root.monitorName);
                            root.engine.switchWorkspace(item.number, item.monitor);
                        }
                        Rectangle {
                            visible: !workspaceButton.item.migrated
                            anchors.centerIn: parent
                            width: workspaceButton.item.active ? 18 : 6; height: 6
                            radius: 3
                            color: workspaceButton.item.active ? Theme.accent : Theme.border
                        }
                    }
                }
            }
            Item { Layout.fillWidth: true; Layout.minimumWidth: 0 }
            Text {
                visible: !root.narrow
                Layout.maximumWidth: Math.max(0, root.width * 0.2)
                Layout.fillWidth: true
                text: root.activeTitle
                color: Theme.muted
                font.family: Theme.sans; font.pixelSize: Theme.fontSize
                horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight
                Accessible.name: root.activeTitle
            }
            Item { Layout.fillWidth: true; Layout.minimumWidth: 0 }
            ShellButton {
                id: modeButton
                text: root.modeLabel
                hint: root.engine.ready ? Lang.f(Lang.s.barModeHint, root.modeLabel) : Lang.s.barEngineUnavailable
                implicitWidth: root.tiny ? 36 : 108
                // Обе подписи режима стоят на месте и сменяются по общему прогрессу 0→1:
                // подтверждённая смена режима видна как переход, а не замена текста.
                contentItem: Item {
                    clip: true
                    Repeater {
                        model: [{mode: "windows", icon: "\uf24d", label: Lang.s.modeWindows}, {mode: "tiles", icon: "\uf00a", label: Lang.s.modeTiles}]
                        delegate: Row {
                            required property var modelData
                            required property int index
                            readonly property real distance: Math.abs(root.modeProgress - index)
                            visible: root.engine.ready && !!root.workspace && !modeButton.busy && opacity > 0
                            opacity: 1 - distance
                            anchors.horizontalCenter: parent.horizontalCenter
                            y: Math.round((parent.height - height) / 2 + (index - root.modeProgress) * 10)
                            spacing: 6
                            Text {
                                text: modelData.icon
                                font.family: Theme.icons; font.pixelSize: Theme.fontSize
                                color: Theme.accentText
                            }
                            Text {
                                visible: !root.tiny
                                text: modelData.label
                                font.family: Theme.sans; font.pixelSize: Theme.fontSize; font.weight: Font.DemiBold
                                color: Theme.accentText
                            }
                        }
                    }
                    Text {
                        visible: modeButton.busy || !root.engine.ready || !root.workspace
                        anchors.centerIn: parent
                        text: modeButton.busy ? "…" : root.tiny ? "!" : root.modeLabel
                        font.family: Theme.sans; font.pixelSize: Theme.fontSize
                        color: modeButton.emphasized ? Theme.accentText : Theme.muted
                    }
                }
                emphasized: root.engine.ready && !!root.workspace
                enabled: root.engine.ready && !!root.monitor && !root.engine.busy
                busy: root.engine.busy && root.engine.pendingMonitor === (root.monitor ? root.monitor.key : "")
                onClicked: root.engine.toggle(root.monitor.key)
            }
            Text {
                visible: !root.compact
                Layout.preferredWidth: 160
                text: "CPU " + root.indicators.cpuText + "   RAM " + root.indicators.memoryText
                color: Theme.muted; font.family: Theme.mono; font.pixelSize: Theme.smallFontSize
            }
            Row {
                visible: !root.compact
                spacing: 1
                Repeater {
                    model: SystemTray.items
                    delegate: ShellButton {
                        required property var modelData
                        hint: modelData.tooltipTitle || modelData.title || modelData.id
                        implicitWidth: 26
                        function showMenu() {
                            var point = mapToItem(root.contentItem, 0, height);
                            modelData.display(root, point.x, point.y);
                        }
                        onClicked: {
                            if (modelData.onlyMenu) showMenu();
                            else modelData.activate();
                        }
                        Image { anchors.centerIn: parent; width: 17; height: 17; source: parent.modelData.icon; sourceSize.width: 24; sourceSize.height: 24 }
                        TapHandler { acceptedButtons: Qt.RightButton; onTapped: parent.showMenu() }
                    }
                }
            }
            ShellButton {
                id: networkButton
                font.family: Theme.icons
                text: root.network.wifiConnected ? "\uf1eb" : root.network.connected ? "\uf0e8" : "\uf127"
                hint: Lang.f(Lang.s.barNetworkHint, root.network.summary)
                onClicked: popout.toggle("network")
            }
            ShellButton {
                text: root.desktop.keyboardLayout
                hint: (root.desktop.keyboardLayoutName ? root.desktop.keyboardLayoutName + " · " : "") + Lang.f(Lang.s.barLayoutHint, Models.toggleLabel(Lang.toggle, Lang.s))
                onClicked: root.desktop.switchLayout()
            }
            Text {
                visible: root.services.bluetooth.available && !root.narrow
                font.family: Theme.icons
                text: "\uf293"
                color: Theme.muted; font.pixelSize: Theme.iconFontSize
                Accessible.name: root.services.bluetooth.enabled ? Lang.s.barBluetoothOn : Lang.s.barBluetoothOff
            }
            Text {
                visible: root.services.power.hasBattery && !root.tiny
                Layout.preferredWidth: 58
                text: (root.services.power.charging ? "↯ " : "▰ ") + root.services.power.percent + "%"
                color: Theme.text; font.family: Theme.mono; font.pixelSize: Theme.smallFontSize
                Accessible.name: Lang.f(root.services.power.charging ? Lang.s.barBatteryChargingName : Lang.s.barBatteryName, root.services.power.percent)
            }
            ShellButton {
                id: details
                font.family: Theme.icons
                text: "\uf1de"
                hint: Lang.s.quickSettingsTitle
                onClicked: popout.toggle("quick")
            }
            // «Не засыпать» включено: нажатие выключает режим.
            ShellButton {
                visible: root.services.keepAwake.active
                font.family: Theme.icons
                text: "\uf0f4"
                foreground: Theme.muted
                hint: Lang.s.barKeepAwakeOn
                onClicked: root.services.keepAwake.active = false
            }
            // «Не беспокоить» включено: нажатие выключает режим.
            ShellButton {
                visible: root.services.notifications.dnd
                font.family: Theme.icons
                text: "\uf186"
                foreground: Theme.muted
                hint: Lang.s.barDndOn
                onClicked: root.services.notifications.setDnd(false)
            }
            // Часы открывают центр уведомлений; точка — есть непрочитанные.
            ShellButton {
                id: clockButton
                text: Lang.time(clock.date)
                font.family: Theme.mono
                hint: Lang.longDate(clock.date) + (root.services.notifications.unread > 0
                      ? " · " + Lang.f(Lang.s.barNotificationsUnread, root.services.notifications.unread) : "")
                Accessible.name: Lang.longDate(clock.date) + ", " + Lang.time(clock.date)
                onClicked: popout.toggle("notifications")
                Rectangle {
                    visible: root.services.notifications.unread > 0
                    width: 6; height: 6; radius: 3
                    color: Theme.accent
                    anchors { top: parent.top; right: parent.right; topMargin: 4; rightMargin: 3 }
                }
            }
            // Кнопка питания — последний элемент панели, видна и на узком экране.
            ShellButton {
                id: powerButton
                font.family: Theme.icons
                text: "\uf011"
                foreground: Theme.danger
                hint: Lang.s.barPower
                onClicked: popout.toggle("power")
            }
        }
    }
    SystemClock { id: clock; precision: SystemClock.Minutes }
    HintPopup { id: hintPopup }
    // Одно всплывающее окно на панель; содержимое выбирает открывшая его кнопка.
    ShellPopup {
        id: popout
        readonly property bool showingApplications: currentName === "applications"
        readonly property bool showingNetwork: currentName === "network"
        readonly property bool showingQuick: currentName === "quick"
        readonly property bool showingPower: currentName === "power"
        readonly property bool showingKill: currentName === "kill"
        readonly property bool showingClipboard: currentName === "clipboard"
        readonly property bool showingNotifications: currentName === "notifications"
        parentPanel: root
        // Сетевая панель держит формы, меню питания — ход и итог закрытия приложений: щелчок
        // в другом окне (например, в диалоге сохранения) их не закрывает.
        persistent: showingNetwork || (showingPower && (root.services.session.busy || root.services.session.remaining.length > 0))
        popupX: showingApplications ? 6 : Math.max(6, root.width - panelWidth - 6)
        popupY: Theme.outerMargin + Theme.barHeight + 8
        panelWidth: showingApplications ? Math.min(360, root.width - Theme.outerMargin * 2) : Math.min(showingNetwork || showingClipboard || showingNotifications ? 400 : 330, root.width - 24)
        panelHeight: showingApplications ? Math.min(430, root.screen ? root.screen.height - 100 : 430)
                                            : Math.min(content.implicitHeight + 24, root.screen ? root.screen.height - 100 : 500)
        onPresented: { if (showingApplications) searchPanel.reset(); else if (showingPower) powerMenu.reset(); else if (showingKill) killConfirm.focusCancel(); else if (showingClipboard) clipboardPanel.reset(); }
        onDismissed: { searchPanel.reset(); powerMenu.reset(); }
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
        ScrollView {
            id: summaryScroll
            visible: !popout.showingApplications
            anchors.fill: parent
            rightPadding: ScrollBar.vertical.visible ? ScrollBar.vertical.width + 4 : 0
            ScrollBar.vertical: ShellScrollBar {}
            ColumnLayout {
                id: content
                width: summaryScroll.availableWidth; spacing: 12
                ClipboardPanel {
                    id: clipboardPanel
                    visible: popout.showingClipboard
                    Layout.fillWidth: true
                    clipboard: root.services.clipboard
                    onDone: popout.close()
                }
                NotificationCenter {
                    visible: popout.showingNotifications
                    Layout.fillWidth: true
                    service: root.services.notifications
                }
                KillConfirm {
                    id: killConfirm
                    visible: popout.showingKill
                    Layout.fillWidth: true
                    onDone: popout.close()
                }
                PowerMenu {
                    id: powerMenu
                    visible: popout.showingPower
                    Layout.fillWidth: true
                    session: root.services.session
                    onDone: popout.close()
                }
                Text { visible: popout.showingNetwork; text: Lang.s.settingsNetwork; color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.titleFontSize; font.bold: true }
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
                    builtinScreen: Models.isBuiltinOutput(root.monitorName)
                    onNetworkRequested: popout.open("network")
                    onSettingsRequested: { popout.close(); root.services.settings.open(""); }
                }
                // Скрытое с узкой панели остаётся доступным здесь.
                Text { visible: popout.showingQuick && root.compact; text: "CPU  " + root.indicators.cpuText + "\nRAM  " + root.indicators.memoryText + " " + Lang.s.unitGb; color: Theme.text; font.family: Theme.mono; font.pixelSize: Theme.fontSize; lineHeight: 1.4 }
                Text { visible: popout.showingQuick && root.compact && SystemTray.items.values.length > 0; text: Lang.s.barBackgroundApps; color: Theme.muted; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize }
                Repeater {
                    model: popout.showingQuick && root.compact ? SystemTray.items : null
                    delegate: ShellButton { required property var modelData; Layout.fillWidth: true; text: modelData.title || modelData.id; onClicked: { modelData.onlyMenu ? modelData.display(root, root.width - 300, 70) : modelData.activate(); } }
                }
                Text { visible: popout.showingQuick && root.tiny && root.services.power.hasBattery; text: Lang.f(Lang.s.powerBattery, root.services.power.percent) + (root.services.power.timeText ? " · " + root.services.power.timeText : ""); color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.fontSize }
            }
        }
    }
    ShellButton {
        visible: root.message.length > 0
        x: 12; y: Theme.outerMargin + Theme.barHeight - 1
        width: parent.width - 24; height: 28
        text: root.message
        hint: root.message + " · " + (root.engine.ready ? Lang.s.barDismissMessage : Lang.s.barRetryConnection)
        background: Rectangle {
            color: parent.hovered ? Theme.raised : Theme.surface
            radius: Theme.controlRadius
            border.width: parent.visualFocus ? 2 : 1
            border.color: parent.visualFocus ? Theme.accent : Theme.border
        }
        contentItem: Text {
            text: root.message; color: root.errorText ? Theme.danger : Theme.text; font.family: Theme.sans
            font.pixelSize: Theme.smallFontSize; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter
        }
        onClicked: {
            root.desktop.errorMessage = "";
            root.desktop.notice = "";
            if (!root.engine.ready) root.engine.retry();
            root.engine.dismiss();
        }
    }
}
