import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Services.SystemTray
import ".."
import "../controls"
import "../panels"
import "../logic/Models.js" as Models

// Верхняя панель экрана: меню приложений, пространства, заголовок окна, режим, показатели, трей и часы.
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
    readonly property string modeLabel: !engine.ready ? "Нет связи" : workspace ? workspace.mode === "tiles" ? "Тайлы" : "Окна" : "—"
    readonly property var buttons: engine.ready ? Models.workspaceItems(engine.state, monitorName) : []
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
                font.family: Theme.icons; text: "\uf009"; hint: "Открыть приложения"; implicitWidth: 28
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
                        hint: "Пространство " + item.number + (item.migrated ? " · " + Models.monitorLabel(item.monitor) : "")
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
                hint: root.engine.ready ? "Режим: " + root.modeLabel + " · Сменить · Super+M" : "Сервис окон недоступен"
                implicitWidth: root.tiny ? 36 : 108
                // Обе подписи режима стоят на месте и сменяются по общему прогрессу 0→1:
                // подтверждённая смена режима видна как переход, а не замена текста.
                contentItem: Item {
                    clip: true
                    Repeater {
                        model: [{mode: "windows", icon: "\uf24d", label: "Окна"}, {mode: "tiles", icon: "\uf00a", label: "Тайлы"}]
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
                text: root.network.connected ? "\uf796" : "\uf127"
                hint: "Сеть · " + root.network.summary
                onClicked: popout.toggle("network")
            }
            ShellButton {
                text: root.desktop.keyboardLayout
                hint: (root.desktop.keyboardLayoutName ? root.desktop.keyboardLayoutName + " · " : "") + "Сменить раскладку · левый Alt+Shift"
                onClicked: root.desktop.switchLayout()
            }
            Text {
                visible: root.services.bluetooth.available && !root.narrow
                font.family: Theme.icons
                text: "\uf293"
                color: Theme.muted; font.pixelSize: Theme.iconFontSize
                Accessible.name: root.services.bluetooth.enabled ? "Bluetooth включён" : "Bluetooth выключен"
            }
            Text {
                visible: root.services.power.hasBattery && !root.tiny
                Layout.preferredWidth: 58
                text: (root.services.power.charging ? "↯ " : "▰ ") + root.services.power.percent + "%"
                color: Theme.text; font.family: Theme.mono; font.pixelSize: Theme.smallFontSize
                Accessible.name: "Заряд батареи " + root.services.power.percent + "%" + (root.services.power.charging ? ", заряжается" : "")
            }
            ShellButton {
                id: details
                font.family: Theme.icons
                text: "\uf1de"
                hint: "Быстрые настройки"
                onClicked: popout.toggle("quick")
            }
            Text {
                text: Qt.formatTime(clock.date, "HH:mm")
                color: Theme.text; font.family: Theme.mono; font.pixelSize: Theme.fontSize
                Accessible.name: Qt.formatDateTime(clock.date, "dddd, d MMMM, HH:mm")
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
        parentPanel: root
        // Сетевая панель держит формы и не закрывается от щелчка в другом окне.
        persistent: showingNetwork
        popupX: showingApplications ? Theme.outerMargin : Math.max(12, root.width - width - 12)
        popupY: Theme.outerMargin + Theme.barHeight + 8
        implicitWidth: showingApplications ? Math.min(360, root.width - Theme.outerMargin * 2) : Math.min(showingNetwork ? 400 : 330, root.width - 24)
        implicitHeight: showingApplications ? Math.min(430, root.screen ? root.screen.height - 100 : 430)
                                            : Math.min(content.implicitHeight + 24, root.screen ? root.screen.height - 100 : 500)
        onPresented: { if (showingApplications) search.forceActiveFocus(); }
        onDismissed: search.clear()
        ColumnLayout {
            visible: popout.showingApplications
            anchors.fill: parent; spacing: 10
            Text { text: "Приложения"; color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.titleFontSize; font.bold: true }
            TextField {
                id: search
                Layout.fillWidth: true
                placeholderText: "Найти приложение"
                font.family: Theme.sans; font.pixelSize: Theme.fontSize
                color: Theme.text; placeholderTextColor: Theme.muted; selectByMouse: true; rightPadding: 32
                Accessible.name: "Поиск приложений"
                background: Rectangle { color: Theme.background; radius: Theme.controlRadius; border.color: search.activeFocus ? Theme.accent : Theme.border; border.width: 1 }
                ShellButton { anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; visible: search.text.length > 0; text: "×"; hint: "Очистить поиск"; onClicked: { search.clear(); search.forceActiveFocus(); } }
                onAccepted: { if (apps.count) apps.itemAt(0).clicked(); }
            }
            ScrollView {
                id: appScroll
                Layout.fillWidth: true; Layout.fillHeight: true
                ScrollBar.vertical: ShellScrollBar {}
                Column {
                    width: appScroll.availableWidth; spacing: 3
                    Repeater {
                        id: apps
                        model: root.desktop.entries.filter(entry => (entry.name + " " + entry.id).toLowerCase().indexOf(search.text.toLowerCase()) >= 0)
                        delegate: ShellButton {
                            required property var modelData
                            width: popout.availableWidth
                            text: modelData.name; hint: modelData.name
                            onClicked: { root.desktop.launch(modelData.id, root.monitorName); popout.close(); }
                        }
                    }
                    Text { visible: apps.count === 0; text: "Приложения не найдены"; color: Theme.muted; font.family: Theme.sans; topPadding: 12 }
                }
            }
        }
        ScrollView {
            id: summaryScroll
            visible: !popout.showingApplications
            anchors.fill: parent
            ScrollBar.vertical: ShellScrollBar {}
            ColumnLayout {
                id: content
                width: summaryScroll.availableWidth; spacing: 12
                Text { visible: popout.showingNetwork; text: "Сеть"; color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.titleFontSize; font.bold: true }
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
                Text { visible: popout.showingQuick && root.compact; text: "CPU  " + root.indicators.cpuText + "\nRAM  " + root.indicators.memoryText + " ГБ"; color: Theme.text; font.family: Theme.mono; font.pixelSize: Theme.fontSize; lineHeight: 1.4 }
                Text { visible: popout.showingQuick && root.compact && SystemTray.items.values.length > 0; text: "Фоновые приложения"; color: Theme.muted; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize }
                Repeater {
                    model: popout.showingQuick && root.compact ? SystemTray.items : null
                    delegate: ShellButton { required property var modelData; Layout.fillWidth: true; text: modelData.title || modelData.id; onClicked: { modelData.onlyMenu ? modelData.display(root, root.width - 300, 70) : modelData.activate(); } }
                }
                Text { visible: popout.showingQuick && root.tiny && root.services.power.hasBattery; text: "Батарея " + root.services.power.percent + "%" + (root.services.power.timeText ? " · " + root.services.power.timeText : ""); color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.fontSize }
            }
        }
    }
    ShellButton {
        visible: root.message.length > 0
        x: 12; y: Theme.outerMargin + Theme.barHeight - 1
        width: parent.width - 24; height: 28
        text: root.message
        hint: root.message + (root.engine.ready ? " · Закрыть сообщение" : " · Повторить подключение")
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
