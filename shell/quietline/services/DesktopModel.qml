import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import ".."
import "../logic/Models.js" as Models

// Окна Hyprland, приложения из desktop entries, закрепления дока и раскладка клавиатуры.
Scope {
    id: root
    property var pinned: ["org.kde.dolphin", "google-chrome", "code", "com.mitchellh.ghostty", "org.telegram.desktop"]
    property string errorMessage: ""
    property string notice: ""
    // Идёт запись экрана (событие Hyprland `screencast`); до первого события после старта — `false`.
    property bool screencast: false
    property bool saving: true
    property var keyboard: null
    property var xkbNames: ({})
    readonly property string keyboardLayout: Models.layoutCode(keyboard, xkbNames, Lang.s)
    readonly property string keyboardLayoutName: keyboard ? keyboard.active_keymap : ""
    property var pendingPins: []
    property bool pinsLoaded: false
    property bool preferencesAnswered: false
    readonly property var entries: DesktopEntries.applications.values.filter(entry => !entry.noDisplay).map(entry => ({
        id: entry.id, name: entry.name, icon: entry.icon, startupClass: entry.startupClass
    })).sort((a, b) => a.name.localeCompare(b.name))
    // `activated` — окно с фокусом на видимом пространстве своего монитора: на пустом
    // пространстве ни одно окно не активно, хотя у прежнего окна флаг `activated` остаётся.
    // Флаг IPC Hyprland появляется только с первым событием фокуса, поэтому учитывается и
    // состояние Wayland-окна (foreign-toplevel), известное сразу после запуска оболочки.
    readonly property var windows: Hyprland.toplevels.values.map(window => {
        var data = window.lastIpcObject || {};
        var visible = !!window.monitor && !!window.workspace && window.monitor.activeWorkspace === window.workspace;
        return {address: window.address, appId: window.wayland ? window.wayland.appId : data.class,
                className: data.class || "", title: window.title,
                monitor: window.monitor ? window.monitor.name : "", workspace_id: window.workspace ? window.workspace.id : -1,
                activated: (window.activated || (!!window.wayland && window.wayland.activated)) && visible, fullscreen: data.fullscreen || 0,
                focusHistoryID: data.focusHistoryID, mapped: data.mapped !== false, hidden: data.hidden || false,
                pid: data.pid || -1,
                minimized: !!window.workspace && window.workspace.name === Models.MINIMIZED_WORKSPACE};
    })
    function groups(name) { return Models.groupApps(windows, name, pinned, entries, Lang.s); }
    function entryFor(id) { return DesktopEntries.byId(id); }
    function focusMonitor(name) {
        if (/^[A-Za-z0-9_.:-]+$/.test(name || "")) Hyprland.dispatch('hl.dsp.focus({monitor="' + name + '"})');
    }
    // Приложение запускается в своей группе процессов `app-quietline-*`: по ней
    // `quietline-shell app quit` завершает процесс, оставшийся без окон.
    function run(id, command, workingDirectory) {
        var line = Models.launchCommand(command, Models.scopeUnit(id, Math.random().toString(36).slice(2, 10)));
        if (!line) { errorMessage = Lang.s.desktopNoLaunch; return; }
        Quickshell.execDetached({command: line, workingDirectory: workingDirectory});
    }
    function launch(id, monitor) {
        var entry = entryFor(id);
        if (!entry) { errorMessage = Lang.s.desktopNotInstalled; return; }
        errorMessage = "";
        focusMonitor(monitor);
        run(id, entry.command, entry.workingDirectory);
    }
    function focusWindow(window) {
        var selector = window ? Models.windowSelector(window.address) : null;
        if (selector) Hyprland.dispatch('hl.dsp.focus({window="' + selector + '"})');
    }
    // Свёрнутое окно возвращается на активное пространство монитора `monitor` и получает фокус.
    function activate(group, monitor) {
        if (!group.windows.length) { launch(group.id, monitor); return; }
        var target = Models.clickTarget(group);
        if (target && target.minimized) restore(target, monitor);
        else focusWindow(target);
    }
    function minimize(window) {
        var selector = window ? Models.windowSelector(window.address) : null;
        if (selector) Hyprland.dispatch('hl.dsp.window.move({window="' + selector + '", workspace="' + Models.MINIMIZED_WORKSPACE + '", follow=false})');
    }
    function restore(window, monitor) {
        var selector = window ? Models.windowSelector(window.address) : null;
        var output = Hyprland.monitors.values.find(item => item.name === monitor) || Hyprland.focusedMonitor;
        var workspace = output && output.activeWorkspace ? output.activeWorkspace.id : null;
        if (!selector || !Number.isInteger(workspace) || workspace <= 0) return;
        Hyprland.dispatch('hl.dsp.window.move({window="' + selector + '", workspace=' + workspace + ', follow=false})');
        focusWindow(window);
    }
    // Разворачивает окно на рабочую область или возвращает прежний размер; окно сначала получает фокус.
    function toggleMaximize(window) {
        if (!window) return;
        focusWindow(window);
        Hyprland.dispatch('hl.dsp.window.fullscreen({ mode = "maximized", action = "toggle" })');
    }
    function cycle(group, direction) { focusWindow(Models.cycleTarget(group, direction)); }
    function closeWindow(window) {
        var selector = window ? Models.windowSelector(window.address) : null;
        if (selector) Hyprland.dispatch('hl.dsp.window.close({window="' + selector + '"})');
    }
    function newWindow(id, monitor) {
        var entry = entryFor(id);
        if (!entry) { errorMessage = Lang.s.desktopNotInstalled; return; }
        focusMonitor(monitor);
        var action = entry.actions.find(action => action.id === "new-window" || action.id === "new-empty-window");
        run(id, action ? action.command : entry.command, entry.workingDirectory);
    }
    function quit(id) {
        var targets = windows.filter(window => {
            var entry = Models.desktopFor(window.appId || window.className, entries);
            return entry ? entry.id === id : Models.normalizedId(window.appId || window.className) === id;
        });
        // Окна закрываются по процессам: процесс, оставшийся без окон, завершает `app quit`.
        targets.map(window => window.pid).filter((pid, index, pids) => pid > 1 && pids.indexOf(pid) === index).forEach(pid => {
            Quickshell.execDetached(["quietline-shell", "app", "quit", "--pid", String(pid), "--notify"]);
        });
        notice = targets.length ? Lang.s.desktopQuitRequested : Lang.s.desktopNoWindows;
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
        var saving = pinsLoaded;
        try {
            var response = JSON.parse(text);
            if (response.error) { errorMessage = Lang.f(saving ? Lang.s.pinsSaveFailed : Lang.s.pinsLoadFailed, response.error); return; }
            if (Array.isArray(response.pinned)) { pinned = response.pinned; pinsLoaded = true; errorMessage = ""; }
        } catch (_) { errorMessage = saving ? Lang.s.pinsSaveFailedApps : Lang.s.pinsLoadFailedApps; }
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
                    root.errorMessage = root.pinsLoaded ? Lang.s.pinsSaveNoReply : Lang.s.pinsLoadNoReply;
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
            if (event.name === "screencast") root.screencast = String(event.data).split(",")[0] === "1";
            if (["fullscreen", "activewindowv2", "movewindowv2", "openwindow", "closewindow"].indexOf(event.name) >= 0) Hyprland.refreshToplevels();
        }
    }
    Timer { interval: 6000; running: root.notice.length > 0; onTriggered: root.notice = "" }
}
