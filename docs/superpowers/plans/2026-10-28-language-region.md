# Языки и регион — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Статус:** выполнен, ждёт живой проверки (ветка `feature/language-installer`): `quietline-shell region`, оболочка на двух языках, раздел «Язык и регион», раскладки `us,ru`, док без неустановленных программ — `scripts/smoke-language.md`, `docs/backlog.md`.

**Goal:** оболочка Quietline на русском или английском по выбору, раздел «Язык и регион» в окне «Настройки» (язык системы, формат даты и времени, раскладки), раскладки `us,ru` всегда, английские сообщения в терминале при любом языке и док без неустановленных программ.

**Architecture:**
- Настройки региона хранит `quietline-shell region` в `$XDG_CONFIG_HOME/quietline/region.json`. При записи он же обновляет `LANG` в `$XDG_CONFIG_HOME/locale.conf` (для программ после повторного входа), пишет `$XDG_CONFIG_HOME/quietline/keyboard.lua` (его читает `quietline.lua` при каждой загрузке конфигурации Hyprland) и применяет раскладки сразу через `hyprctl eval`.
- Строки оболочки — таблицы `ru`/`en` в `logic/Strings.js`; синглтон `Lang.qml` читает настройки и отдаёт таблицу текущего языка `Lang.s`, поэтому смена языка сразу перерисовывает привязанные тексты. Функции `Models.js`, возвращающие текст, получают таблицу последним параметром.
- Уведомления, которые шлёт сам `quietline-shell`, берут текст по языку из `region.json`.

**Tech Stack:** Python 3.14 (стандартная библиотека), pytest; Quickshell 0.3.2 (QML, Qt 6), `node --test`; Hyprland 0.55 Lua-конфиг и `hyprctl eval`; fish.

**Spec:** `docs/superpowers/specs/2026-10-28-language-and-installer-design.md` — «Часть 1. Языки и регион»; основная спека `docs/superpowers/specs/2026-10-19-quietline-desktop-design.md`.

**Основа:** этапы 1–4 в `main`. Ветка — `feature/language-installer` (в ней уже лежит дизайн этапа 5). Установщик — отдельный план, после этого.

## Global Constraints

- Минимальные версии: Hyprland 0.55, Quickshell 0.3.2. `hyprctl eval`, опции `input.kb_layout`/`kb_options` и `Date.toLocale*String(locale, format)` проверяются в документации этих версий (вики Hyprland — переключатель версии; `https://quickshell.org/docs/v0.3.2/`). Несовместимость — стоп и правка плана.
- Языки — только `ru` и `en`. Неизвестный язык везде трактуется как `en`.
- Раскладки — всегда ровно две: `us` и `ru`, меняется только порядок. По умолчанию `["us", "ru"]` и `grp:lalt_lshift_toggle` (левые `Alt+Shift`).
- Сочетания переключения — только `grp:lalt_lshift_toggle` (левые Alt+Shift), `grp:alt_shift_toggle` (Alt+Shift), `grp:ctrl_shift_toggle` (Ctrl+Shift), `grp:caps_toggle` (Caps Lock). `Super+Space` занят поиском и в список не входит.
- Формат времени: `24h` → `HH:mm`, `12h` → `h:mm AP`. Формат даты: `dmy` → `dd.MM.yyyy`, `ymd` → `yyyy-MM-dd`, `mdy` → `MM/dd/yyyy`. Без файла настроек: русский — `24h` и `dmy`, английский — `12h` и `mdy`.
- Язык по умолчанию без `region.json`: `ru`, если `LANG` начинается с `ru`, иначе `en`.
- Формат даты и времени управляет только датами оболочки (часы панели, экран блокировки); остальные программы следуют `LANG`.
- В терминале fish сообщения программ всегда английские (`LC_MESSAGES=en_US.UTF-8`, `LANGUAGE` снят), форматы — по `LANG`.
- Комментарии и docstring — по-русски; вывод `quietline-shell` в консоль (JSON, ошибки) — по-английски. Видимые пользователю тексты оболочки и уведомлений — на выбранном языке.
- Папка держит не больше восьми записей: в `src/quietline_shell/` их уже восемь, поэтому настройки региона и тексты уведомлений живут в `config.py`, а не в новом модуле.
- Тесты: `uv run --python 3.14 pytest`, `node --test 'tests/shell/*.test.cjs'`. QML проверяется только в живом сеансе — пункты в `scripts/smoke-language.md` и `docs/backlog.md`.

