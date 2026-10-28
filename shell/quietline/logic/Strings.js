.pragma library

// Видимые тексты оболочки на русском и английском. Ключи плоские, camelCase; подстановки
// `{0}`, `{1}` заполняет `format`. У каждого ключа есть оба перевода с одинаковыми
// подстановками (проверяет tests/shell/strings.test.cjs). Используются в QML через
// синглтон `Lang` (`Lang.s`) и в тестах Node.

// Ключевые слова поиска одинаковы в обоих языках: раздел и действие находятся по слову любого языка.
var KEYWORDS = {
    settingsNetworkKeywords: "wi-fi wifi ethernet интернет профиль адрес сеть network internet profile address",
    settingsAudioKeywords: "громкость микрофон динамики звук sound audio volume microphone speakers",
    settingsDisplayKeywords: "монитор яркость дисплей экран display monitor brightness screen",
    settingsBluetoothKeywords: "наушники блютуз bluetooth headphones",
    settingsPowerKeywords: "батарея энергосбережение питание power battery energy",
    settingsKeyboardKeywords: "раскладка язык клавиатура keyboard layout language",
    settingsShortcutsKeywords: "клавиши горячие памятка сочетания shortcuts hotkeys keys",
    settingsAboutKeywords: "версия система компьютер about version system computer",
    actionLockKeywords: "блокировка экран lock screen",
    actionLogoutKeywords: "выход logout log out sign out",
    actionRebootKeywords: "перезагрузка reboot restart",
    actionPoweroffKeywords: "выключение shutdown poweroff shut down",
    actionScreenshotKeywords: "скриншот screenshot снимок region",
    actionClipboardKeywords: "буфер обмена clipboard history",
    clipboardImageKeywords: "изображение image"
};

function withKeywords(strings) {
    for (var key in KEYWORDS) strings[key] = KEYWORDS[key];
    return strings;
}

