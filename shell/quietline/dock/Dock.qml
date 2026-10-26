import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import ".."
import "../controls"
import "../logic/Models.js" as Models

// Док экрана: закреплённые и запущенные на мониторе приложения; виден только в режиме «Окна» без полноэкранного окна.
PanelWindow {
    id: root
    required property var engine
    required property var desktop
    required property var indicators
    readonly property string monitorName: screen ? screen.name : ""
    readonly property var workspace: engine.ready ? Models.activeWorkspace(engine.state, monitorName) : null
    readonly property bool fullscreen: !!workspace && Models.fullscreenOn(desktop.windows, monitorName, workspace.workspace_id)
    readonly property bool shown: engine.ready && !!workspace && workspace.mode === "windows" && !fullscreen
    readonly property var apps: desktop.groups(monitorName)
    readonly property var appsById: Models.keyed(apps, app => app.id)
    readonly property var hints: hintPopup
    property bool keyboardNavigation: false
    WlrLayershell.keyboardFocus: keyboardNavigation ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.OnDemand
    function focusDock() {
        if (!shown || !apps.length) return;
        keyboardNavigation = true;
        Qt.callLater(function() { appRepeater.itemAt(0).forceActiveFocus(); });
    }
    HyprlandFocusGrab { windows: [root]; active: root.keyboardNavigation; onCleared: root.keyboardNavigation = false }
    anchors { bottom: true; left: true; right: true }
    implicitHeight: 84
    exclusiveZone: shown ? 84 : 0
    visible: shown || surface.opacity > 0
    color: "transparent"
    mask: Region { item: surface }
    Rectangle {
        id: surface
        Keys.onEscapePressed: root.keyboardNavigation = false
        width: Math.min(parent.width - 24, iconRow.implicitWidth + 22)
        height: 68
        x: Math.round((parent.width - width) / 2)
        y: parent.height - height - Theme.dockBottom + (root.shown ? 0 : 10)
        radius: Theme.dockRadius
        color: Theme.surface
        border.width: 1; border.color: Theme.border
        opacity: root.shown ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: root.indicators.reducedMotion ? 0 : Theme.motionDuration } }
        Behavior on y { NumberAnimation { duration: root.indicators.reducedMotion ? 0 : Theme.motionDuration; easing.type: Easing.OutCubic } }
        ScrollView {
            id: scroll
            anchors.fill: parent; anchors.leftMargin: 11; anchors.rightMargin: 11; anchors.topMargin: 8; anchors.bottomMargin: 4
            contentWidth: iconRow.implicitWidth
            contentHeight: 54
            ScrollBar.horizontal: ShellScrollBar { orientation: Qt.Horizontal }
            ScrollBar.vertical.policy: ScrollBar.AlwaysOff
            Row {
                id: iconRow
                spacing: Theme.dockGap
                Repeater {
                    id: appRepeater
                    model: ScriptModel { values: root.apps.map(app => app.id) }
                    delegate: ShellButton {
                        id: dockButton
                        required property string modelData
                        readonly property var app: root.appsById[modelData] || ({id: modelData, name: modelData, icon: "", windows: [],
                            pinned: false, available: false, running: false, active: false, lastWindow: null})
                        property int pinIndex: root.desktop.pinned.indexOf(app.id)
                        property int dropIndex: -1
                        property bool launchFlash: false
                        width: Theme.dockIconSize; height: Theme.dockIconSize
                        hintBelow: false
                        hint: app.name + (!app.available && !app.running ? " · не установлено" : app.windows.length > 1 ? " · окон: " + app.windows.length + " · колесо — переключить" : "")
                        emphasized: app.active
                        scale: hovered ? Theme.hoverScale : launchFlash ? 0.94 : 1
                        transform: Translate { y: dockButton.hovered ? -Theme.hoverLift : 0; Behavior on y { NumberAnimation { duration: root.indicators.reducedMotion ? 0 : Theme.hoverDuration } } }
                        Behavior on scale { NumberAnimation { duration: root.indicators.reducedMotion ? 0 : Theme.hoverDuration; easing.type: Easing.OutCubic } }
                        onClicked: { root.keyboardNavigation = false; root.desktop.activate(app, root.monitorName); launchFlash = true; response.restart(); }
                        Image {
                            id: appIcon
                            anchors.centerIn: parent
                            width: 27; height: 27
                            source: Quickshell.iconPath(dockButton.app.icon, true)
                            sourceSize.width: 48; sourceSize.height: 48
                            opacity: dockButton.app.available || dockButton.app.running ? 1 : 0.4
                        }
                        Text {
                            anchors.centerIn: parent
                            text: "\uf2d0"
                            font.family: Theme.icons; font.pixelSize: Theme.dockGlyphSize
                            color: dockButton.app.available || dockButton.app.running ? Theme.text : Theme.muted
                            visible: appIcon.status !== Image.Ready
                        }
                        Rectangle {
                            anchors.top: parent.bottom; anchors.topMargin: 5; anchors.horizontalCenter: parent.horizontalCenter
                            width: dockButton.app.windows.length > 1 ? 10 : 4; height: 4; radius: 2
                            color: dockButton.app.active ? Theme.text : Theme.accent
                            visible: dockButton.app.running
                        }
                        Timer { id: response; interval: 300; onTriggered: dockButton.launchFlash = false }
                        // Положение читается при открытии меню: mapToItem не следит за прокруткой дока.
                        function openMenu() {
                            var point = mapToItem(root.contentItem, 0, 0);
                            menu.popupX = Math.max(12, Math.min(root.width - menu.width - 12, point.x));
                            menu.popupY = (root.screen ? root.screen.height : 1080) - root.height + point.y - menu.height - 10;
                            menu.open(modelData);
                        }
                        TapHandler { acceptedButtons: Qt.RightButton; onTapped: dockButton.openMenu() }
                        // Средняя кнопка закрывает одно окно — самое недавнее, а не всё приложение.
                        TapHandler {
                            acceptedButtons: Qt.MiddleButton
                            enabled: dockButton.app.running
                            onTapped: root.desktop.closeWindow(dockButton.app.lastWindow)
                        }
                        // Колесо перебирает окна приложения на этом мониторе.
                        WheelHandler {
                            property real accumulated: 0
                            enabled: dockButton.app.windows.length > 1
                            onWheel: event => {
                                accumulated += event.angleDelta.y || event.angleDelta.x;
                                if (Math.abs(accumulated) < 120) return;
                                root.desktop.cycle(dockButton.app, accumulated > 0 ? 1 : -1);
                                accumulated = 0;
                            }
                        }
                        Keys.onMenuPressed: openMenu()
                        Keys.onLeftPressed: event => { if ((event.modifiers & Qt.AltModifier) && pinIndex > 0) { root.desktop.movePin(pinIndex, pinIndex - 1); event.accepted = true; } else event.accepted = false; }
                        Keys.onRightPressed: event => { if ((event.modifiers & Qt.AltModifier) && pinIndex >= 0 && pinIndex < root.desktop.pinned.length - 1) { root.desktop.movePin(pinIndex, pinIndex + 1); event.accepted = true; } else event.accepted = false; }
                        Item {
                            id: ghost
                            width: dockButton.width; height: dockButton.height
                            visible: dragHandler.active
                            Drag.active: dragHandler.active
                            Drag.source: dockButton
                            Drag.hotSpot.x: width / 2; Drag.hotSpot.y: height / 2
                            Image { anchors.fill: parent; source: Quickshell.iconPath(dockButton.app.icon, true); opacity: 0.7 }
                        }
                        DragHandler {
                            id: dragHandler
                            target: ghost
                            enabled: dockButton.app.pinned && !root.desktop.saving
                            onActiveChanged: {
                                if (active) dockButton.dropIndex = -1;
                                else {
                                    if (dockButton.dropIndex >= 0) root.desktop.movePin(dockButton.pinIndex, dockButton.dropIndex);
                                    ghost.x = 0; ghost.y = 0;
                                }
                            }
                        }
                        DropArea {
                            anchors.fill: parent
                            enabled: dockButton.pinIndex >= 0
                            onEntered: drag => { if (drag.source && drag.source.pinIndex >= 0) drag.source.dropIndex = dockButton.pinIndex; }
                            onExited: { if (drag.source && drag.source.dropIndex === dockButton.pinIndex) drag.source.dropIndex = -1; }
                        }
                    }
                }
            }
        }
    }
    HintPopup { id: hintPopup }
    // Одно контекстное меню на док; привязано к ID приложения, для которого открыто.
    ShellPopup {
        id: menu
        readonly property var app: root.appsById[currentName] || null
        readonly property int pinIndex: root.desktop.pinned.indexOf(currentName)
        parentPanel: root
        implicitWidth: 260
        implicitHeight: menuItems.implicitHeight + 24
        onPresented: newWindowItem.forceActiveFocus()
        onAppChanged: { if (opened && !app) close(); }
        Column {
            id: menuItems
            width: parent.width
            spacing: 2
            ShellMenuItem { id: newWindowItem; width: parent.width; text: "Новое окно"; enabled: !!menu.app && menu.app.available; onTriggered: { root.desktop.newWindow(menu.currentName, root.monitorName); menu.close(); } }
            ShellMenuItem { width: parent.width; text: menu.pinIndex >= 0 ? "Открепить" : "Закрепить"; enabled: !root.desktop.saving; onTriggered: { root.desktop.togglePin(menu.currentName); menu.close(); } }
            Rectangle { width: parent.width; height: 1; color: Theme.border }
            ShellMenuItem { width: parent.width; text: "Сдвинуть влево · Alt+←"; enabled: menu.pinIndex > 0 && !root.desktop.saving; onTriggered: { root.desktop.movePin(menu.pinIndex, menu.pinIndex - 1); menu.close(); } }
            ShellMenuItem { width: parent.width; text: "Сдвинуть вправо · Alt+→"; enabled: menu.pinIndex >= 0 && menu.pinIndex < root.desktop.pinned.length - 1 && !root.desktop.saving; onTriggered: { root.desktop.movePin(menu.pinIndex, menu.pinIndex + 1); menu.close(); } }
            Rectangle { width: parent.width; height: 1; color: Theme.border }
            ShellMenuItem { width: parent.width; text: "Закрыть окно · средняя кнопка"; enabled: !!menu.app && menu.app.running; onTriggered: { root.desktop.closeWindow(menu.app.lastWindow); menu.close(); } }
            ShellMenuItem { width: parent.width; text: "Выйти"; enabled: !!menu.app && menu.app.running; onTriggered: { root.desktop.quit(menu.currentName); menu.close(); } }
        }
    }
    onShownChanged: { if (!shown) { keyboardNavigation = false; menu.close(); } }
}
