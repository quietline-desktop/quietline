import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import "../logic/Models.js" as Models

// Окна Hyprland, приложения из desktop entries, закрепления дока и раскладка клавиатуры.
Scope {
    id: root
    property var pinned: ["org.kde.dolphin", "google-chrome", "code", "com.mitchellh.ghostty", "org.telegram.desktop"]
    property string errorMessage: ""
    property string notice: ""
    property bool saving: true
    property var keyboard: null
    property var xkbNames: ({})
    readonly property string keyboardLayout: Models.layoutCode(keyboard, xkbNames)
    readonly property string keyboardLayoutName: keyboard ? keyboard.active_keymap : ""
    property var pendingPins: []
    property bool pinsLoaded: false
    property bool preferencesAnswered: false
    readonly property var entries: DesktopEntries.applications.values.filter(entry => !entry.noDisplay).map(entry => ({
        id: entry.id, name: entry.name, icon: entry.icon, startupClass: entry.startupClass
    })).sort((a, b) => a.name.localeCompare(b.name))
    readonly property var windows: Hyprland.toplevels.values.map(window => {
        var data = window.lastIpcObject || {};
        return {address: window.address, appId: window.wayland ? window.wayland.appId : data.class,
                className: data.class || "", title: window.title,
                monitor: window.monitor ? window.monitor.name : "", workspace_id: window.workspace ? window.workspace.id : -1,
                activated: window.activated, fullscreen: data.fullscreen || 0,
                focusHistoryID: data.focusHistoryID, mapped: data.mapped !== false, hidden: data.hidden || false};
    })
    function groups(name) { return Models.groupApps(windows, name, pinned, entries); }
    function entryFor(id) { return DesktopEntries.byId(id); }
    function focusMonitor(name) {
        if (/^[A-Za-z0-9_.:-]+$/.test(name || "")) Hyprland.dispatch('hl.dsp.focus({monitor="' + name + '"})');
    }
    function launch(id, monitor) {
        var entry = entryFor(id);
        if (!entry) { errorMessage = "Приложение не установлено"; return; }
        errorMessage = "";
        focusMonitor(monitor);
        entry.execute();
    }
    function focusWindow(window) {
        var selector = window ? Models.windowSelector(window.address) : null;
        if (selector) Hyprland.dispatch('hl.dsp.focus({window="' + selector + '"})');
    }
    function activate(group, monitor) {
        if (group.windows.length) focusWindow(Models.clickTarget(group));
        else launch(group.id, monitor);
    }
    function cycle(group, direction) { focusWindow(Models.cycleTarget(group, direction)); }
    function closeWindow(window) {
        var selector = window ? Models.windowSelector(window.address) : null;
        if (selector) Hyprland.dispatch('hl.dsp.window.close({window="' + selector + '"})');
    }
    function newWindow(id, monitor) {
        var entry = entryFor(id);
        if (!entry) { errorMessage = "Приложение не установлено"; return; }
        focusMonitor(monitor);
        var action = entry.actions.find(action => action.id === "new-window" || action.id === "new-empty-window");
        if (action) action.execute();
        else entry.execute();
    }
    function quit(id) {
        var targets = windows.filter(window => {
            var entry = Models.desktopFor(window.appId || window.className, entries);
            return entry ? entry.id === id : Models.normalizedId(window.appId || window.className) === id;
        });
        targets.forEach(window => {
            var selector = Models.windowSelector(window.address);
            if (selector) Hyprland.dispatch('hl.dsp.window.close({window="' + selector + '"})');
        });
        notice = targets.length ? "Запрос выхода отправлен. Сохраните документы в открытых окнах." : "У приложения нет открытых окон";
    }
    function savePins(ids) {
        if (saving) return;
        pendingPins = ids;
        saving = true;
        preferences.command = ["quietline-shell", "pins", "--set", JSON.stringify(ids)];
        preferences.running = true;
    }
    function togglePin(id) {
        var ids = pinned.slice(), index = ids.indexOf(id);
        if (index < 0) ids.push(id); else ids.splice(index, 1);
        savePins(ids);
    }
    function movePin(from, to) { savePins(Models.movePin(pinned, from, to)); }
    function switchLayout() { Quickshell.execDetached(["hyprctl", "switchxkblayout", "all", "next"]); }
    function receivePreferences(text) {
        preferencesAnswered = true;
        var action = pinsLoaded ? "сохранить" : "загрузить";
        try {
            var response = JSON.parse(text);
            if (response.error) { errorMessage = "Не удалось " + action + " закрепления: " + response.error; return; }
            if (Array.isArray(response.pinned)) { pinned = response.pinned; pinsLoaded = true; errorMessage = ""; }
        } catch (_) { errorMessage = "Не удалось " + action + " закреплённые приложения"; }
    }
    Process {
        id: preferences
        command: ["quietline-shell", "pins"]
        running: true
        stdout: StdioCollector { onStreamFinished: root.receivePreferences(text) }
        // Незапустившийся процесс не выдаёт exited, поэтому завершение отслеживается по running.
        onRunningChanged: {
            if (running) { root.preferencesAnswered = false; return; }
            Qt.callLater(function() {
                root.saving = false;
                if (!root.preferencesAnswered && !root.errorMessage)
                    root.errorMessage = "Не удалось " + (root.pinsLoaded ? "сохранить" : "загрузить") + " закреплённые приложения: quietline-shell не ответил";
            });
        }
    }
    Process {
        id: keyboards
        command: ["hyprctl", "-j", "devices"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var items = JSON.parse(text).keyboards || [];
                    root.keyboard = items.find(item => item.main) || items[0] || null;
                } catch (_) { root.keyboard = null; }
            }
        }
    }
    FileView {
        path: Quickshell.env("QUIETLINE_XKB_RULES") || "/usr/share/X11/xkb/rules/base.lst"
        printErrors: false
        onLoaded: root.xkbNames = Models.parseXkbRules(text())
    }
    Connections {
        target: Hyprland
        function onRawEvent(event) {
            if (event.name === "activelayout" && !keyboards.running) keyboards.running = true;
            if (["fullscreen", "activewindowv2", "movewindowv2", "openwindow", "closewindow"].indexOf(event.name) >= 0) Hyprland.refreshToplevels();
        }
    }
    Timer { interval: 6000; running: root.notice.length > 0; onTriggered: root.notice = "" }
}
