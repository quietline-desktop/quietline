.pragma library

// Чистые функции оболочки: проверка состояния движка, кнопки пространств, группы дока,
// CPU/RAM, закрепления и раскладка клавиатуры. Используются в QML и в тестах Node.
//
// Состояние движка — `PublicState.to_json()` из src/quietline_engine/controller.py:
// `{revision, monitors: [{key, name, focused, active_workspace_id, active_number, mode}],
// workspaces: [{monitor_key, display_monitor_key, number, workspace_id, mode}], error}`.
// Протокол сокета описан в docstring src/quietline_engine/server.py.

var MODES = ["windows", "tiles"];

function validNumber(value) { return Number.isInteger(value) && value >= 1 && value <= 10; }

// Состояние целиком соответствует контракту движка; иначе оно не заменяет подтверждённое.
function validState(state) {
    if (!state || typeof state !== "object" || !Number.isInteger(state.revision) || state.revision < 0
            || !Array.isArray(state.monitors) || !Array.isArray(state.workspaces)
            || (state.error !== null && typeof state.error !== "string")) return false;
    var keys = Object.create(null);
    for (var monitor of state.monitors) {
        if (!monitor || typeof monitor.key !== "string" || typeof monitor.name !== "string"
                || typeof monitor.focused !== "boolean" || !Number.isInteger(monitor.active_workspace_id)
                || (monitor.active_number !== null && !validNumber(monitor.active_number))
                || (monitor.mode !== null && MODES.indexOf(monitor.mode) < 0)
                || keys[monitor.key]) return false;
        keys[monitor.key] = true;
    }
    var ids = Object.create(null), places = Object.create(null);
    for (var workspace of state.workspaces) {
        if (!workspace || typeof workspace.monitor_key !== "string" || typeof workspace.display_monitor_key !== "string"
                || !validNumber(workspace.number) || !Number.isInteger(workspace.workspace_id)
                || MODES.indexOf(workspace.mode) < 0) return false;
        var place = workspace.monitor_key + "\n" + workspace.number;
        if (ids[workspace.workspace_id] || places[place]) return false;
        ids[workspace.workspace_id] = true;
        places[place] = true;
    }
    return true;
}

// Текст ошибки ответа движка для панели: по коду из протокола, с подробностью от движка.
var ERROR_TEXTS = {
    invalid_number: "Нет такого пространства: номера от 1 до 10",
    command_failed: "Сервис окон не выполнил команду",
    invalid_request: "Сервис окон не принял команду",
    unknown_method: "Сервис окон не знает эту команду",
    internal_error: "Внутренняя ошибка сервиса окон"
};

function errorText(error) {
    var code = error && typeof error.code === "string" ? error.code : "";
    var detail = error && typeof error.message === "string" ? error.message : "";
    if (code === "invalid_number") return ERROR_TEXTS.invalid_number;
    var text = ERROR_TEXTS[code] || "Команда не выполнена";
    return detail ? text + ": " + detail : text;
}

// Ошибка последней команды или сверки из подтверждённого состояния.
function stateError(state) { return state && state.error ? "Ошибка сервиса окон: " + state.error : ""; }

// Разбор одной строки сокета движка. `revision` — ревизия принятого состояния,
// `freshConnection` — подписка этого соединения ещё не дала состояния: после перезапуска
// сервиса ревизия начинается заново, поэтому первое состояние соединения принимается
// при любой ревизии. Результат — `{kind, id, ...}`:
// - `state` — принять `state`;
// - `ignore` — устаревшее состояние или неизвестное событие;
// - `error` — ответ с ошибкой: `code` и `message` для панели;
// - `invalid` — строка не по протоколу: `message` для панели.
// Событие `{event: "state", state}` с той же ревизией принимается: оно несёт новый текст ошибки.
// Ответ `{id, result}` с той же ревизией повторяет уже принятое событие и пропускается.
function decodeMessage(line, revision, freshConnection) {
    var message;
    try { message = JSON.parse(line); } catch (_) { return {kind: "invalid", id: null, message: "Не удалось прочитать ответ сервиса окон"}; }
    if (!message || typeof message !== "object" || Array.isArray(message))
        return {kind: "invalid", id: null, message: "Некорректный ответ сервиса окон"};
    if (message.event !== undefined) {
        if (message.event !== "state") return {kind: "ignore", id: null};
        if (!validState(message.state)) return {kind: "invalid", id: null, message: "Сервис окон прислал неполное состояние"};
        if (!freshConnection && message.state.revision < revision) return {kind: "ignore", id: null};
        return {kind: "state", id: null, state: message.state};
    }
    var id = message.id === undefined ? null : message.id;
    if (message.error !== undefined) {
        var error = message.error && typeof message.error === "object" ? message.error : {};
        return {kind: "error", id: id, code: typeof error.code === "string" ? error.code : "", message: errorText(error)};
    }
    if (!validState(message.result)) return {kind: "invalid", id: id, message: "Сервис окон вернул неполное состояние"};
    if (!freshConnection && message.result.revision <= revision) return {kind: "ignore", id: id};
    return {kind: "state", id: id, state: message.result};
}

