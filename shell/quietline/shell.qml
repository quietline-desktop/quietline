//@ pragma Env QML_DISABLE_DISTANCEFIELD=1
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import "services"
import "system"
import "settings/window"
import "session"
import "notifications"
import "osd"
import "clipboard"
import "search"
import "bar"
import "dock"
import "logic/Models.js" as Models

// Корень оболочки Quietline: панель и док на каждом экране, IPC `quietline` для клавиш и проверок.
ShellRoot {
    id: root
    property var surfaces: []
    EngineClient { id: windowEngine }
    DesktopModel { id: desktopService }
    Indicators { id: systemIndicators }
    NetworkService { id: networkService }
    AudioService { id: audioService }
    BrightnessService { id: brightnessService }
    DisplayService { id: displayService }
    BluetoothService { id: bluetoothService }
    PowerService { id: powerService }
    KeepAwake { id: keepAwakeService }
    SessionService { id: sessionService }
    ClipboardService { id: clipboardService }
    SearchService { id: searchService }
    // Центр уведомлений открыт хотя бы на одной панели; отключённый монитор уносит своё состояние.
    NotificationService { id: notificationService; centerOpen: root.surfaces.some(item => item.bar.notificationsOpen) }
    NotificationPopups { service: notificationService }
    // Системные сервисы, общие для всех панелей, всплывающих окон и окна «Настройки».
    readonly property var services: ({network: networkService, audio: audioService, brightness: brightnessService, display: displayService,
                                      bluetooth: bluetoothService, power: powerService, keepAwake: keepAwakeService, notifications: notificationService, session: sessionService, clipboard: clipboardService, search: searchService, settings: settingsWindow})
    SettingsWindow { id: settingsWindow; services: root.services; desktop: desktopService }
    Osd { id: osdWindow; services: root.services; desktop: desktopService; indicators: systemIndicators }
    Variants {
        model: Quickshell.screens
        Scope {
            id: output
            required property var modelData
            TopBar { id: topbar; screen: output.modelData; engine: windowEngine; desktop: desktopService; indicators: systemIndicators; services: root.services }
            Dock { id: dock; screen: output.modelData; engine: windowEngine; desktop: desktopService; indicators: systemIndicators }
            Component.onCompleted: root.surfaces = root.surfaces.concat([{owner: output, bar: topbar, dock: dock}])
            Component.onDestruction: root.surfaces = root.surfaces.filter(item => item.owner !== output)
        }
    }
    IpcHandler {
        target: "quietline"
        function status(): string {
            return JSON.stringify({ready: windowEngine.ready, revision: windowEngine.revision, busy: windowEngine.busy,
                error: windowEngine.message || desktopService.errorMessage, reducedMotion: systemIndicators.reducedMotion, keepAwake: keepAwakeService.active,
                notifications: {count: notificationService.history.length, unread: notificationService.unread, dnd: notificationService.dnd},
                pinned: desktopService.pinned, windows: desktopService.windows,
                screens: root.surfaces.map(item => ({name: item.bar.monitorName,
                    mode: item.dock.workspace ? item.dock.workspace.mode : null,
                    dockVisible: item.dock.visible, dockRevealed: item.dock.revealed,
                    barHeight: item.bar.implicitHeight, applicationsOpen: item.bar.applicationsOpen, summaryOpen: item.bar.summaryOpen, apps: item.dock.apps.map(app => ({id:app.id, count:app.windows.length, last:app.lastWindow ? app.lastWindow.address : null}))}))});
        }
        // `Super+Space`: поиск на мониторе с фокусом; повторный вызов закрывает его.
        function launcher(): void {
            var name = Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : "";
            var item = root.surfaces.find(item => item.bar.monitorName === name) || root.surfaces[0];
            if (item) item.bar.toggleApplications();
        }
        function focusDock(): void {
            var name = Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : "";
            var item = root.surfaces.find(item => item.bar.monitorName === name) || root.surfaces[0];
            if (item) item.dock.focusDock();
        }
        // `monitor` — имя разъёма или ключ монитора движка.
        function toggle(monitor: string): void {
            var key = Models.monitorKey(windowEngine.state, monitor);
            if (key) windowEngine.toggle(key);
        }
        function showApplications(monitor: string): void {
            var item = root.surfaces.find(item => item.bar.monitorName === monitor);
            if (item) item.bar.openApplications();
        }
        function showSummary(monitor: string): void {
            var item = root.surfaces.find(item => item.bar.monitorName === monitor);
            if (item) item.bar.openSummary();
        }
        function movePin(from: int, to: int): void { desktopService.movePin(from, to); }
        // `Super+V`: история буфера на мониторе с фокусом; повторный вызов закрывает её.
        function clipboard(): void {
            var name = Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : "";
            var item = root.surfaces.find(item => item.bar.monitorName === name) || root.surfaces[0];
            if (item) item.bar.toggleClipboard();
        }
        // `Super+Shift+Q`: подтверждение принудительного завершения активного окна на мониторе с фокусом.
        function confirmKill(): void {
            var name = Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : "";
            var item = root.surfaces.find(item => item.bar.monitorName === name) || root.surfaces[0];
            if (item) item.bar.confirmKill(desktopService.windows.find(window => window.activated) || null);
        }
        // Окно «Настройки» на разделе `section` (`network`, `audio`, `display`, `bluetooth`,
        // `power`, `region`, `shortcuts`, `about`; `keyboard` открывает `region`); пусто — последний открытый раздел.
        function settings(section: string): void { settingsWindow.open(section); }
        // `Super+N`: центр уведомлений на мониторе с фокусом.
        function notifications(): void {
            var name = Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : "";
            var item = root.surfaces.find(item => item.bar.monitorName === name) || root.surfaces[0];
            if (item) item.bar.toggleNotifications();
        }
        // «Не беспокоить»: `on`, `off` или `toggle`.
        function dnd(action: string): void {
            notificationService.setDnd(action === "toggle" ? !notificationService.dnd : action === "on");
        }
        // Клавиши яркости после `brightnessctl`: перечитать яркость и показать индикатор (`brightness`).
        function osd(kind: string): void { if (kind === "brightness") brightnessService.refresh(); }
    }
}
