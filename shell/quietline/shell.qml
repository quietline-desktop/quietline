import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import "services"
import "system"
import "settings"
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
    BluetoothService { id: bluetoothService }
    PowerService { id: powerService }
    // Системные сервисы, общие для всех панелей, всплывающих окон и окна «Настройки».
    readonly property var services: ({network: networkService, audio: audioService, brightness: brightnessService,
                                      bluetooth: bluetoothService, power: powerService, settings: settingsWindow})
    SettingsWindow { id: settingsWindow; services: root.services; desktop: desktopService }
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
                error: windowEngine.message || desktopService.errorMessage, reducedMotion: systemIndicators.reducedMotion,
                pinned: desktopService.pinned, windows: desktopService.windows,
                screens: root.surfaces.map(item => ({name: item.bar.monitorName,
                    mode: item.dock.workspace ? item.dock.workspace.mode : null,
                    dockVisible: item.dock.visible, dockReserved: item.dock.exclusiveZone,
                    barHeight: item.bar.implicitHeight, applicationsOpen: item.bar.applicationsOpen, summaryOpen: item.bar.summaryOpen, apps: item.dock.apps.map(app => ({id:app.id, count:app.windows.length, last:app.lastWindow ? app.lastWindow.address : null}))}))});
        }
        function launcher(): void {
            var name = Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : "";
            var item = root.surfaces.find(item => item.bar.monitorName === name) || root.surfaces[0];
            if (item) item.bar.openApplications();
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
        // Окно «Настройки» на разделе `section` (`network`, `audio`, `display`, `bluetooth`,
        // `power`, `keyboard`, `shortcuts`, `about`); пусто — последний открытый раздел.
        function settings(section: string): void { settingsWindow.open(section); }
    }
}