function monitorFor(state, name) {
    if (!state) return null;
    return state.monitors.find(function(monitor) { return monitor.name === name; }) || null;
}

// Ключ монитора по имени разъёма или по самому ключу; неизвестный монитор — пустая строка.
function monitorKey(state, monitor) {
    if (!state) return "";
    var found = state.monitors.find(function(item) { return item.name === monitor || item.key === monitor; });
    return found ? found.key : "";
}

// Пространство движка, активное на мониторе `name`; чужое пространство — `null`.
function activeWorkspace(state, name) {
    var monitor = monitorFor(state, name);
    if (!monitor) return null;
    return state.workspaces.find(function(workspace) {
        return workspace.workspace_id === monitor.active_workspace_id && workspace.display_monitor_key === monitor.key;
    }) || null;
}

// Подпись монитора по ключу движка: `connector:DP-1` → «DP-1»,
// `make|model|serial` → «make model», `make|model|serial|DP-1` → «make model (DP-1)».
function monitorLabel(key) {
    if (key.indexOf("connector:") === 0) return key.slice(10);
    var parts = key.split("|");
    if (parts.length < 3) return key;
    var label = [parts[0], parts[1]].filter(Boolean).join(" ") || parts[2];
    return parts.length > 3 ? label + " (" + parts.slice(3).join("|") + ")" : label;
}

// Кнопки пространств монитора `name`: свои `1`…N (не меньше трёх, на одну больше
// старшего занятого номера, не больше десяти) и затем пространства отключённых мониторов,
// которые сейчас показаны на этом мониторе.
function workspaceItems(state, name) {
    var monitor = monitorFor(state, name);
    if (!monitor) return [];
    var own = state.workspaces.filter(function(workspace) { return workspace.monitor_key === monitor.key; });
    var highest = Math.min(10, Math.max(3, own.reduce(function(maximum, workspace) { return Math.max(maximum, workspace.number + 1); }, 0)));
    var result = [];
    for (var number = 1; number <= highest; number++) {
        var ref = own.find(function(workspace) { return workspace.number === number; });
        result.push({number: number, monitor: monitor.key, workspace_id: ref ? ref.workspace_id : null,
                    label: String(number), migrated: false,
                    active: !!ref && ref.workspace_id === monitor.active_workspace_id});
    }
    for (var ref of state.workspaces) {
        if (ref.monitor_key !== monitor.key && ref.display_monitor_key === monitor.key)
            result.push({number: ref.number, monitor: ref.monitor_key, workspace_id: ref.workspace_id,
                        label: ref.number + " · " + monitorLabel(ref.monitor_key), migrated: true,
                        active: ref.workspace_id === monitor.active_workspace_id});
    }
    return result;
}

function normalizedId(id) { return String(id || "").toLowerCase().replace(/\.desktop$/, ""); }

function desktopFor(appId, entries) {
    var id = normalizedId(appId);
    return entries.find(function(entry) {
        return normalizedId(entry.id) === id || (entry.startupClass && normalizedId(entry.startupClass) === id);
    }) || null;
}

function groupApps(windows, monitor, pinned, entries) {
    var groups = {};
    for (var id of pinned) {
        var entry = entries.find(function(candidate) { return candidate.id === id; }) || null;
        groups[id] = {id: id, name: entry ? entry.name : id, icon: entry ? entry.icon : "application-x-executable",
                      pinned: true, available: !!entry, windows: []};
    }
    for (var window of windows) {
        if (window.monitor !== monitor || !window.address || window.hidden || window.mapped === false) continue;
        // Специальные пространства (scratchpad) имеют отрицательный ID и в док монитора не входят.
        if (window.workspace_id < 0) continue;
        var entry = desktopFor(window.appId || window.className, entries);
        var id = entry ? entry.id : normalizedId(window.appId || window.className || window.address);
        if (!groups[id]) groups[id] = {id: id, name: entry ? entry.name : (window.appId || window.title || "Приложение"),
                                      icon: entry ? entry.icon : "application-x-executable", pinned: false, available: !!entry, windows: []};
        groups[id].windows.push(window);
    }
    var result = Object.keys(groups).map(function(id) {
        var group = groups[id];
        group.windows.sort(function(a, b) {
            if (!!a.activated !== !!b.activated) return a.activated ? -1 : 1;
            return (a.focusHistoryID === undefined || a.focusHistoryID < 0 ? 99999 : a.focusHistoryID)
                 - (b.focusHistoryID === undefined || b.focusHistoryID < 0 ? 99999 : b.focusHistoryID);
        });
        group.running = group.windows.length > 0;
        group.active = group.windows.some(function(window) { return window.activated; });
        group.lastWindow = group.windows[0] || null;
        return group;
    });
    result.sort(function(a, b) {
        var ai = pinned.indexOf(a.id), bi = pinned.indexOf(b.id);
        if (ai >= 0 && bi >= 0) return ai - bi;
        if (ai >= 0) return -1;
        if (bi >= 0) return 1;
        return a.name.localeCompare(b.name);
    });
    return result;
}