## Review Focus

1. **Нет `region.json`, он повреждён или в нём неизвестный язык:** оболочка не остаётся с пустыми подписями — берёт язык по `LANG` или английский; CLI отвечает `{"error"}` и не перезаписывает файл. Тесты `test_region_defaults_follow_lang`, `test_corrupt_region_is_reported_without_overwriting` (Task 1), `test_unknown_language_falls_back_to_english` (Task 3).
2. **У пользователя свой `~/.config/locale.conf` с `LC_TIME`, `LC_COLLATE` и т.п.:** меняется только строка `LANG`, остальное сохраняется. Тест `test_locale_conf_keeps_other_variables` (Task 1).
3. **Hyprland не запущен или не знает `hyprctl eval`:** настройки всё равно сохраняются, ответ `"applied": false`, ошибки нет; при следующем входе раскладки берутся из `keyboard.lua`. Тест `test_keyboard_apply_failure_still_saves` (Task 1).
4. **Строка с подстановкой есть в одном языке, а в другом нет или с другим числом `{0}`, `{1}`:** тест паритета ключей и подстановок `test_both_languages_have_the_same_keys_and_placeholders` (Task 3); недостающий ключ на `ru` берётся из `en`, а не `undefined`.
5. **Забытая русская строка в QML после перевода:** при английском языке пользователь видит её посреди английского интерфейса. Тест `test_qml_and_models_have_no_cyrillic_string_literals` (Task 4).

---

## Файлы

- `src/quietline_shell/config.py` — настройки региона, `locale.conf`, `keyboard.lua`, применение раскладок, тексты уведомлений.
- `src/quietline_shell/__main__.py` — подкоманда `region`.
- `src/quietline_shell/capture.py`, `session.py` — уведомления через тексты по языку.
- `config/hyprland/quietline.lua` — раскладки из `keyboard.lua` с запасными значениями.
- `config/fish/quietline-locale.fish` — английские сообщения в терминале (ставит установщик).
- `shell/quietline/logic/Strings.js` — таблицы строк `ru`/`en`, форматы даты и времени.
- `shell/quietline/Lang.qml`, `shell/quietline/qmldir` — синглтон языка и региона.
- `shell/quietline/logic/Models.js` — текстовые функции с таблицей строк, док и памятка без неустановленных программ.
- Все QML-файлы с текстом (список — Task 4).
- `shell/quietline/settings/SettingsWindow.qml` — раздел «Язык и регион» вместо «Клавиатуры».
- `tests/helper/test_region.py`, `tests/shell/strings.test.cjs`, `tests/shell/models.test.cjs`.
- `scripts/smoke-language.md`, `docs/backlog.md`, основная спека, `AGENTS.md`, `README.md`, `CHANGELOG.md`.

---

### Task 1: `quietline-shell region` — настройки, `locale.conf`, `keyboard.lua`

**Files:**
- Modify: `src/quietline_shell/config.py`, `src/quietline_shell/__main__.py` (docstring и подкоманда)
- Test: `tests/helper/test_region.py`

