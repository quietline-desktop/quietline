.pragma library

// Чистые функции оболочки: проверка состояния движка, кнопки пространств, группы дока,
// CPU/RAM, закрепления и раскладка клавиатуры. Используются в QML и в тестах Node.
// Функции, возвращающие видимый текст, получают последним параметром таблицу строк `s`
// (`Lang.s`, `table()` из Strings.js).
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

// Подстановка `{n}` из `args[n]` в строку таблицы — как `format` в Strings.js, который
// Models.js не импортирует: таблица приходит параметром.
function format(template, args) {
    return String(template).replace(/\{(\d+)\}/g, function(match, index) {
        var value = args[Number(index)];
        return value === undefined || value === null ? match : String(value);
    });
}

// Ключ таблицы строк по коду из `keys`; неизвестный код — `fallback`.
function textKey(keys, code, fallback) {
    return Object.prototype.hasOwnProperty.call(keys, code) ? keys[code] : fallback;
}

// Текст ошибки ответа движка для панели: по коду из протокола, с подробностью от движка.
var ERROR_KEYS = {
    invalid_number: "engineInvalidNumber",
    command_failed: "engineCommandFailed",
    invalid_request: "engineInvalidRequest",
    unknown_method: "engineUnknownMethod",
    internal_error: "engineInternalError"
};

function errorText(error, s) {
    var code = error && typeof error.code === "string" ? error.code : "";
    var detail = error && typeof error.message === "string" ? error.message : "";
    if (code === "invalid_number") return s.engineInvalidNumber;
    var text = s[textKey(ERROR_KEYS, code, "engineCommandNotDone")];
    return detail ? text + ": " + detail : text;
}

// Ошибка последней команды или сверки из подтверждённого состояния.
function stateError(state, s) { return state && state.error ? format(s.engineStateError, [state.error]) : ""; }

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
function decodeMessage(line, revision, freshConnection, s) {
    var message;
    try { message = JSON.parse(line); } catch (_) { return {kind: "invalid", id: null, message: s.engineUnreadable}; }
    if (!message || typeof message !== "object" || Array.isArray(message))
        return {kind: "invalid", id: null, message: s.engineMalformed};
    if (message.event !== undefined) {
        if (message.event !== "state") return {kind: "ignore", id: null};
        if (!validState(message.state)) return {kind: "invalid", id: null, message: s.engineIncompleteEvent};
        if (!freshConnection && message.state.revision < revision) return {kind: "ignore", id: null};
        return {kind: "state", id: null, state: message.state};
    }
    var id = message.id === undefined ? null : message.id;
    if (message.error !== undefined) {
        var error = message.error && typeof message.error === "object" ? message.error : {};
        return {kind: "error", id: id, code: typeof error.code === "string" ? error.code : "", message: errorText(error, s)};
    }
    if (!validState(message.result)) return {kind: "invalid", id: id, message: s.engineIncompleteResult};
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
function workspaceItems(state, name, s) {
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
                        label: format(s.workspaceMigrated, [ref.number, monitorLabel(ref.monitor_key)]), migrated: true,
                        active: ref.workspace_id === monitor.active_workspace_id});
    }
    return result;
}

// Номера на панели: только существующие пространства — занятые, текущее и перенесённые
// с отключённого монитора; пустые номера открываются клавишами.
function barWorkspaces(items) {
    return (items || []).filter(function(item) { return item.active || item.migrated || item.workspace_id !== null; });
}

// Название активного приложения монитора `monitor` для панели: имя desktop-записи,
// иначе заголовок окна (собственные окна оболочки — «Настройки»), иначе appId или класс;
// без активного окна — пусто.
function activeAppName(windows, monitor, entries) {
    var window = (windows || []).find(function(candidate) { return candidate.monitor === monitor && candidate.activated; });
    if (!window) return "";
    var entry = desktopFor(window.appId || window.className, entries || []);
    return entry ? entry.name : (window.title || window.appId || window.className || "");
}

function normalizedId(id) { return String(id || "").toLowerCase().replace(/\.desktop$/, ""); }

function desktopFor(appId, entries) {
    var id = normalizedId(appId);
    return entries.find(function(entry) {
        return normalizedId(entry.id) === id || (entry.startupClass && normalizedId(entry.startupClass) === id);
    }) || null;
}

