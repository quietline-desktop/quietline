import QtQuick
import Quickshell
import Quickshell.Io
import ".."
import "../logic/Models.js" as Models

// Состояние NetworkManager для панели, сетевой панели и страницы «Сеть» окна «Настройки».
// Действия идут по одному через `quietline-shell network`; пароль и профиль — только через stdin.
// Ответ на действие обновляет состояние повторным `network status`.
Scope {
    id: root
    property var devices: []
    property var profiles: []
    property var wifi: ({enabled: false})
    // Сигнал активной точки Wi‑Fi 0–100 или `null`.
    property var wifiSignal: null
    property var networks: []
    property bool busy: false
    property bool scanning: false
    // Ошибка последнего действия держится до следующего; ошибка опроса состояния — до удачного опроса.
    property string errorMessage: ""
    property string statusError: ""
    property string notice: ""
    // Неподтверждённая конфигурация: `{checkpoint, deadline}`, `deadline` — мс или `null` после перезапуска оболочки.
    property var pending: null
    property real now: Date.now()
    readonly property int secondsLeft: pending && pending.deadline ? Models.secondsLeft(pending.deadline, now) : -1
    readonly property var ethernet: devices.filter(device => device.type === "ethernet")
    readonly property var wifiDevice: devices.find(device => device.type === "wifi") || null
    readonly property bool connected: devices.some(device => Models.deviceLabel(device, Lang.s) === Lang.s.deviceConnected)
    readonly property bool wifiConnected: !!wifiDevice && Models.deviceLabel(wifiDevice, Lang.s) === Lang.s.deviceConnected
    // Подсказка значка сети: активные интерфейсы, профиль и адреса.
    readonly property string summary: {
        var lines = devices.filter(device => device.state === "connected" || device.state === "connecting")
            .map(device => device.device + (device.profile ? " · " + device.profile : "") + " · "
                 + (device.addresses.length ? device.addresses.join(", ") : Models.deviceLabel(device, Lang.s)));
        return lines.join("\n") || statusError || Lang.s.networkNone;
    }
    // Вид последнего запущенного действия (`scan`, `connect`, `save`, `apply`…).
    property string lastAction: ""
    // Номер завершённого действия: опрос, начатый до конца действия, устарел и не применяется.
    property int actionGeneration: 0
    property bool refreshQueued: false
    signal profileSaved()

    // Опрос во время другого опроса ставится в очередь и выполняется сразу после него.
    function refresh() {
        if (statusProcess.running) { refreshQueued = true; return; }
        statusProcess.generation = actionGeneration;
        statusProcess.running = true;
    }
    // Без связи с NetworkManager устройства не показываются: прежнее «Подключено» было бы ложным.
    function statusFailed(text) {
        statusError = text;
        devices = [];
    }
    function run(args, input, kind) {
        if (busy) return false;
        busy = true;
        lastAction = kind;
        errorMessage = "";
        notice = "";
        action.kind = kind;
        action.payload = input === undefined ? null : input;
        action.answered = false;
        action.stdinEnabled = input !== undefined;
        action.command = ["quietline-shell", "network"].concat(args);
        action.running = true;
        return true;
    }
    function scanWifi() { if (run(["wifi-scan"], undefined, "scan")) scanning = true; }
    function setWifi(on) { run(["wifi-radio", on ? "--on" : "--off"], undefined, "radio"); }
    function connectWifi(ssid, password, device) {
        run(["wifi-connect", "--ssid", ssid].concat(device ? ["--device", device] : []), (password || "") + "\n", "connect");
    }
    function saveProfile(profile) { run(["profile-save"], JSON.stringify(profile), "save"); }
    function deleteProfile(uuid) { run(["profile-delete", "--uuid", uuid], undefined, "delete"); }
    function apply(uuid, device) { run(["apply", "--uuid", uuid, "--device", device], undefined, "apply"); }
    function useDhcp(device) { run(["dhcp", "--device", device], undefined, "apply"); }
    function keep() { if (pending) run(["confirm", "--checkpoint", pending.checkpoint], undefined, "confirm"); }
    function revert() { if (pending) run(["rollback", "--checkpoint", pending.checkpoint], undefined, "rollback"); }

    function finish(text, kind) {
        var data;
        try { data = JSON.parse(text); }
        catch (_) { errorMessage = Models.networkErrorText(kind, {error: "quietline-shell returned no JSON"}, Lang.s); return; }
        if (data.error) { errorMessage = Models.networkErrorText(kind, data, Lang.s); return; }
        if (kind === "scan") networks = data.networks || [];
        else if (kind === "apply") {
            // Срок в панели на секунду раньше срока отката NetworkManager.
            pending = {checkpoint: data.checkpoint, deadline: Date.now() + (data.timeout - 1) * 1000};
            notice = Lang.s.networkApplied;
        } else if (kind === "confirm") notice = Lang.s.networkSaved;
        else if (kind === "rollback") notice = Lang.s.networkRolledBack;
        else if (kind === "save") { notice = Lang.f(Lang.s.networkProfileSaved, data.profile.name); profileSaved(); }
        if (kind === "confirm" || kind === "rollback") pending = null;
    }

    Process {
        id: action
        property string kind: ""
        property var payload: null
        property bool answered: false
        onStarted: { if (payload !== null) { write(payload); stdinEnabled = false; } }
        stdout: StdioCollector {
            onStreamFinished: { action.answered = true; root.finish(text, action.kind); }
        }
        // Незапустившийся процесс не даёт сигнала завершения, поэтому итог подводится по `running`.
        onRunningChanged: {
            if (running) return;
            Qt.callLater(function() {
                if (!action.answered) root.errorMessage = Models.networkErrorText(action.kind, {error: "quietline-shell did not respond"}, Lang.s);
                if (action.kind === "scan") root.scanning = false;
                action.payload = null;
                root.actionGeneration += 1;
                root.busy = false;
                root.refresh();
            });
        }
    }
    Process {
        id: statusProcess
        property bool answered: false
        property int generation: 0
        command: ["quietline-shell", "network", "status"]
        running: true
        onRunningChanged: {
            if (running) { answered = false; return; }
            Qt.callLater(function() {
                if (!statusProcess.answered) root.statusFailed(Models.networkErrorText("status", {error: "quietline-shell did not respond"}, Lang.s));
                if (root.refreshQueued) { root.refreshQueued = false; root.refresh(); }
            });
        }
        stdout: StdioCollector {
            onStreamFinished: {
                statusProcess.answered = true;
                if (statusProcess.generation !== root.actionGeneration || root.busy) { root.refreshQueued = true; return; }
                var data;
                try { data = JSON.parse(text); }
                catch (_) { root.statusFailed(Models.networkErrorText("status", {error: "quietline-shell returned no JSON"}, Lang.s)); return; }
                if (data.error) { root.statusFailed(Models.networkErrorText("status", data, Lang.s)); return; }
                root.statusError = "";
                var hadDeadline = root.pending && root.pending.deadline;
                root.devices = data.devices || [];
                root.profiles = data.profiles || [];
                root.wifi = data.wifi || {enabled: false};
                root.wifiSignal = typeof data.wifiSignal === "number" ? data.wifiSignal : null;
                root.pending = Models.pendingFromStatus(data, root.pending);
                if (hadDeadline && !root.pending) root.notice = Lang.s.networkConfirmExpired;
            }
        }
    }
    Timer { interval: 5000; repeat: true; running: true; onTriggered: root.refresh() }
    Timer {
        interval: 250; repeat: true
        running: !!root.pending && !!root.pending.deadline
        onTriggered: {
            root.now = Date.now();
            if (root.secondsLeft === 0) Qt.callLater(root.refresh);
        }
    }
}