var STRINGS = {
    ru: withKeywords({
        clockTitle: "Формат времени",

        engineInvalidNumber: "Нет такого пространства: номера от 1 до 10",
        engineCommandFailed: "Сервис окон не выполнил команду",
        engineInvalidRequest: "Сервис окон не принял команду",
        engineUnknownMethod: "Сервис окон не знает эту команду",
        engineInternalError: "Внутренняя ошибка сервиса окон",
        engineCommandNotDone: "Команда не выполнена",
        engineStateError: "Ошибка сервиса окон: {0}",
        engineUnreadable: "Не удалось прочитать ответ сервиса окон",
        engineMalformed: "Некорректный ответ сервиса окон",
        engineIncompleteEvent: "Сервис окон прислал неполное состояние",
        engineIncompleteResult: "Сервис окон вернул неполное состояние",

        workspaceMigrated: "{0} · {1}",
        appUnnamed: "Приложение",
        layoutUnknown: "…",

        deviceNoCable: "Нет кабеля",
        deviceConnected: "Подключено",
        deviceConnecting: "Подключение…",
        deviceDisconnected: "Отключено",
        deviceUnavailable: "Недоступно",

        profileFieldName: "Укажите имя профиля длиной до 64 символов",
        profileFieldMethod: "Неизвестный способ настройки адреса",
        profileFieldPrefix: "Укажите префикс сети, например 10.42.0.5/24",
        profileFieldAddress: "Некорректный адрес IPv4",
        profileFieldGateway: "Некорректный адрес шлюза",
        profileFieldDns: "Некорректный адрес DNS",
        profileFieldProfile: "Некорректные данные профиля",

        networkStatusFailed: "Состояние сети недоступно",
        networkScanFailed: "Не удалось найти сети Wi-Fi",
        networkRadioFailed: "Не удалось переключить Wi-Fi",
        networkConnectFailed: "Не удалось подключиться к Wi-Fi",
        networkSaveFailed: "Профиль не сохранён",
        networkDeleteFailed: "Профиль не удалён",
        networkApplyFailed: "Конфигурация не применена",
        networkConfirmFailed: "Конфигурация не подтверждена",
        networkRollbackFailed: "Конфигурация не возвращена",
        networkActionFailed: "Сетевое действие не выполнено",

        durationHoursMinutes: "{0} ч {1} мин",
        durationMinutes: "{0} мин",

        bindSwitch: "Открыть пространство {0}",
        bindMove: "Перенести окно на пространство {0}",
        bindToggle: "Сменить режим «Окна / Тайлы»",
        bindTerminal: "Открыть терминал",
        bindLock: "Заблокировать сеанс",
        bindQuit: "Выйти из приложения",
        bindKill: "Принудительно завершить приложение",
        bindClipboard: "История буфера",
        bindScreenshotOutput: "Снимок монитора в файл и буфер",
        bindScreenshotRegion: "Снимок области с разметкой",
        bindSearch: "Открыть поиск",
        bindShortcuts: "Памятка сочетаний клавиш",
        bindSettings: "Открыть окно «Настройки»",
        bindDolphin: "Открыть Dolphin",

        sessionLogout: "Выйти из сеанса",
        sessionReboot: "Перезагрузить",
        sessionPoweroff: "Выключить",
        sessionLogoutQuestion: "Закрыть все приложения и выйти из сеанса?",
        sessionRebootQuestion: "Закрыть все приложения и перезагрузить компьютер?",
        sessionPoweroffQuestion: "Закрыть все приложения и выключить компьютер?",
        sessionAction: "Действие сеанса",
        sessionActionFailed: "{0} не удалось",
        sessionRemaining: "Не завершились: {0}. Сохраните документы и повторите.",
        sessionUntitledWindow: "окно без названия",

        clipboardImage: "Изображение",
        clipboardImageDetails: "Изображение {0} · {1}×{2}",

        searchApp: "Приложение",
        searchAction: "Действие",
        searchSettings: "Настройки",
        searchCalcHint: "Enter — скопировать результат",

        settingsNetwork: "Сеть",
        settingsAudio: "Звук",
        settingsDisplay: "Экран и яркость",
        settingsBluetooth: "Bluetooth",
        settingsPower: "Питание",
        settingsKeyboard: "Клавиатура",
        settingsShortcuts: "Сочетания клавиш",
        settingsAbout: "О системе",

        actionLock: "Заблокировать",
        actionLogout: "Выйти из сеанса",
        actionReboot: "Перезагрузить",
        actionPoweroff: "Выключить",
        actionScreenshot: "Снимок области экрана",
        actionClipboard: "История буфера",

        regionReadFailed: "Настройки языка и региона недоступны",
        regionSaveFailed: "Настройки языка и региона не сохранены"
    }),
    en: withKeywords({
        clockTitle: "Time format",

        engineInvalidNumber: "No such workspace: numbers 1 to 10",
        engineCommandFailed: "The window service did not run the command",
        engineInvalidRequest: "The window service rejected the command",
        engineUnknownMethod: "The window service does not know this command",
        engineInternalError: "Window service internal error",
        engineCommandNotDone: "Command failed",
        engineStateError: "Window service error: {0}",
        engineUnreadable: "Could not read the window service reply",
        engineMalformed: "Malformed window service reply",
        engineIncompleteEvent: "The window service sent an incomplete state",
        engineIncompleteResult: "The window service returned an incomplete state",

        workspaceMigrated: "{0} · {1}",
        appUnnamed: "Application",
        layoutUnknown: "…",

        deviceNoCable: "No cable",
        deviceConnected: "Connected",
        deviceConnecting: "Connecting…",
        deviceDisconnected: "Disconnected",
        deviceUnavailable: "Unavailable",

        profileFieldName: "Enter a profile name up to 64 characters",
        profileFieldMethod: "Unknown address method",
        profileFieldPrefix: "Enter a network prefix, for example 10.42.0.5/24",
        profileFieldAddress: "Invalid IPv4 address",
        profileFieldGateway: "Invalid gateway address",
        profileFieldDns: "Invalid DNS address",
        profileFieldProfile: "Invalid profile data",

        networkStatusFailed: "Network status is unavailable",
        networkScanFailed: "Could not find Wi-Fi networks",
        networkRadioFailed: "Could not switch Wi-Fi",
        networkConnectFailed: "Could not connect to Wi-Fi",
        networkSaveFailed: "Profile not saved",
        networkDeleteFailed: "Profile not deleted",
        networkApplyFailed: "Configuration not applied",
        networkConfirmFailed: "Configuration not confirmed",
        networkRollbackFailed: "Configuration not restored",
        networkActionFailed: "Network action failed",

        durationHoursMinutes: "{0} h {1} min",
        durationMinutes: "{0} min",

        bindSwitch: "Open workspace {0}",
        bindMove: "Move window to workspace {0}",
        bindToggle: "Switch “Windows / Tiles” mode",
        bindTerminal: "Open terminal",
        bindLock: "Lock session",
        bindQuit: "Quit application",
        bindKill: "Force quit application",
        bindClipboard: "Clipboard history",
        bindScreenshotOutput: "Screenshot monitor to file and clipboard",
        bindScreenshotRegion: "Screenshot region with markup",
        bindSearch: "Open search",
        bindShortcuts: "Keyboard shortcuts",
        bindSettings: "Open Settings",
        bindDolphin: "Open Dolphin",

        sessionLogout: "Log out",
        sessionReboot: "Restart",
        sessionPoweroff: "Shut down",
        sessionLogoutQuestion: "Close all applications and log out?",
        sessionRebootQuestion: "Close all applications and restart the computer?",
        sessionPoweroffQuestion: "Close all applications and shut down the computer?",
        sessionAction: "Session action",
        sessionActionFailed: "{0} failed",
        sessionRemaining: "Still running: {0}. Save your documents and try again.",
        sessionUntitledWindow: "untitled window",

        clipboardImage: "Image",
        clipboardImageDetails: "Image {0} · {1}×{2}",

        searchApp: "Application",
        searchAction: "Action",
        searchSettings: "Settings",
        searchCalcHint: "Enter — copy the result",

        settingsNetwork: "Network",
        settingsAudio: "Sound",
        settingsDisplay: "Display and brightness",
        settingsBluetooth: "Bluetooth",
        settingsPower: "Power",
        settingsKeyboard: "Keyboard",
        settingsShortcuts: "Keyboard shortcuts",
        settingsAbout: "About",

        actionLock: "Lock",
        actionLogout: "Log out",
        actionReboot: "Restart",
        actionPoweroff: "Shut down",
        actionScreenshot: "Screenshot a region",
        actionClipboard: "Clipboard history",

        regionReadFailed: "Language and region settings are unavailable",
        regionSaveFailed: "Language and region settings not saved"
    })
};

// Таблица языка: английская, поверх неё русская при `ru`; любой другой язык — английская.
// Ключ, которого нет в русской таблице, берётся из английской.
function table(language) {
    var result = {};
    var key;
    for (key in STRINGS.en) result[key] = STRINGS.en[key];
    if (language === "ru") for (key in STRINGS.ru) result[key] = STRINGS.ru[key];
    return result;
}

// Подстановка `{n}` из `args[n]`; подстановка без значения остаётся как есть.
function format(template, args) {
    return String(template).replace(/\{(\d+)\}/g, function(match, index) {
        var value = (args || [])[Number(index)];
        return value === undefined || value === null ? match : String(value);
    });
}

// Шаблоны Qt для `Date.toLocaleTimeString` / `toLocaleDateString`; неизвестное значение —
// 24 часа и ISO-дата.
function timeFormat(clock) { return clock === "12h" ? "h:mm AP" : "HH:mm"; }

function dateFormat(date) {
    if (date === "dmy") return "dd.MM.yyyy";
    if (date === "mdy") return "MM/dd/yyyy";
    return "yyyy-MM-dd";
}

// Имя локали Qt для названий дней и месяцев.
function localeName(language) { return language === "ru" ? "ru_RU" : "en_US"; }