**Interfaces:**
- Produces (в `config.py`):
  - `LANGUAGES = ("ru", "en")`, `CLOCKS = ("24h", "12h")`, `DATES = ("dmy", "ymd", "mdy")`, `LAYOUTS = ("us", "ru")`, `TOGGLES = ("grp:lalt_lshift_toggle", "grp:alt_shift_toggle", "grp:ctrl_shift_toggle", "grp:caps_toggle")`;
  - `default_region_path() -> Path` — `$XDG_CONFIG_HOME/quietline/region.json`;
  - `default_region(lang: str | None) -> dict` — `{"language", "clock", "date", "layouts", "toggle"}` по правилам Global Constraints;
  - `load_region(path: Path, lang: str | None = None) -> dict` — без файла `default_region(lang)`; повреждённый файл или чужой формат — `ValueError` с путём; файл `{"version": 1, "language", "clock", "date", "layouts", "toggle"}`;
  - `validated_region(data: object, current: dict) -> dict` — частичное обновление поверх `current`; неизвестное поле или значение — `ValueError`; `layouts` — перестановка `LAYOUTS`;
  - `save_region(path: Path, region: dict, config_home: Path) -> None` — атомарно (`atomic_write_json`) пишет `region.json`, затем `config_home/locale.conf` и `config_home/quietline/keyboard.lua`;
  - `keyboard_lua(region: dict) -> str` — `return { kb_layout = "us,ru", kb_options = "grp:lalt_lshift_toggle" }\n`;
  - `apply_keyboard(region: dict) -> bool` — при `HYPRLAND_INSTANCE_SIGNATURE` запускает `["hyprctl", "eval", 'hl.config({ input = { kb_layout = "…", kb_options = "…" } })']`; `True` только при коде 0; без Hyprland, без `hyprctl`, по таймауту — `False`.
- CLI: `quietline-shell region [--set JSON] [--path PATH]` → `{"language", "clock", "date", "layouts", "toggle"}`; с `--set` ещё `"applied": bool`. Ошибка — `{"error"}` и код 1.
- `locale.conf`: строка `LANG=ru_RU.UTF-8` или `LANG=en_US.UTF-8`; остальные строки файла сохраняются в прежнем порядке, нет строки `LANG` — дописывается.

- [x] **Step 1: Написать падающие тесты** в `tests/helper/test_region.py`:
  - `test_region_defaults_follow_lang` — `LANG=ru_RU.UTF-8` → `{"language": "ru", "clock": "24h", "date": "dmy", "layouts": ["us", "ru"], "toggle": "grp:lalt_lshift_toggle"}`; `LANG=de_DE.UTF-8` и `None` → `en`, `12h`, `mdy`;
  - `test_region_roundtrip_and_partial_update` — `--set '{"clock": "12h"}'` меняет только `clock`;
  - `test_invalid_region_values_are_rejected` — параметризация: `language: "de"`, `clock: "25h"`, `layouts: ["us"]`, `layouts: ["us", "us"]`, `toggle: "grp:win_space_toggle"`, лишнее поле → `ValueError`, файл не создан;
  - `test_corrupt_region_is_reported_without_overwriting` — битый JSON → CLI `{"error"}`, код 1, содержимое файла прежнее;
  - `test_locale_conf_keeps_other_variables` — `locale.conf` с `LC_TIME=en_GB.UTF-8\nLANG=en_US.UTF-8\n` после смены на `ru` → `LC_TIME=en_GB.UTF-8\nLANG=ru_RU.UTF-8\n`;
  - `test_keyboard_lua_follows_order_and_toggle` — `layouts: ["ru", "us"]`, `grp:caps_toggle` → `kb_layout = "ru,us"`, `kb_options = "grp:caps_toggle"`;
  - `test_keyboard_apply_failure_still_saves` — без `HYPRLAND_INSTANCE_SIGNATURE` и с `hyprctl`, возвращающим 1: `"applied": false`, файлы записаны, код 0.
- [x] **Step 2: Убедиться, что тесты падают.** `uv run --python 3.14 pytest tests/helper/test_region.py -v` → FAIL: нет `default_region`.
- [x] **Step 3: Реализовать** функции в `config.py` и подкоманду в `__main__.py`; docstring модуля и CLI дописать.
- [x] **Step 4: Убедиться, что тесты проходят.** `uv run --python 3.14 pytest tests/helper -v` → PASS.
- [x] **Step 5: Коммит** `feat(shell): настройки языка и региона в quietline-shell`.

### Task 2: Уведомления `quietline-shell` на языке системы

