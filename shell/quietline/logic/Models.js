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
        // Специальные пространства (scratchpad) имеют отрицательный ID и в док монитора не входят.
        if (window.workspace_id < 0) continue;
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

// Громкость PipeWire в пределах 0…150 %.
function clampVolume(value) { return Math.max(0, Math.min(1.5, value)); }

// Время батареи: «1 ч 20 мин» или «10 мин», не меньше минуты.
function formatDuration(seconds, s) {
    var minutes = Math.max(1, Math.round(seconds / 60)), hours = Math.floor(minutes / 60);
    return hours ? format(s.durationHoursMinutes, [hours, minutes % 60]) : format(s.durationMinutes, [minutes]);
}

// Биты `modmask` Hyprland в том порядке, в каком модификаторы называют.
var MODIFIERS = [[64, "Super"], [4, "Ctrl"], [8, "Alt"], [1, "Shift"]];

// Описание известной команды привязки; неизвестная остаётся как есть.
function bindAction(command, s) {
    var match;
    if ((match = /^quietline-engine switch (\d+)$/.exec(command))) return format(s.bindSwitch, [match[1]]);
    if ((match = /^quietline-engine move (\d+)$/.exec(command))) return format(s.bindMove, [match[1]]);
    if (command === "quietline-engine toggle") return s.bindToggle;
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
    return command;
}

// Приложения, на которые ссылаются привязки Hyprland: команда -> ID desktop entry.
var BIND_APPS = {dolphin: "org.kde.dolphin", ghostty: "com.mitchellh.ghostty"};

// Памятка сочетаний из `hyprctl binds -j`: `[{keys: "Super+Shift+1", action}]`.
// Привязки к приложениям, которых нет среди `entries`, в памятку не входят.
function describeBinds(binds, s, entries) {
    return (binds || []).filter(function(bind) {
        var command = bind.arg || bind.dispatcher || "";
        var appId = Object.prototype.hasOwnProperty.call(BIND_APPS, command) ? BIND_APPS[command] : null;
        return !appId || !!desktopFor(appId, entries || []);
    }).map(function(bind) {
        var keys = MODIFIERS.filter(function(item) { return (bind.modmask & item[0]) !== 0; })
            .map(function(item) { return item[1]; });
        keys.push(bind.key);
        return {keys: keys.join("+"), action: bindAction(bind.arg || bind.dispatcher || "", s)};
    });
}

// Действия сеанса после корректного закрытия окон (`quietline-shell session`).
var SESSION_ACTIONS = ["logout", "reboot", "poweroff"];
var SESSION_LABEL_KEYS = {logout: "sessionLogout", reboot: "sessionReboot", poweroff: "sessionPoweroff"};
var SESSION_QUESTION_KEYS = {logout: "sessionLogoutQuestion", reboot: "sessionRebootQuestion", poweroff: "sessionPoweroffQuestion"};

// Подпись и вопрос подтверждения действия сеанса; неизвестное действие — пустая строка.
function sessionLabel(action, s) { var key = textKey(SESSION_LABEL_KEYS, action, ""); return key ? s[key] : ""; }
function sessionQuestion(action, s) { var key = textKey(SESSION_QUESTION_KEYS, action, ""); return key ? s[key] : ""; }

// Приложения, окна которых не закрылись: «Не завершились: Code (notes.md), Telegram».
function remainingText(remaining, s) {
    var names = [];
    (remaining || []).forEach(function(window) {
        var name = window.app || s.sessionUntitledWindow;
        var label = window.title && window.title !== name ? name + " (" + window.title + ")" : name;
        if (names.indexOf(label) < 0) names.push(label);
    });
    return names.length ? format(s.sessionRemaining, [names.join(", ")]) : "";
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

// Разделы окна «Настройки» и системные действия для поиска: ключи подписи и ключевых слов
// таблицы строк. Ключевые слова содержат слова обоих языков.
var SETTINGS_SECTIONS = [
    {id: "network", label: "settingsNetwork", keywords: "settingsNetworkKeywords"},
    {id: "audio", label: "settingsAudio", keywords: "settingsAudioKeywords"},
    {id: "display", label: "settingsDisplay", keywords: "settingsDisplayKeywords"},
    {id: "bluetooth", label: "settingsBluetooth", keywords: "settingsBluetoothKeywords"},
    {id: "power", label: "settingsPower", keywords: "settingsPowerKeywords"},
    {id: "region", label: "settingsRegion", keywords: "settingsRegionKeywords"},
    {id: "shortcuts", label: "settingsShortcuts", keywords: "settingsShortcutsKeywords"},
    {id: "about", label: "settingsAbout", keywords: "settingsAboutKeywords"}
];
// Прежние идентификаторы разделов и раздел, который открывается вместо них.
var SECTION_ALIASES = {keyboard: "region"};
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

var SEARCH_ACTIONS = [
    {id: "lock", title: "actionLock", keywords: "actionLockKeywords"},
    {id: "logout", title: "actionLogout", keywords: "actionLogoutKeywords"},
    {id: "reboot", title: "actionReboot", keywords: "actionRebootKeywords"},
    {id: "poweroff", title: "actionPoweroff", keywords: "actionPoweroffKeywords"},
    {id: "screenshot", title: "actionScreenshot", keywords: "actionScreenshotKeywords"},
    {id: "clipboard", title: "actionClipboard", keywords: "actionClipboardKeywords"}
];

// Насколько `text` подходит под `needle`: начало строки — 3, начало слова — 2, где-то внутри — 1.
function matchScore(text, needle) {
    var value = String(text || "").toLowerCase();
    if (!needle || value.indexOf(needle) < 0) return 0;
    if (value.indexOf(needle) === 0) return 3;
    return (" " + value).indexOf(" " + needle) >= 0 ? 2 : 1;
}

// Результаты поиска: вычисление, затем приложения, действия и разделы настроек по совпадению,
// затем файлы. Пустой запрос — все приложения. `home` сокращается до «~» в путях файлов.
function searchResults(query, apps, files, home, limit, s) {
    var needle = String(query || "").trim().toLowerCase();
    var max = limit || 40;
    if (!needle) return (apps || []).slice(0, max).map(function(app) { return {kind: "app", id: app.id, title: app.name, subtitle: s.searchApp}; });
    var scored = [];
    (apps || []).forEach(function(app) {
        var score = Math.max(matchScore(app.name, needle), matchScore(app.id, needle) - 0.5);
        if (score > 0) scored.push({kind: "app", id: app.id, title: app.name, subtitle: s.searchApp, score: score + 0.2});
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