// Группы дока: закреплённое приложение без desktop-записи и без окон не показывается.
function groupApps(windows, monitor, pinned, entries, s) {
    var groups = {}, missing = {};
    for (var id of pinned) {
        var entry = entries.find(function(candidate) { return candidate.id === id; }) || null;
        groups[id] = {id: id, name: entry ? entry.name : id, icon: entry ? entry.icon : "application-x-executable",
                      pinned: true, windows: []};
        if (!entry) missing[id] = true;
    }
    for (var window of windows) {
        if (window.monitor !== monitor || !window.address || window.hidden || window.mapped === false) continue;
        // Специальные пространства (scratchpad) в док монитора не входят; свёрнутые окна —
        // входят: их возвращают из дока.
        if (window.workspace_id < 0 && !window.minimized) continue;
        var entry = desktopFor(window.appId || window.className, entries);
        var id = entry ? entry.id : normalizedId(window.appId || window.className || window.address);
        if (!groups[id]) groups[id] = {id: id, name: entry ? entry.name : (window.appId || window.title || s.appUnnamed),
                                      icon: entry ? entry.icon : "application-x-executable", pinned: false, windows: []};
        groups[id].windows.push(window);
    }
    var result = Object.keys(groups).filter(function(id) {
        return !missing[id] || groups[id].windows.length > 0;
    }).map(function(id) {
        var group = groups[id];
        group.windows.sort(function(a, b) {
            if (!!a.activated !== !!b.activated) return a.activated ? -1 : 1;
            return (a.focusHistoryID === undefined || a.focusHistoryID < 0 ? 99999 : a.focusHistoryID)
                 - (b.focusHistoryID === undefined || b.focusHistoryID < 0 ? 99999 : b.focusHistoryID);
        });
        group.running = group.windows.length > 0;
        group.minimized = group.running && group.windows.every(function(window) { return !!window.minimized; });
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

// Команда движка, которая разворачивает окно размером или возвращает ему прежний размер;
// адрес не литерал — `null`.
function maximizeCommand(address) {
    var selector = windowSelector(address);
    return selector ? ["quietline-engine", "maximize", "--window", selector.slice("address:".length).toLowerCase()] : null;
}

// Выражение для `Hyprland.dispatch`: фокус окна и подъём его поверх остальных одним вызовом —
// фокус сам по себе плавающее окно не поднимает. Адрес не литерал — `null`.
function focusWindowCommand(address) {
    var selector = windowSelector(address);
    return selector ? 'function() hl.dispatch(hl.dsp.focus({ window = "' + selector + '" })); '
        + 'hl.dispatch(hl.dsp.window.bring_to_top()) end' : null;
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
// Пространство свёрнутых окон: окно уходит туда кнопкой заголовка и возвращается из дока.
var MINIMIZED_WORKSPACE = "special:quietline-minimized";

// Нет ли на пространстве `workspace` монитора `monitor` ни одного показанного окна.
function workspaceEmpty(windows, monitor, workspace) {
    return !(windows || []).some(function(window) {
        return window.monitor === monitor && window.workspace_id === workspace && !window.hidden && window.mapped !== false;
    });
}

// Виден ли док: только в режиме «Окна» без полноэкранного окна (`available`), и тогда —
// всегда, если автоскрытие выключено (`always`), иначе пока указатель у нижнего края или на
// доке, открыто меню, идёт перетаскивание, навигация с клавиатуры или пространство пусто.
function dockRevealed(state) {
    if (!state.available) return false;
    return !!(state.always || state.hovered || state.menuOpen || state.dragging || state.keyboard || state.empty);
}

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

function layoutCode(keyboard, names, s) {
    if (!keyboard) return s.layoutUnknown;
    var code = names[keyboard.active_keymap];
    if (!code) {
        var layouts = String(keyboard.layout || "").split(",").map(function(layout) { return layout.trim(); }).filter(Boolean);
        var index = keyboard.active_layout_index;
        code = layouts[index] || (layouts.length === 1 ? layouts[0] : "");
    }
    return code ? code.toUpperCase() : s.layoutUnknown;
}

// Подпись сетевого устройства. «Подключено» — только с адресом: NetworkManager сообщает
// состояние 100 чуть раньше; отсутствие кабеля важнее любого состояния.
function deviceLabel(device, s) {
    if (device.type === "ethernet" && device.cable === false) return s.deviceNoCable;
    if (device.state === "connected") return (device.addresses || []).length ? s.deviceConnected : s.deviceConnecting;
    if (device.state === "connecting") return s.deviceConnecting;
    if (device.state === "disconnected") return s.deviceDisconnected;
    return s.deviceUnavailable;
}

// Значок Material Symbols силы сигнала Wi-Fi по уровню 0–100: четыре, три, две или одна дуга.
function wifiSymbol(signal) {
    if (signal >= 75) return "signal_wifi_4_bar";
    if (signal >= 50) return "network_wifi_3_bar";
    if (signal >= 25) return "network_wifi_2_bar";
    return "network_wifi_1_bar";
}

// Секунды до отката: округление вверх, не меньше 0.
function secondsLeft(deadlineMs, nowMs) { return Math.max(0, Math.ceil((deadlineMs - nowMs) / 1000)); }

// Незавершённая контрольная точка из `network status`. Точка этой оболочки сохраняет свой
// срок; найденная после перезапуска оболочки идёт без срока — откатит её сам NetworkManager.
function pendingFromStatus(status, current) {
    var paths = (status && status.pendingCheckpoints) || [];
    if (!paths.length) return null;
    if (current && paths.indexOf(current.checkpoint) >= 0) return current;
    return {checkpoint: paths[0], deadline: null};
}

// Текст ошибки формы профиля по полю `field` ответа `quietline-shell network`.
var PROFILE_FIELD_KEYS = {
    name: "profileFieldName",
    method: "profileFieldMethod",
    prefix: "profileFieldPrefix",
    address: "profileFieldAddress",
    gateway: "profileFieldGateway",
    dns: "profileFieldDns",
    profile: "profileFieldProfile"
};

// Что не получилось, по виду сетевого действия `NetworkService`.
var NETWORK_ACTION_KEYS = {
    status: "networkStatusFailed",
    scan: "networkScanFailed",
    radio: "networkRadioFailed",
    connect: "networkConnectFailed",
    save: "networkSaveFailed",
    delete: "networkDeleteFailed",
    apply: "networkApplyFailed",
    confirm: "networkConfirmFailed",
    rollback: "networkRollbackFailed"
};

// Текст ошибки для сетевой панели: по полю формы — текст поля, иначе фраза действия
// и подробность `quietline-shell` (по-английски) через двоеточие.
function networkErrorText(kind, response, s) {
    var field = response ? textKey(PROFILE_FIELD_KEYS, response.field, "") : "";
    if (field) return s[field];
    var text = s[textKey(NETWORK_ACTION_KEYS, kind, "networkActionFailed")];
    var detail = response && typeof response.error === "string" ? response.error : "";
    return detail ? text + ": " + detail : text;
}

// Подсветка из `brightnessctl -m -c backlight`: строки `устройство,класс,текущее,процент%,максимум`.
// Без устройства класса `backlight` — `null`.
function parseBrightness(text) {
    for (var line of String(text || "").split("\n")) {
        var fields = line.split(",");
        if (fields.length >= 5 && fields[1] === "backlight")
            return {device: fields[0], percent: parseInt(fields[3], 10) || 0};
    }
    return null;
}

// Аргументы записи яркости; без устройства или с процентом меньше 1 — `null`.
function brightnessArgs(device, percent) {
    if (!device || !(percent >= 1)) return null;
    return ["brightnessctl", "-c", "backlight", "-d", device, "set", Math.min(100, Math.round(percent)) + "%"];
}

// Подсветка принадлежит встроенному экрану; панели внешних выходов ползунка не получают.
function isBuiltinOutput(name) { return /^(eDP|LVDS|DSI)-/.test(name || ""); }

// Монитор в правиле Hyprland для `quietline-shell display`: `desc:<описание>`, чтобы масштаб
// следовал за монитором при смене разъёма; без описания или с кавычкой, обратной косой чертой
// или управляющим символом в нём — имя разъёма.
function displayOutput(monitor) {
    var description = String((monitor && monitor.description) || "");
    if (description && description.length <= 200 && !/["\\\x00-\x1f\x7f]/.test(description)) return "desc:" + description;
    return String((monitor && monitor.name) || "");
}

// Масштабы для режима `width`×`height`, которые Hyprland применяет без подгонки: логический
// размер в каждом измерении — целое число пикселей.
var SCALE_STEPS = [1, 1.25, 1.5, 1.75, 2];
function scaleChoices(width, height) {
    if (!(width > 0) || !(height > 0)) return [];
    return SCALE_STEPS.filter(function(scale) { return Number.isInteger(width / scale) && Number.isInteger(height / scale); });
}

// Режимы монитора из `quietline-shell display` (`[{width, height, refresh}]`): разрешения без
// повторов по убыванию площади и частоты разрешения по убыванию.
function displayResolutions(modes) {
    var result = [];
    (modes || []).forEach(function(mode) {
        if (!result.some(function(item) { return item.width === mode.width && item.height === mode.height; }))
            result.push({width: mode.width, height: mode.height});
    });
    return result.sort(function(a, b) { return b.width * b.height - a.width * a.height || b.width - a.width; });
}
function displayRates(modes, width, height) {
    var rates = (modes || []).filter(function(mode) { return mode.width === width && mode.height === height; })
        .map(function(mode) { return mode.refresh; });
    return rates.filter(function(rate, index) { return rates.indexOf(rate) === index; }).sort(function(a, b) { return b - a; });
}
// Режим для `hl.monitor`: `2560x1440@74.96`.
function displayMode(width, height, refresh) { return width + "x" + height + "@" + Number(refresh).toFixed(2); }
// Частота для подписи: «74,96 Гц», целая — без дробной части («60 Гц»).
function refreshLabel(refresh, s) {
    var value = Math.round(Number(refresh) * 100) / 100;
    var text = Number.isInteger(value) ? String(value) : value.toFixed(2).replace(".", s.decimalPoint);
    return format(s.displayHz, [text]);
}
// Ближайшая к `refresh` частота из `rates` (индекс); пусто — −1.
function nearestRate(rates, refresh) {
    var best = -1;
    (rates || []).forEach(function(rate, index) {
        if (best < 0 || Math.abs(rate - refresh) < Math.abs(rates[best] - refresh)) best = index;
    });
    return best;
}

// Сроки простоя «Питания» в минутах: 0 — «Никогда».
function idleLabel(minutes, s) { return minutes ? format(s.idleMinutes, [minutes]) : s.idleNever; }

// Громкость PipeWire в пределах 0…150 %.
function clampVolume(value) { return Math.max(0, Math.min(1.5, value)); }

// Индикатор громкости, микрофона, яркости и раскладки: глиф Nerd Font, заполнение полосы
// 0…1 (громкость выше 100 % заполняет её целиком; у раскладки полосы нет — `-1`) и подпись.
var OSD_HIDE_MS = 1500;
// Сколько после изменения ползунком оболочки индикатор не показывает изменения звука.
var OSD_LOCAL_MS = 600;
// Значки индикатора — имена Material Symbols: обычный и выключенный звук.
var OSD_ICONS = {volume: ["volume_up", "volume_off"], mic: ["mic", "mic_off"], brightness: ["light_mode", "light_mode"], layout: ["keyboard", "keyboard"]};
function osdView(kind, value, muted) {
    var icons = OSD_ICONS[kind] || OSD_ICONS.volume;
    if (kind === "layout") return {icon: icons[0], fill: -1, text: String(value)};
    var number = Math.max(0, Number(value) || 0);
    return {icon: icons[muted ? 1 : 0], fill: Math.min(1, number), text: Math.round(number * 100) + "%"};
}
function osdSuppressed(localUntil, now) { return now < localUntil; }

// Пороги предупреждения о заряде при разряде; последний — критическое уведомление.
var BATTERY_LEVELS = [20, 10, 5];
var BATTERY_CRITICAL = 5;
// Порог, о котором пора предупредить: наименьший из тех, до которых заряд опустился и о
// которых ещё не предупреждали (`warned` — последний предупреждённый порог, `null` после
// зарядки). Колебание заряда около порога не повторяет предупреждение. Без разряда и при
// нулевом заряде (UPower ещё не отдал значение) предупреждения нет.
function batteryWarning(warned, percent, discharging) {
    if (!discharging || !(percent > 0)) return null;
    var found = null;
    for (var i = 0; i < BATTERY_LEVELS.length; i++) {
        var level = BATTERY_LEVELS[i];
        if (percent <= level && (warned === null || level < warned)) found = level;
    }
    return found;
}

// Время батареи: «1 ч 20 мин» или «10 мин», не меньше минуты.
function formatDuration(seconds, s) {
    var minutes = Math.max(1, Math.round(seconds / 60)), hours = Math.floor(minutes / 60);
    return hours ? format(s.durationHoursMinutes, [hours, minutes % 60]) : format(s.durationMinutes, [minutes]);
}

// Биты `modmask` Hyprland в том порядке, в каком модификаторы называют.
var MODIFIERS = [[64, "Super"], [4, "Ctrl"], [8, "Alt"], [1, "Shift"]];

// Действия привязок Quietline без команды: описание `quietline:<действие>` в Lua-конфигурации.
var QUIETLINE_BIND_KEYS = {
    "close": "bindClose", "focus-left": "bindFocusLeft", "focus-right": "bindFocusRight",
    "focus-up": "bindFocusUp", "focus-down": "bindFocusDown", "move-left": "bindMoveLeft",
    "move-right": "bindMoveRight", "move-up": "bindMoveUp", "move-down": "bindMoveDown",
    "monitor-left": "bindMonitorLeft", "monitor-right": "bindMonitorRight", "float": "bindFloat",
    "fullscreen": "bindFullscreen", "cycle": "bindCycle",
    "drag": "bindDrag", "resize": "bindResize"
};

// Описание известной команды привязки; неизвестная остаётся как есть.
function bindAction(command, s) {
    var match;
    if ((match = /^quietline:(.+)$/.exec(command))) {
        var key = textKey(QUIETLINE_BIND_KEYS, match[1], "");
        return key ? s[key] : command;
    }
    if ((match = /^quietline-engine switch (\d+)$/.exec(command))) return format(s.bindSwitch, [match[1]]);
    if ((match = /^quietline-engine move (\d+)$/.exec(command))) return format(s.bindMove, [match[1]]);
    if (command === "quietline-engine toggle") return s.bindToggle;
    if (command === "quietline-engine maximize") return s.bindMaximize;
    if (command === "ghostty") return s.bindTerminal;
    if (command === "quietline-shell lock") return s.bindLock;
    if (/^quietline-shell app quit/.test(command)) return s.bindQuit;
    if (/ipc call quietline confirmKill$/.test(command)) return s.bindKill;
    if (/ipc call quietline clipboard$/.test(command)) return s.bindClipboard;
    if (command === "quietline-shell screenshot output") return s.bindScreenshotOutput;
    if (command === "quietline-shell screenshot region") return s.bindScreenshotRegion;
    if (/ipc call quietline launcher$/.test(command)) return s.bindSearch;
    if (/ipc call quietline settings shortcuts$/.test(command)) return s.bindShortcuts;
    if (/ipc call quietline settings/.test(command)) return s.bindSettings;
    if (command === "dolphin") return s.bindDolphin;
    if (/ipc call quietline notifications$/.test(command)) return s.bindNotifications;
    if (/^wpctl set-volume .*@DEFAULT_AUDIO_SINK@ \d+%\+$/.test(command)) return s.bindVolumeUp;
    if (/^wpctl set-volume .*@DEFAULT_AUDIO_SINK@ \d+%-$/.test(command)) return s.bindVolumeDown;
    if (command === "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle") return s.bindMute;
    if (command === "wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle") return s.bindMicMute;
    if (/^brightnessctl .* set \d+%\+/.test(command)) return s.bindBrightnessUp;
    if (/^brightnessctl .* set \d+%-/.test(command)) return s.bindBrightnessDown;
    if (command === "exec_cmd") return s.bindCommand;
    return command;
}

// Подписи мультимедийных клавиш в памятке вместо имён XKB.
var KEY_LABEL_KEYS = {
    XF86AudioRaiseVolume: "keyVolumeUp", XF86AudioLowerVolume: "keyVolumeDown", XF86AudioMute: "keyMute",
    XF86AudioMicMute: "keyMicMute", XF86MonBrightnessUp: "keyBrightnessUp", XF86MonBrightnessDown: "keyBrightnessDown",
    "mouse:272": "keyMouseLeft", "mouse:273": "keyMouseRight"
};
// Клавиши, которые одинаково подписываются на любом языке.
var KEY_SYMBOLS = {Left: "←", Right: "→", Up: "↑", Down: "↓", Return: "Enter"};

// Приложения, на которые ссылаются привязки Hyprland: команда -> ID desktop entry.
var BIND_APPS = {dolphin: "org.kde.dolphin", ghostty: "com.mitchellh.ghostty"};

// Команда привязки: описание (Lua-конфигурация Quietline пишет туда команду или
// `quietline:<действие>`), иначе аргумент. У Lua-привязки без описания аргумент — номер
// ссылки Lua, тогда берётся имя диспетчера из `HL.Dispatcher(<имя>)`.
function bindCommand(bind) {
    if (bind.description) return String(bind.description);
    var arg = String(bind.arg || ""), dispatcher = String(bind.dispatcher || "");
    var lua = /^HL\.Dispatcher\((.+)\)$/.exec(dispatcher);
    if (lua && (!arg || /^\d+$/.test(arg))) return lua[1];
    return arg || dispatcher;
}

// Подпись клавиш привязки: модификаторы и клавиша.
function bindKeys(bind, s) {
    var keys = MODIFIERS.filter(function(item) { return (bind.modmask & item[0]) !== 0; })
        .map(function(item) { return item[1]; });
    var label = textKey(KEY_LABEL_KEYS, bind.key, "");
    keys.push(label ? s[label] : textKey(KEY_SYMBOLS, bind.key, bind.key));
    return keys.join("+");
}

// Памятка сочетаний из `hyprctl binds -j`: `[{keys: "Super+Shift+1", action}]`.
// Привязки к приложениям, которых нет среди `entries`, в памятку не входят. Идущие подряд
// привязки `switch N` (или `move N`) с одними модификаторами и номерами N, N+1, … —
// одна строка `Super+1…0` с диапазоном пространств на месте первой из них.
function describeBinds(binds, s, entries) {
    var rows = [], ranges = [], open = {};
    (binds || []).forEach(function(bind) {
        if (!bind || typeof bind !== "object") return;
        var command = bindCommand(bind);
        var appId = Object.prototype.hasOwnProperty.call(BIND_APPS, command) ? BIND_APPS[command] : null;
        if (appId && !desktopFor(appId, entries || [])) return;
        var workspace = /^quietline-engine (switch|move) (\d+)$/.exec(command);
        if (workspace) {
            var id = workspace[1] + ":" + bind.modmask, range = open[id], number = Number(workspace[2]);
            if (range && range.row === rows.length - 1 && number === range.lastNumber + 1) {
                range.lastKey = bind.key;
                range.lastNumber = number;
                range.count += 1;
                return;
            }
            open[id] = {row: rows.length, bind: bind, kind: workspace[1], firstNumber: number,
                        lastKey: bind.key, lastNumber: number, count: 1};
            ranges.push(open[id]);
        }
        rows.push({keys: bindKeys(bind, s), action: bindAction(command, s)});
    });
    ranges.forEach(function(range) {
        if (range.count < 2) return;
        rows[range.row] = {
            keys: bindKeys(range.bind, s) + "…" + range.lastKey,
            action: format(range.kind === "switch" ? s.bindSwitch : s.bindMove, [range.firstNumber + "–" + range.lastNumber])
        };
    });
    return rows;
}

// Действия сеанса после корректного закрытия окон (`quietline-shell session`).
var SESSION_ACTIONS = ["logout", "reboot", "poweroff"];
var SESSION_LABEL_KEYS = {logout: "sessionLogout", reboot: "sessionReboot", poweroff: "sessionPoweroff"};
var SESSION_QUESTION_KEYS = {logout: "sessionLogoutQuestion", reboot: "sessionRebootQuestion", poweroff: "sessionPoweroffQuestion"};

// Подпись и вопрос подтверждения действия сеанса; неизвестное действие — пустая строка.
function sessionLabel(action, s) { var key = textKey(SESSION_LABEL_KEYS, action, ""); return key ? s[key] : ""; }
function sessionQuestion(action, s) { var key = textKey(SESSION_QUESTION_KEYS, action, ""); return key ? s[key] : ""; }

// Приложения, которые не закрылись перед выходом: имя desktop-записи (иначе класс окна),
// несколько окон одного приложения — числом в скобках, окно без имени — отдельной подписью.
function remainingText(remaining, s, entries) {
    var names = [], counts = {};
    (remaining || []).forEach(function(window) {
        var entry = window.app ? desktopFor(window.app, entries || []) : null;
        var name = entry ? entry.name : (window.app || s.sessionUntitledWindow);
        if (!(name in counts)) { counts[name] = 0; names.push(name); }
        counts[name] += 1;
    });
    var labels = names.map(function(name) { return counts[name] > 1 ? name + " (" + counts[name] + ")" : name; });
    return labels.length ? format(s.sessionRemaining, [labels.join(", ")]) : "";
}

function sessionErrorText(action, detail, s) {
    var label = sessionLabel(action, s) || s.sessionAction;
    return format(s.sessionActionFailed, [label]) + (detail ? ": " + detail : "");
}

// Группа процессов systemd для приложения, запущенного оболочкой: `app-quietline-<id>-<token>`.
function scopeUnit(id, token) {
    var name = String(id || "app").replace(/[^A-Za-z0-9_.:-]/g, "_").slice(0, 64) || "app";
    return "app-quietline-" + name + "-" + String(token).replace(/[^A-Za-z0-9]/g, "").slice(0, 16);
}

// Команда запуска desktop entry в своей группе процессов; пустая команда — `null`.
function launchCommand(command, unit) {
    if (!command || !command.length) return null;
    return ["systemd-run", "--user", "--scope", "--collect", "--quiet", "--unit=" + unit, "--"].concat(Array.from(command));
}

// Сколько мс держать уведомление: критическое — до закрытия (0), остальные — не дольше
// `NOTIFICATION_MS`, короче — если приложение просит меньше (`expireTimeout` в секундах).
var NOTIFICATION_MS = 6000;
var NOTIFICATION_LIMIT = 3;
// История уведомлений: при переполнении закрываются самые старые.
var NOTIFICATION_HISTORY_LIMIT = 100;
function notificationsToDrop(count) { return Math.max(0, count - NOTIFICATION_HISTORY_LIMIT); }
// Всплывёт ли карточка: при открытом центре уведомлений — нет (уведомление сразу в списке),
// критическая — всегда, остальные — вне режима «Не беспокоить».
function popupAllowed(urgency, dnd, centerOpen) {
    if (centerOpen) return false;
    return urgency === 2 || !dnd;
}
// Картинка уведомления для Image. Путь к файлу (`image-path`, в том числе в виде
// `image://icon/<путь>`) становится адресом `file://`: файл, который приложение уже удалило
// (миниатюра снимка Satty), даёт ошибку загрузки и запасной значок, а не клетку «нет значка».
// Имя значка и `image://qsimage/…` остаются как есть.
function notificationImage(image) {
    var value = String(image || "");
    var path = value.indexOf("image://icon/") === 0 ? decodeURIComponent(value.slice(13)) : value;
    if (path.indexOf("file://") === 0) return path;
    if (path.charAt(0) === "/") return "file://" + path;
    return value;
}
// `transient` живёт только карточкой: без видимой карточки (скрыта, не всплыла при
// «Не беспокоить» или открытом центре) он сразу закрывается по сроку.
function transientExpires(transient, popupShown) { return !!transient && !popupShown; }
// Давность уведомления для истории: меньше минуты, меньше часа (минуты), сегодня, раньше.
function notificationAge(received, now) {
    var seconds = Math.max(0, (now - received) / 1000);
    if (seconds < 60) return {kind: "now", minutes: 0};
    if (seconds < 3600) return {kind: "minutes", minutes: Math.floor(seconds / 60)};
    var then = new Date(received), today = new Date(now);
    var sameDay = then.getFullYear() === today.getFullYear() && then.getMonth() === today.getMonth() && then.getDate() === today.getDate();
    return {kind: sameDay ? "today" : "earlier", minutes: Math.floor(seconds / 60)};
}
function notificationTimeout(expireTimeout, urgency) {
    if (urgency === 2) return 0;
    var requested = Number(expireTimeout) * 1000;
    return requested > 0 ? Math.min(requested, NOTIFICATION_MS) : NOTIFICATION_MS;
}

// Записи истории буфера, подходящие под запрос: по тексту превью, картинки — по слову «изображение» или «image».
function clipboardMatches(entries, query, s) {
    var needle = String(query || "").trim().toLowerCase();
    return (entries || []).filter(function(entry) {
        if (!needle) return true;
        var text = entry.kind === "image" ? s.clipboardImageKeywords + " " + entry.preview : entry.preview;
        return String(text).toLowerCase().indexOf(needle) >= 0;
    });
}

// Подпись картинки из превью cliphist «[[ binary data 14 KiB png 120x80 ]]»: «Изображение PNG · 120×80».
// Вид записи буфера для значка и подписи: картинка, ссылка (одна строка http/https/file) или текст.
function clipboardKind(entry) {
    if (!entry) return "text";
    if (entry.kind === "image") return "image";
    return /^(https?|file|ftp):\/\/\S+$/i.test(String(entry.preview || "").trim()) ? "link" : "text";
}
var CLIPBOARD_SYMBOLS = {image: "image", link: "link", text: "notes"};
var CLIPBOARD_KIND_KEYS = {image: "clipboardImage", link: "clipboardLink", text: "clipboardText"};
function clipboardSymbol(entry) { return CLIPBOARD_SYMBOLS[clipboardKind(entry)]; }
function clipboardKindLabel(entry, s) { return s[CLIPBOARD_KIND_KEYS[clipboardKind(entry)]]; }

function clipboardImageLabel(preview, s) {
    var match = /binary data .* (\w+) (\d+)x(\d+)/.exec(String(preview || ""));
    return match ? format(s.clipboardImageDetails, [match[1].toUpperCase(), match[2], match[3]]) : s.clipboardImage;
}

// Простые вычисления поиска: числа (дробная часть через точку или запятую), `+ - * / % ^`
// и скобки. Свой разбор без eval; не арифметика, ошибка или бесконечность — `null`.
function calculate(text) {
    var source = String(text || "").trim();
    if (!source || source.length > 100 || !/[-+*\/%^]/.test(source) || !/^[\d\s.,+\-*\/%^()]+$/.test(source)) return null;
    var tokens = source.match(/\d+(?:[.,]\d+)?|[-+*\/%^()]/g) || [];
    if (tokens.join("") !== source.replace(/\s+/g, "")) return null;
    var position = 0;
    function peek() { return tokens[position]; }
    function expression() {
        var value = term();
        while (peek() === "+" || peek() === "-") {
            var operator = tokens[position++];
            var right = term();
            value = operator === "+" ? value + right : value - right;
        }
        return value;
    }
    function term() {
        var value = unary();
        while (peek() === "*" || peek() === "/" || peek() === "%") {
            var operator = tokens[position++];
            var right = unary();
            value = operator === "*" ? value * right : operator === "/" ? value / right : value % right;
        }
        return value;
    }
    function unary() {
        if (peek() === "-") { position++; return -unary(); }
        if (peek() === "+") { position++; return unary(); }
        return power();
    }
    function power() {
        var base = primary();
        if (peek() === "^") { position++; return Math.pow(base, unary()); }
        return base;
    }
    function primary() {
        var token = tokens[position++];
        if (token === "(") {
            var value = expression();
            if (tokens[position++] !== ")") throw new Error("missing )");
            return value;
        }
        if (token !== undefined && /^\d/.test(token)) return parseFloat(token.replace(",", "."));
        throw new Error("unexpected token");
    }
    try {
        var result = expression();
        return position === tokens.length && isFinite(result) ? result : null;
    } catch (_) {
        return null;
    }
}

// Число для показа и копирования: без хвостов двоичной арифметики (0.1 + 0.2 → 0.3).
function formatNumber(value) { return String(parseFloat(Number(value).toPrecision(12))); }

// Разделы окна «Настройки» в порядке боковой панели (они же — в поиске): ключи подписи и
// ключевых слов таблицы строк, значок Material Symbols, цвет квадрата значка и номер группы
// боковой панели. Ключевые слова содержат слова обоих языков.
var SETTINGS_SECTIONS = [
    {id: "network", label: "settingsNetwork", keywords: "settingsNetworkKeywords", symbol: "wifi", color: "#0a84ff", group: 0},
    {id: "bluetooth", label: "settingsBluetooth", keywords: "settingsBluetoothKeywords", symbol: "bluetooth", color: "#0a84ff", group: 0},
    {id: "audio", label: "settingsAudio", keywords: "settingsAudioKeywords", symbol: "volume_up", color: "#ff375f", group: 1},
    {id: "display", label: "settingsDisplay", keywords: "settingsDisplayKeywords", symbol: "light_mode", color: "#0a84ff", group: 1},
    {id: "mouse", label: "settingsMouse", keywords: "settingsMouseKeywords", symbol: "mouse", color: "#8e8e93", group: 1},
    {id: "keyboard", label: "settingsKeyboard", keywords: "settingsKeyboardKeywords", symbol: "keyboard", color: "#8e8e93", group: 1},
    {id: "power", label: "settingsPower", keywords: "settingsPowerKeywords", symbol: "battery_full", color: "#30d158", group: 1},
    {id: "appearance", label: "settingsAppearance", keywords: "settingsAppearanceKeywords", symbol: "palette", color: "#5e5ce6", group: 2},
    {id: "dock", label: "settingsDock", keywords: "settingsDockKeywords", symbol: "dock_to_bottom", color: "#8e8e93", group: 2},
    {id: "notifications", label: "settingsNotifications", keywords: "settingsNotificationsKeywords", symbol: "notifications", color: "#5e5ce6", group: 2},
    {id: "region", label: "settingsRegion", keywords: "settingsRegionKeywords", symbol: "language", color: "#8e8e93", group: 3},
    {id: "datetime", label: "settingsDateTime", keywords: "settingsDateTimeKeywords", symbol: "schedule", color: "#8e8e93", group: 3},
    {id: "apps", label: "settingsApps", keywords: "settingsAppsKeywords", symbol: "apps", color: "#8e8e93", group: 3},
    {id: "shortcuts", label: "settingsShortcuts", keywords: "settingsShortcutsKeywords", symbol: "keyboard_command_key", color: "#8e8e93", group: 3},
    {id: "about", label: "settingsAbout", keywords: "settingsAboutKeywords", symbol: "info", color: "#8e8e93", group: 3}
];
// Прежние идентификаторы разделов и раздел, который открывается вместо них.
var SECTION_ALIASES = {time: "datetime", pins: "dock"};
function resolveSection(name) { return textKey(SECTION_ALIASES, name, name); }

// Подписи сочетаний переключения раскладки (значения `grp:*` из `quietline-shell region`)
// и раскладок; неизвестное значение возвращается как есть.
var TOGGLE_KEYS = {
    "grp:lalt_lshift_toggle": "toggleLaltLshift",
    "grp:alt_shift_toggle": "toggleAltShift",
    "grp:ctrl_shift_toggle": "toggleCtrlShift",
    "grp:caps_toggle": "toggleCaps"
};
var LAYOUT_KEYS = {us: "layoutNameUs", ru: "layoutNameRu"};
function toggleLabel(toggle, s) {
    var key = textKey(TOGGLE_KEYS, toggle, "");
    return key ? s[key] : String(toggle);
}
function layoutLabel(code, s) {
    var key = textKey(LAYOUT_KEYS, code, "");
    return key ? s[key] : String(code);
}

// Системные действия поиска; `group` — группа меню при пустом поле.
var SEARCH_ACTIONS = [
    {id: "lock", group: "actions", title: "actionLock", keywords: "actionLockKeywords"},
    {id: "logout", group: "power", title: "actionLogout", keywords: "actionLogoutKeywords"},
    {id: "reboot", group: "power", title: "actionReboot", keywords: "actionRebootKeywords"},
    {id: "poweroff", group: "power", title: "actionPoweroff", keywords: "actionPoweroffKeywords"},
    {id: "screenshot", group: "actions", title: "actionScreenshot", keywords: "actionScreenshotKeywords"},
    {id: "clipboard", group: "actions", title: "actionClipboard", keywords: "actionClipboardKeywords"}
];

// Насколько `text` подходит под `needle`: начало строки — 3, начало слова — 2, где-то внутри — 1.
function matchScore(text, needle) {
    var value = String(text || "").toLowerCase();
    if (!needle || value.indexOf(needle) < 0) return 0;
    if (value.indexOf(needle) === 0) return 3;
    return (" " + value).indexOf(" " + needle) >= 0 ? 2 : 1;
}

// Разделы окна поиска: при запросе первый результат — «Лучшее совпадение», остальные
// сгруппированы по виду (вычисление — к лучшему совпадению, разделы настроек — к действиям);
// без запроса — только приложения. Порядок внутри раздела сохраняется, `index` — номер
// результата в исходном списке (по нему идёт выбор стрелками).
// У каждой строки — ключ `key` (заголовок — «#вид», результат — «вид:идентификатор»): по нему
// список сохраняет строку при обновлении результатов.
var SEARCH_SECTION_KEYS = {best: "searchBest", app: "searchApps", action: "searchActions", file: "searchFiles"};
function searchSections(results, query, s) {
    var order = ["best", "app", "action", "file"];
    var groups = {best: [], app: [], action: [], file: []};
    (results || []).forEach(function(item, index) {
        var kind = item.kind === "settings" ? "action" : item.kind === "calc" ? "best" : item.kind;
        if (String(query || "").trim() && index === 0) kind = "best";
        if (!groups[kind]) kind = "action";
        groups[kind].push({item: item, index: index});
    });
    var rows = [];
    order.forEach(function(kind) {
        if (!groups[kind].length) return;
        rows.push({header: true, key: "#" + kind, title: s[SEARCH_SECTION_KEYS[kind]]});
        groups[kind].forEach(function(entry) { rows.push({header: false, key: entry.item.kind + ":" + entry.item.id, item: entry.item, index: entry.index}); });
    });
    return rows;
}

// Значок результата поиска без собственной картинки (Material Symbols).
var SEARCH_ACTION_SYMBOLS = {lock: "lock", screenshot: "screenshot_region", clipboard: "content_paste",
    logout: "logout", reboot: "restart_alt", poweroff: "power_settings_new"};
function searchSymbol(item) {
    if (!item) return "search";
    if (item.kind === "group") return item.symbol;
    if (item.kind === "calc") return "calculate";
    if (item.kind === "settings") return "settings";
    if (item.kind === "action") return SEARCH_ACTION_SYMBOLS[item.id] || "bolt";
    if (item.kind === "file") return /\.(png|jpe?g|gif|webp|svg|bmp|tiff?)$/i.test(item.title || "") ? "image"
        : /\.pdf$/i.test(item.title || "") ? "picture_as_pdf" : "description";
    return "apps";
}

// Результаты поиска: вычисление, затем приложения, действия и разделы настроек по совпадению,
// затем файлы. Пустой запрос — все приложения. `home` сокращается до «~» в путях файлов.
function searchResults(query, apps, files, home, limit, s) {
    var needle = String(query || "").trim().toLowerCase();
    var max = limit || 40;
    if (!needle) return (apps || []).slice(0, max).map(function(app) { return {kind: "app", id: app.id, title: app.name, subtitle: s.searchApp, icon: app.icon || ""}; });
    var scored = [];
    (apps || []).forEach(function(app) {
        var score = Math.max(matchScore(app.name, needle), matchScore(app.id, needle) - 0.5);
        if (score > 0) scored.push({kind: "app", id: app.id, title: app.name, subtitle: s.searchApp, icon: app.icon || "", score: score + 0.2});
    });
    SEARCH_ACTIONS.forEach(function(action) {
        var title = s[action.title];
        var score = Math.max(matchScore(title, needle), matchScore(s[action.keywords], needle) - 0.5);
        if (score > 0) scored.push({kind: "action", id: action.id, title: title, subtitle: s.searchAction, score: score + 0.1});
    });
    SETTINGS_SECTIONS.forEach(function(section) {
        var label = s[section.label];
        var score = Math.max(matchScore(label, needle), matchScore(s[section.keywords], needle) - 0.5);
        if (score > 0) scored.push({kind: "settings", id: section.id, title: label, subtitle: s.searchSettings, score: score});
    });
    scored.sort(function(a, b) { return b.score - a.score; });
    var results = [];
    var value = calculate(query);
    if (value !== null) results.push({kind: "calc", id: "calc", title: "= " + formatNumber(value), value: formatNumber(value), subtitle: s.searchCalcHint});
    results = results.concat(scored.map(function(item) { delete item.score; return item; }));
    (files || []).forEach(function(path) {
        var slash = path.lastIndexOf("/");
        var folder = path.slice(0, slash) || "/";
        if (home && (folder === home || folder.indexOf(home + "/") === 0)) folder = "~" + folder.slice(home.length);
        results.push({kind: "file", id: path, title: path.slice(slash + 1), subtitle: folder, path: path});
    });
    return results.slice(0, max);
}

// Группы меню поиска при пустом поле: значок, ключи названия и пояснения таблицы строк.
var SEARCH_GROUPS = [
    {id: "apps", symbol: "apps", title: "searchApps", hint: "searchGroupAppsHint"},
    {id: "actions", symbol: "bolt", title: "searchActions", hint: "searchGroupActionsHint"},
    {id: "power", symbol: "power_settings_new", title: "searchGroupPower", hint: "searchGroupPowerHint"},
    {id: "settings", symbol: "settings", title: "searchSettings", hint: "searchGroupSettingsHint"}
];
function searchGroups(s) {
    return SEARCH_GROUPS.map(function(group) {
        return {kind: "group", id: group.id, key: "group:" + group.id, title: s[group.title], subtitle: s[group.hint], symbol: group.symbol};
    });
}

// Пункты группы `id`: приложения по алфавиту, действия группы, разделы «Настроек».
// Неизвестная группа — пустой список.
function searchGroupItems(id, apps, s) {
    var items = [];
    if (id === "apps") {
        items = (apps || []).slice().sort(function(a, b) { return String(a.name).localeCompare(String(b.name)); })
            .map(function(app) { return {kind: "app", id: app.id, title: app.name, subtitle: s.searchApp, icon: app.icon || ""}; });
    } else if (id === "settings") {
        items = SETTINGS_SECTIONS.map(function(section) { return {kind: "settings", id: section.id, title: s[section.label], subtitle: s.searchSettings}; });
    } else {
        items = SEARCH_ACTIONS.filter(function(action) { return action.group === id; })
            .map(function(action) { return {kind: "action", id: action.id, title: s[action.title], subtitle: s.searchAction}; });
    }
    return items.map(function(item) { item.key = item.kind + ":" + item.id; return item; });
}

// Строки меню поиска при пустом поле: группы или пункты открытой группы `group`, в том же
// виде, что строки результатов (`header`, `key`, `item`, `index`).
function searchBrowseRows(group, apps, s) {
    var items = group ? searchGroupItems(group, apps, s) : searchGroups(s);
    return items.map(function(item, index) { return {header: false, key: item.key, item: item, index: index}; });
}

// Найденные раньше файлы, подходящие под новый запрос по правилу `quietline-shell files`
// (`plocate -b -i`: имя файла содержит запрос без учёта регистра). Запрос короче двух символов
// файлов не ищет.
function searchFileMatches(files, query) {
    var needle = String(query || "").trim().toLowerCase();
    if (needle.length < 2) return [];
    return (files || []).filter(function(path) {
        return String(path).slice(String(path).lastIndexOf("/") + 1).toLowerCase().indexOf(needle) >= 0;
    });
}

// Высота списка поиска по строкам: заголовок раздела 26, вычисление 48, файл и группа (две
// строки текста) 44, остальные 40 px, поля списка сверху 6 и снизу 8; не больше `max`.
// Пустой список — 0.
var SEARCH_ROW_HEIGHTS = {calc: 48, file: 44, group: 44};
function searchListHeight(rows, max) {
    if (!rows || !rows.length) return 0;
    var height = 14;
    rows.forEach(function(row) { height += row.header ? 26 : textKey(SEARCH_ROW_HEIGHTS, row.item && row.item.kind, 40); });
    return Math.min(height, max);
}

// Стопки центра уведомлений: записи истории (новые сверху) одного приложения подряд не
// обязательно — группа встаёт на место своей самой новой записи, порядок внутри сохраняется.
function notificationGroups(history, keyOf) {
    var groups = [], byKey = {};
    (history || []).forEach(function(entry) {
        var key = keyOf(entry);
        if (!byKey[key]) { byKey[key] = {key: key, entries: []}; groups.push(byKey[key]); }
        byKey[key].entries.push(entry);
    });
    return groups;
}

// Сетка месяца для календаря: 6 недель по 7 дней, неделя начинается с `firstDay`
// (0 — воскресенье … 6 — суббота). Дни чужого месяца — `current: false`; `today` — сегодня.
function monthGrid(year, month, firstDay, today) {
    var first = new Date(year, month, 1);
    var shift = (first.getDay() - firstDay + 7) % 7;
    var cells = [];
    for (var i = 0; i < 42; i++) {
        var date = new Date(year, month, 1 - shift + i);
        cells.push({day: date.getDate(), current: date.getMonth() === month,
                    today: !!today && date.getFullYear() === today.year && date.getMonth() === today.month && date.getDate() === today.day});
    }
    return cells;
}

// Значок Wi‑Fi панели: дуги по сигналу активной точки, как в списке сетей; без данных о сигнале — `wifi`.
function barWifiSymbol(signal) {
    return signal === null || signal === undefined ? "wifi" : wifiSymbol(signal);
}

// Значок громкости панели: выключен, ноль, до трети, громче.
function volumeSymbol(volume, muted) {
    if (muted) return "volume_off";
    if (!(volume > 0.005)) return "volume_mute";
    return volume < 0.33 ? "volume_down" : "volume_up";
}

// Пространство для колеса мыши над номерами панели: следующее (`direction` > 0) или предыдущее
// после активного среди своих пространств монитора, без перехода по кругу; перенесённые с другого
// монитора пропускаются. Нет такого — `null`.
function wheelWorkspace(items, direction) {
    var own = (items || []).filter(function(item) { return !item.migrated; });
    var index = own.findIndex(function(item) { return item.active; });
    if (index < 0) return null;
    return own[index + (direction > 0 ? 1 : -1)] || null;
}

// Номера для «На пространство» меню окна: 1…N, где N — наибольший номер своего пространства
// монитора + 1, но не больше 10.
function moveTargets(items) {
    var top = 0;
    (items || []).forEach(function(item) { if (!item.migrated && item.number > top) top = item.number; });
    var result = [];
    for (var number = 1; number <= Math.min(10, top + 1); number++) result.push(number);
    return result;
}

// Уровень заряда для заливки батареи: `critical` — 10 % и ниже, `low` — 20 % и ниже, при зарядке
// и выше — `normal`.
function batteryLevel(percent, charging) {
    if (charging) return "normal";
    if (percent <= 10) return "critical";
    return percent <= 20 ? "low" : "normal";
}

// Приложения, записывающие микрофон, по свойствам входных аудиопотоков Pipewire: `application.name`
// (иначе `node.name`) без повторов; потоки самой оболочки (Quickshell) не считаются.
function micUsers(streams) {
    var names = [];
    (streams || []).forEach(function(props) {
        if (!props) return;
        var name = String(props["application.name"] || props["node.name"] || "");
        var binary = String(props["application.process.binary"] || "").toLowerCase();
        if (!name || /^quickshell$/i.test(name) || binary === "quickshell" || binary === "qs") return;
        if (names.indexOf(name) < 0) names.push(name);
    });
    return names;
}

// Целый ли масштаб окна (1, 2, 3): при нём текст рисуется нативно с хинтингом fontconfig, при дробном
// или неизвестном (0, отсутствует) — кривыми, чтобы буквы стояли на одной базовой линии.
function integerScale(ratio) {
    var value = Number(ratio);
    return value >= 1 && Math.abs(value - Math.round(value)) < 0.01;
}

// Текст для `Text.StyledText`: `&`, `<`, `>` и `"` экранируются, чтобы чужая строка (имя окна,
// приложения) не стала разметкой.
function escapeMarkup(value) {
    return String(value === undefined || value === null ? "" : value)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