**Files:**
- Modify: `src/quietline_shell/config.py`, `capture.py`, `session.py`, `__main__.py`
- Test: `tests/helper/test_region.py`, существующие `test_capture.py`, `test_session.py`

**Interfaces:**
- Consumes: `load_region`, `default_region_path` (Task 1).
- Produces: `NOTIFICATION_TEXTS: dict[str, dict[str, str]]` (`ru`, `en`) и `notification_text(key: str, **values: str) -> str` — язык из `region.json`, при ошибке чтения — по `LANG`. Ключи: `capture_failed`, `save_failed`, `copy_failed`, `screenshot_saved`, `editor_failed`, `lock_failed`, `app_in_background` (`{app}`), `app_in_background_hint`, `app_unnamed`.
- Английский текст: «Screenshot saved and copied», «Could not take a screenshot», «Could not save the screenshot», «Screenshot saved but not copied», «Could not open the screenshot editor», «Could not lock the session», «“{app}” keeps running in the background», «Super+Shift+Q will force it to quit.», «Application».

- [x] **Step 1: Написать падающие тесты:** `test_notification_text_follows_region_language` — `region.json` с `en` → `notification_text("screenshot_saved") == "Screenshot saved and copied"`; без файла и `LANG=ru_RU.UTF-8` → русский текст; `test_notification_texts_have_both_languages` — одинаковые ключи и подстановки. В `test_capture.py` один существующий тест уведомления переключить на проверку через `notification_text`.
- [x] **Step 2: Убедиться, что тесты падают.** `uv run --python 3.14 pytest tests/helper -v` → FAIL.
- [x] **Step 3: Реализовать** и заменить все 9 вызовов `notify(...)` с русским текстом на `notification_text(...)`. Подробности ошибок (`str(error)`, «satty is not installed») остаются английскими.
- [x] **Step 4: Убедиться, что тесты проходят.** `uv run --python 3.14 pytest -q` → PASS.
- [x] **Step 5: Коммит** `feat(shell): уведомления quietline-shell на языке системы`.

### Task 3: Таблицы строк, синглтон `Lang` и текстовые функции `Models.js`

**Files:**
- Create: `shell/quietline/logic/Strings.js`, `shell/quietline/Lang.qml`, `tests/shell/strings.test.cjs`
- Modify: `shell/quietline/qmldir` (`singleton Lang 1.0 Lang.qml`), `shell/quietline/logic/Models.js`, `tests/shell/models.test.cjs`

**Interfaces:**
- Produces (`Strings.js`, `.pragma library`):
  - `STRINGS = {ru: {…}, en: {…}}` — плоские ключи camelCase; подстановки `{0}`, `{1}`;
  - `table(language: string) -> object` — `en`, поверх него `ru` при `language === "ru"`; иначе `en`;
  - `format(template: string, args: array) -> string`;
  - `timeFormat(clock: string) -> string`, `dateFormat(date: string) -> string` — шаблоны из Global Constraints; `localeName(language) -> "ru_RU" | "en_US"`.
- Produces (`Lang.qml`, `Singleton` с `Process`): свойства `language`, `clock`, `date`, `layouts`, `toggle`, `error`; `readonly property var s: Strings.table(language)`; функции `f(template, ...args)`, `time(date)`, `shortDate(date)`, `longDate(date)` (`dddd, d MMMM` в локали языка через `date.toLocaleDateString(Qt.locale(…), …)`), `update(changes: object)` — `quietline-shell region --set JSON`, затем перечитывает настройки; ошибка — в `error`. При старте и после `update` читает `quietline-shell region`; пока ответа нет — язык по `LANG` окружения (`Quickshell.env("LANG")`, проверить в документации 0.3.2), чтобы русская оболочка не мелькала английским при старте.
- `Models.js`: таблицы `ERROR_TEXTS`, `NETWORK_ACTION_TEXTS`, `PROFILE_FIELD_TEXTS`, `SESSION_LABELS`, `SESSION_QUESTIONS` переезжают в `Strings.js`. Функции с текстом получают таблицу `s` последним параметром: `errorText(error, s)`, `stateError(state, s)`, `decodeMessage(line, revision, freshConnection, s)`, `workspaceItems(state, name, s)`, `groupApps(windows, monitor, pinned, entries, s)`, `layoutCode(keyboard, names, s)`, `deviceLabel(device, s)`, `networkErrorText(kind, response, s)`, `formatDuration(seconds, s)`, `bindAction(command, s)`, `describeBinds(binds, s, entries)` (третий параметр — Task 6), `remainingText(remaining, s)`, `sessionErrorText(action, detail, s)`, `clipboardMatches(entries, query, s)`, `clipboardImageLabel(preview, s)`, `searchResults(query, apps, files, home, limit, s)`. `SETTINGS_SECTIONS` и `SEARCH_ACTIONS` хранят ключи подписи и ключевые слова на обоих языках, поиск находит раздел по слову любого языка.

