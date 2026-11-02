import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import ".."
import "../controls"
import "../surfaces"
import "../logic/Models.js" as Models

// Док экрана: закреплённые и запущенные на мониторе приложения. Есть только в режиме
// «Окна» без полноэкранного окна и места не резервирует: окна занимают экран до низа.
// Скрыт, пока указатель не коснётся нижнего края (полоса 2 px) или не окажется на доке;
// прячется через 400 мс после ухода. Не прячется при открытом меню, перетаскивании,
// навигации с клавиатуры и на пустом пространстве.
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
    readonly property bool reducedMotion: indicators.reducedMotion
    property bool keyboardNavigation: false
    property bool dragging: false
    // Указатель у края или на доке; после ухода держится ещё 400 мс.
    readonly property bool pointerInside: edgeHover.hovered || surfaceHover.hovered
    property bool hoverHold: false
    readonly property bool revealed: Models.dockRevealed({
        available: shown, hovered: hoverHold, menuOpen: menu.opened, dragging: dragging,
        keyboard: keyboardNavigation, empty: !!workspace && Models.workspaceEmpty(desktop.windows, monitorName, workspace.workspace_id)
    })
    onPointerInsideChanged: {
        if (pointerInside) { hideDelay.stop(); hoverHold = true; }
        else hideDelay.restart();
    }
    Timer { id: hideDelay; interval: 400; onTriggered: root.hoverHold = false }
    WlrLayershell.keyboardFocus: keyboardNavigation ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.OnDemand
    WlrLayershell.namespace: "quietline-dock"
    function focusDock() {
        if (!shown || !apps.length) return;
        keyboardNavigation = true;
        Qt.callLater(function() { appRepeater.itemAt(0).forceActiveFocus(); });
    }
    HyprlandFocusGrab { windows: [root]; active: root.keyboardNavigation; onCleared: root.keyboardNavigation = false }
    anchors { bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    exclusiveZone: 0
    implicitHeight: Theme.dockIconSize + Theme.dockPadding * 2 + Theme.dockBottom + 14
    visible: shown || surface.y < height
    color: "transparent"
    // Скрытый док ловит указатель только полосой у края, показанный — своей поверхностью.
    mask: Region { item: root.revealed ? surface : edge }
    Item {
        id: edge
        anchors.bottom: parent.bottom
        width: parent.width; height: 2
        HoverHandler { id: edgeHover; enabled: root.shown }
    }
    Rectangle {
        id: surface
        Keys.onEscapePressed: root.keyboardNavigation = false
        width: Math.min(parent.width - 24, iconRow.implicitWidth + Theme.dockPadding * 2)
        height: Theme.dockIconSize + Theme.dockPadding * 2 + 2
        x: Math.round((parent.width - width) / 2)
        y: root.revealed ? parent.height - height - Theme.dockBottom : parent.height + 12
        radius: Theme.radiusDock
        color: Theme.dockSurface
        border.width: 1; border.color: Theme.dockBorder
        opacity: root.revealed ? 1 : 0
        Behavior on y { NumberAnimation { duration: root.reducedMotion ? 0 : Theme.slideDuration; easing.type: Easing.OutCubic } }
        Behavior on opacity { NumberAnimation { duration: root.reducedMotion ? 0 : Theme.motionDuration } }
        HoverHandler { id: surfaceHover }
        ScrollView {
            id: scroll
            anchors.fill: parent; anchors.leftMargin: Theme.dockPadding; anchors.rightMargin: Theme.dockPadding; anchors.topMargin: Theme.dockPadding - 1
            contentWidth: iconRow.implicitWidth
            contentHeight: Theme.dockIconSize + 8
            ScrollBar.horizontal: ShellScrollBar { orientation: Qt.Horizontal }
            ScrollBar.vertical.policy: ScrollBar.AlwaysOff
            Row {
                id: iconRow
                spacing: Theme.dockGap
                Repeater {
                    id: appRepeater
                    model: ScriptModel { values: root.apps.map(app => app.id) }
                    delegate: Row {
                        id: slot
                        required property string modelData
                        required property int index
                        readonly property var app: root.appsById[modelData] || ({id: modelData, name: modelData, icon: "", windows: [],
                            pinned: false, running: false, active: false, minimized: false, lastWindow: null})
                        // Разделитель перед первым незакреплённым приложением.
                        readonly property bool separatorBefore: index > 0 && !app.pinned && !!root.apps[index - 1] && root.apps[index - 1].pinned
                        spacing: Theme.dockGap
                        function forceActiveFocus() { dockButton.forceActiveFocus(); }
                        Rectangle {
                            visible: slot.separatorBefore
                            width: 1; height: Theme.dockIconSize - 12
                            y: 6
                            color: Theme.dockSeparator
                        }
                        ShellButton {
                            id: dockButton
                            readonly property var app: slot.app
                            property int pinIndex: root.desktop.pinned.indexOf(app.id)
                            property int dropIndex: -1
                            property bool launchFlash: false
                            width: Theme.dockIconSize; height: Theme.dockIconSize
                            radius: 12
                            hintBelow: false
                            hint: app.name + (app.windows.length > 1 ? " · " + Lang.f(Lang.s.dockWindows, app.windows.length) + " · " + Lang.s.dockWheelHint : "")
                            background: Rectangle {
                                radius: 12
                                color: "transparent"
                                border.width: dockButton.visualFocus ? 2 : 0
                                border.color: Theme.accent
                            }
                            scale: hovered ? Theme.hoverScale : launchFlash ? 0.94 : 1
                            transform: Translate { y: dockButton.hovered ? -Theme.hoverLift : 0; Behavior on y { NumberAnimation { duration: root.reducedMotion ? 0 : Theme.motionDuration; easing.type: Easing.OutCubic } } }
                            Behavior on scale { NumberAnimation { duration: root.reducedMotion ? 0 : Theme.motionDuration; easing.type: Easing.OutCubic } }
                            onClicked: { root.keyboardNavigation = false; root.desktop.activate(app, root.monitorName); launchFlash = true; response.restart(); }
                            contentItem: Item {
                                Image {
                                    id: appIcon
                                    anchors.centerIn: parent
                                    width: Theme.dockIconSize - 4; height: width
                                    source: Quickshell.iconPath(dockButton.app.icon, true)
                                    sourceSize.width: 96; sourceSize.height: 96
                                    smooth: true; mipmap: true
                                }
                                Icon {
                                    anchors.centerIn: parent
                                    name: "apps"
                                    size: 30
                                    visible: appIcon.status !== Image.Ready
                                }
                            }
                            // Точка — приложение запущено; полая — все его окна свёрнуты.
                            Rectangle {
                                anchors.top: parent.bottom; anchors.topMargin: 3; anchors.horizontalCenter: parent.horizontalCenter
                                width: 4; height: 4; radius: 2
                                color: dockButton.app.minimized ? "transparent" : Theme.dockIndicator
                                border.width: dockButton.app.minimized ? 1 : 0
                                border.color: Theme.dockIndicator
                                visible: dockButton.app.running
                            }
                            Timer { id: response; interval: 300; onTriggered: dockButton.launchFlash = false }
                            // Положение читается при открытии меню: mapToItem не следит за прокруткой дока.
                            function openMenu() {
                                var point = mapToItem(root.contentItem, 0, 0);
                                menu.popupX = Math.max(12, Math.min(root.width - menu.panelWidth - 12, point.x + width / 2 - menu.panelWidth / 2));
                                menu.popupY = (root.screen ? root.screen.height : 1080) - root.height + point.y - menu.panelHeight - 12;
                                menu.open(slot.modelData);
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
                                    root.dragging = active;
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
    }
    HintPopup { id: hintPopup }
    // Одно контекстное меню на док; привязано к ID приложения, для которого открыто.
    ShellPopup {
        id: menu
        readonly property var app: root.appsById[currentName] || null
        readonly property int pinIndex: root.desktop.pinned.indexOf(currentName)
        parentPanel: root
        reducedMotion: root.reducedMotion
        padding: 5
        panelWidth: 240
        panelHeight: menuItems.implicitHeight + 10
        fromBottom: true
        onPresented: newWindowItem.forceActiveFocus(root.keyboardNavigation ? Qt.TabFocusReason : Qt.MouseFocusReason)
        onAppChanged: { if (opened && !app) close(); }
        Column {
            id: menuItems
            width: parent.width
            component Separator: Item {
                width: menuItems.width; height: 11
                Rectangle { anchors.centerIn: parent; width: parent.width - 20; height: 1; color: Theme.hairline }
            }
            ShellMenuItem { id: newWindowItem; width: parent.width; symbol: "add"; text: Lang.s.dockNewWindow; enabled: !!menu.app && !!Models.desktopFor(menu.currentName, root.desktop.entries); onTriggered: { root.desktop.newWindow(menu.currentName, root.monitorName); menu.close(); } }
            ShellMenuItem { width: parent.width; symbol: "keep"; text: menu.pinIndex >= 0 ? Lang.s.dockUnpin : Lang.s.dockPin; enabled: !root.desktop.saving; onTriggered: { root.desktop.togglePin(menu.currentName); menu.close(); } }
            Separator {}
            ShellMenuItem { width: parent.width; symbol: "chevron_left"; text: Lang.s.dockMoveLeft; enabled: menu.pinIndex > 0 && !root.desktop.saving; onTriggered: { root.desktop.movePin(menu.pinIndex, menu.pinIndex - 1); menu.close(); } }
            ShellMenuItem { width: parent.width; symbol: "chevron_right"; text: Lang.s.dockMoveRight; enabled: menu.pinIndex >= 0 && menu.pinIndex < root.desktop.pinned.length - 1 && !root.desktop.saving; onTriggered: { root.desktop.movePin(menu.pinIndex, menu.pinIndex + 1); menu.close(); } }
            Separator {}
            ShellMenuItem { width: parent.width; symbol: "close"; text: Lang.s.dockCloseWindow; enabled: !!menu.app && menu.app.running; onTriggered: { root.desktop.closeWindow(menu.app.lastWindow); menu.close(); } }
            ShellMenuItem { width: parent.width; symbol: "logout"; text: Lang.s.dockQuit; enabled: !!menu.app && menu.app.running; onTriggered: { root.desktop.quit(menu.currentName); menu.close(); } }
        }
    }
    onShownChanged: { if (!shown) { keyboardNavigation = false; menu.close(); } }
}