function fullscreenOn(windows, monitor, workspace) {
    return windows.some(function(window) { return window.monitor === monitor && window.workspace_id === workspace && (window.fullscreen & 2) !== 0; });
}

function parseCpu(text) {
    var match = /^cpu\s+(.+)$/m.exec(text);
    if (!match) return null;
    var fields = match[1].trim().split(/\s+/).slice(0, 8).map(Number);
    if (fields.length < 4 || fields.some(function(value) { return !Number.isFinite(value) || value < 0; })) return null;
    return {total: fields.reduce(function(sum, value) { return sum + value; }, 0), idle: fields[3] + (fields[4] || 0)};
}

function cpuUsage(previous, current, smoothed) {
    if (!previous || !current || current.total <= previous.total || current.idle < previous.idle) return null;
    var value = Math.max(0, Math.min(100, 100 * (1 - (current.idle - previous.idle) / (current.total - previous.total))));
    return smoothed === null || smoothed === undefined ? value : smoothed * 0.65 + value * 0.35;
}

function parseMemory(text) {
    var total = /^MemTotal:\s+(\d+)\s+kB/m.exec(text), available = /^MemAvailable:\s+(\d+)\s+kB/m.exec(text);
    if (!total || !available || Number(total[1]) <= 0) return null;
    return {total: Number(total[1]) * 1024, used: Math.max(0, Number(total[1]) - Number(available[1])) * 1024};
}

function movePin(pins, from, to) {
    var result = pins.slice();
    if (!Number.isInteger(from) || !Number.isInteger(to) || from < 0 || to < 0 || from >= pins.length || to >= pins.length) return result;
    result.splice(to, 0, result.splice(from, 1)[0]);
    return result;
}

function windowSelector(address) {
    var raw = String(address || "").replace(/^0x/, "");
    return /^[0-9a-fA-F]+$/.test(raw) ? "address:0x" + raw : null;
}

// Ключ делегата: при обновлении снимка делегат обновляется на месте и не теряет
// фокус, открытое меню и перетаскивание.
function workspaceKey(item) { return item.monitor + ":" + item.number; }

function keyed(items, key) {
    var result = {};
    for (var item of items) result[key(item)] = item;
    return result;
}

// Клик по приложению с фокусом переходит к его следующему недавнему окну,
// иначе — к самому недавнему.
function clickTarget(group) {
    var windows = group.windows || [];
    if (!windows.length) return null;
    return windows.length > 1 && windows[0].activated ? windows[1] : windows[0];
}

function cycleTarget(group, direction) {
    var windows = group.windows || [];
    if (!windows.length) return null;
    var current = windows.findIndex(function(window) { return window.activated; });
    if (current < 0) return windows[0];
    return windows[(current + (direction > 0 ? 1 : -1) + windows.length) % windows.length];
}

// Описание раскладки XKB (`active_keymap` Hyprland) → код раскладки по системному
// списку правил, например «Russian (phonetic)» → «ru».
function parseXkbRules(text) {
    var names = {}, section = "";
    for (var line of String(text || "").split(/\r?\n/)) {
        var header = line.match(/^!\s+(\w+)/);
        if (header) { section = header[1]; continue; }
        var match = section === "layout" ? line.match(/^\s+(\S+)\s+(.+?)\s*$/)
                  : section === "variant" ? line.match(/^\s+\S+\s+([^\s:]+):\s*(.+?)\s*$/) : null;
        if (match) names[match[2]] = match[1];
    }
    return names;
}

function layoutCode(keyboard, names) {
    if (!keyboard) return "…";
    var code = names[keyboard.active_keymap];
    if (!code) {
        var layouts = String(keyboard.layout || "").split(",").map(function(layout) { return layout.trim(); }).filter(Boolean);
        var index = keyboard.active_layout_index;
        code = layouts[index] || (layouts.length === 1 ? layouts[0] : "");
    }
    return code ? code.toUpperCase() : "…";
}