- [x] **Step 1: Написать падающие тесты** в `tests/shell/strings.test.cjs`:
  - `test_both_languages_have_the_same_keys_and_placeholders` — множества ключей `ru` и `en` равны; для каждого ключа множество `{n}` совпадает;
  - `test_unknown_language_falls_back_to_english` — `table("de").clockTitle === table("en").clockTitle`; ключ, удалённый из `ru` в копии таблиц, берётся из `en`;
  - `test_formats_match_the_spec` — `timeFormat("24h") === "HH:mm"`, `timeFormat("12h") === "h:mm AP"`, `dateFormat("dmy") === "dd.MM.yyyy"`, `"ymd" → "yyyy-MM-dd"`, `"mdy" → "MM/dd/yyyy"`;
  - `test_format_substitutes_in_order` — `format("{0} из {1}", [1, 2]) === "1 из 2"`.
  В `models.test.cjs` существующие проверки текстов вызывать с `table("ru")` (ожидания прежние) и добавить по одной проверке на `table("en")` для `errorText`, `bindAction`, `remainingText`, `searchResults` (раздел «Network» находится по слову «сеть» и по «network»).
- [x] **Step 2: Убедиться, что тесты падают.** `node --test 'tests/shell/*.test.cjs'` → FAIL.
- [x] **Step 3: Реализовать** `Strings.js`, перенос таблиц и параметр `s` в `Models.js`, `Lang.qml`. Тест загружает `Strings.js` тем же способом, что `Models.js` (`vm`, без `.pragma`); `Models.js` в тестах получает таблицы через аргумент, а не через импорт.
- [x] **Step 4: Убедиться, что тесты проходят.** `node --test 'tests/shell/*.test.cjs'` → PASS.
- [x] **Step 5: Коммит** `feat(shell): таблицы строк на русском и английском`.

### Task 4: Перевод всех компонентов оболочки

**Files:**
- Modify: `bar/TopBar.qml`, `dock/Dock.qml`, `clipboard/ClipboardPanel.qml`, `clipboard/ClipboardService.qml`, `services/DesktopModel.qml`, `services/EngineClient.qml`, `system/NetworkService.qml`, `system/PowerService.qml`, `session/PowerMenu.qml`, `session/KillConfirm.qml`, `panels/*.qml`, `search/SearchPanel.qml`, `search/SearchService.qml`, `lock/LockScreen.qml`, `lock/LockSurface.qml`, `notifications/NotificationPopups.qml`, `controls/ShellButton.qml`, `settings/SettingsWindow.qml` (кроме нового раздела — Task 5)
- Test: `tests/shell/strings.test.cjs`

**Interfaces:**
- Consumes: `Lang.s`, `Lang.f`, `Lang.time`, `Lang.longDate` (Task 3); новые сигнатуры `Models.js` с `s`.
- Часы панели — `Lang.time(clock.date)`, их доступное имя — `Lang.longDate` + время; экран блокировки — `Lang.time` и `Lang.longDate`.

- [x] **Step 1: Написать падающий тест** `test_qml_and_models_have_no_cyrillic_string_literals` — во всех `shell/quietline/**/*.qml` и в `Models.js` нет строкового литерала (`"…"` или `'…'`) с кириллицей вне комментариев `//`; кириллица разрешена только в `Strings.js`.
- [x] **Step 2: Убедиться, что тест падает.** `node --test 'tests/shell/*.test.cjs'` → FAIL со списком файлов.
- [x] **Step 3: Перевести** все тексты на ключи `Lang.s.*`, добавляя ключи в обе таблицы `Strings.js`; вызовы `Models.js` передают `Lang.s`. Английские формулировки — коротко, в тоне русских; названия режимов — «Windows / Tiles».
- [x] **Step 4: Убедиться, что тесты проходят.** `node --test 'tests/shell/*.test.cjs'` → PASS.
- [x] **Step 5: Коммит** `feat(shell): оболочка на русском и английском`.

### Task 5: Раздел «Язык и регион» и раскладки Hyprland

**Files:**
- Modify: `shell/quietline/settings/SettingsWindow.qml`, `shell/quietline/logic/Models.js` (`SETTINGS_SECTIONS`), `shell/quietline/logic/Strings.js`, `config/hyprland/quietline.lua`
- Create: `config/fish/quietline-locale.fish`
- Test: `tests/helper/test_region.py`, `tests/shell/models.test.cjs`

**Interfaces:**
- Consumes: `Lang.update`, `Lang.layouts`, `Lang.toggle`, `Lang.clock`, `Lang.date`, `Lang.error` (Task 3); `TOGGLES` (Task 1).
- Раздел `region` заменяет `keyboard`; `open("keyboard")` открывает `region`. Блоки:
  - язык: «Русский» / «English» (выбранный — `emphasized`), под ними — «Программы переключатся после повторного входа»;
  - время: 24 / 12 часов; дата: три варианта, подписью — сегодняшняя дата в этом формате;
  - раскладки: текущая раскладка, порядок с кнопкой «Поменять местами», выбор сочетания из `TOGGLES` (подписи — Global Constraints), «Следующая раскладка» как сейчас;
  - ошибка `Lang.error` — строкой цвета `Theme.danger`.
- `quietline.lua`: читает `$XDG_CONFIG_HOME/quietline/keyboard.lua` (без переменной — `~/.config/quietline/keyboard.lua`) через `pcall(dofile, …)`; нет файла или ошибка — `kb_layout = "us,ru"`, `kb_options = "grp:lalt_lshift_toggle"`; результат — в `hl.config({ input = … })`.
- `quietline-locale.fish`: `set -e LANGUAGE`, `set -gx LC_MESSAGES en_US.UTF-8`.

- [x] **Step 1: Написать падающие тесты:**
  - `test_lua_config_reads_keyboard_file_with_defaults` (`test_region.py`) — текст `quietline.lua` содержит путь `quietline/keyboard.lua`, `pcall(dofile`, `"us,ru"` и `"grp:lalt_lshift_toggle"`; вывод `keyboard_lua()` — одна строка `return { kb_layout = …, kb_options = … }`;
  - `test_fish_locale_keeps_terminal_messages_english` — файл содержит `set -gx LC_MESSAGES en_US.UTF-8` и `set -e LANGUAGE` и не задаёт `LANG`;
  - в `models.test.cjs`: `searchResults("раскладка", …, table("ru"))` и `searchResults("keyboard", …, table("en"))` находят раздел `region`; раздела `keyboard` больше нет.
- [x] **Step 2: Убедиться, что тесты падают.** `uv run --python 3.14 pytest tests/helper/test_region.py -v`, `node --test 'tests/shell/*.test.cjs'` → FAIL.
- [x] **Step 3: Реализовать** раздел, `SETTINGS_SECTIONS`, Lua и fish.
- [x] **Step 4: Убедиться, что тесты проходят.** `uv run --python 3.14 pytest -q`, `node --test 'tests/shell/*.test.cjs'` → PASS.
- [x] **Step 5: Коммит** `feat(shell): раздел «Язык и регион» и раскладки us,ru`.

### Task 6: Док и памятка без неустановленных программ

**Files:**
- Modify: `shell/quietline/logic/Models.js` (`groupApps`, `describeBinds`), `shell/quietline/dock/Dock.qml`, `shell/quietline/settings/SettingsWindow.qml` (передача `entries` в `describeBinds`)
- Test: `tests/shell/models.test.cjs`

**Interfaces:**
- `groupApps`: закреплённое приложение без desktop-записи и без окон в результат не попадает; с окнами — показывается как сейчас. Поле `available` и бледная иконка в `Dock.qml` удаляются вместе с подсказкой «не установлено».
- `BIND_APPS = {dolphin: "org.kde.dolphin", ghostty: "com.mitchellh.ghostty"}`; `describeBinds(binds, s, entries)` пропускает привязку, команда которой есть в `BIND_APPS`, а `desktopFor(id, entries)` пуст.

- [x] **Step 1: Написать падающие тесты:** `test_missing_pinned_app_is_hidden_but_running_one_stays` — закреплён `org.kde.dolphin` без записи и без окон → нет в результате; тот же ID с окном → есть; `test_binds_to_missing_apps_are_not_listed` — `SUPER+E dolphin` без записи Dolphin отсутствует в памятке, с записью — «Open Dolphin» для `table("en")`. Существующий тест с `available: false` переписать под новое поведение.
- [x] **Step 2: Убедиться, что тесты падают.** `node --test 'tests/shell/*.test.cjs'` → FAIL.
- [x] **Step 3: Реализовать.**
- [x] **Step 4: Убедиться, что тесты проходят.** `node --test 'tests/shell/*.test.cjs'` → PASS.
- [x] **Step 5: Коммит** `feat(shell): док и памятка скрывают неустановленные программы`.

### Task 7: Документация, сценарий проверки, ревью

**Files:**
- Create: `scripts/smoke-language.md`
- Modify: `docs/superpowers/specs/2026-10-19-quietline-desktop-design.md`, `AGENTS.md`, `README.md`, `CHANGELOG.md`, `docs/backlog.md`, этот план (статус)

- [x] **Step 1: Основная спека** — в «Оболочке и внешнем виде»: оболочка на русском или английском, раздел «Язык и регион» вместо «Клавиатуры» в списке разделов, док скрывает отсутствующие закреплённые приложения; в «Ежедневных действиях» — раскладки `us,ru` всегда; в критериях готовности (п. 4) — оба языка, раскладки, английские сообщения терминала.
- [x] **Step 2: `AGENTS.md`** — Layout: `config/fish/`, `Lang.qml` и `logic/Strings.js`; конвенция: видимые тексты оболочки и уведомлений — через таблицы строк на двух языках, кириллица в QML и `Models.js` запрещена тестом; команда `quietline-shell region`. **`README.md`** — статус этапа 5. **`CHANGELOG.md`** (`Unreleased`): Added — выбор языка, раздел «Язык и регион», формат даты и времени, раскладки `us,ru`; Changed — док скрывает неустановленные программы, раздел «Клавиатура» стал «Языком и регионом».
- [x] **Step 3: `scripts/smoke-language.md`** — смена языка в настройках перерисовывает панель, открытые всплывающие окна и экран блокировки; после повторного входа Dolphin на новом языке; `locale` в Ghostty показывает `LC_MESSAGES=en_US.UTF-8`, `git --help` по-английски; раскладки `us,ru` и левые `Alt+Shift` при первом входе; смена порядка и сочетания действует сразу и после `hyprctl reload`; формат часов меняется сразу; Dolphin удалён — его нет в доке и памятке. Те же пункты — в `docs/backlog.md`.
- [x] **Step 4: Полная проверка** `uv run --python 3.14 pytest -q`, `node --test 'tests/shell/*.test.cjs'` → PASS. Независимое ревью ветки по Review Focus; существенные замечания — с воспроизводящими тестами.
- [x] **Step 5: Коммит** `docs(shell): описаны языки и регион и их живая проверка`.
