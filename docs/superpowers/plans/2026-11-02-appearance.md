# План: светлая тема и выбор указателя

**Статус:** выполняется (ветка `feature/appearance`).

**Спека:** `docs/superpowers/specs/2026-11-02-appearance-design.md`; макет — `docs/design/quiet-line-b-light.html`.

## Цель

Переключатель «Светлая / Тёмная» для всего окружения и выбор цвета и размера указателя Capitaine в «Настройках» → «Оформление», быстрая кнопка темы в модуле «Экран» пункта управления. По умолчанию — тёмная тема, тёмный указатель 24 px.

## Границы

- Входит: `quietline-shell appearance`, `appearance.json` / `appearance.lua`, цвета Hyprland (рамки, тени, hyprbars) и `XCURSOR_*` из `appearance.lua`, `color-scheme` и `gtk-theme` в gsettings, токены `Theme.qml` для двух тем, перевод вписанных в QML цветов на токены, страница «Оформление», кнопка в пункте управления, строки на двух языках.
- Не входит: экран блокировки (общий для тем), схемы KDE, конфигурации Ghostty и других программ, расписание.

## Карта файлов

- `src/quietline_shell/config.py` — `default_appearance_path`, `load_appearance`, `updated_appearance`, `appearance_lua`, `save_appearance`, `apply_appearance` (папка `quietline_shell` уже держит восемь модулей — отдельного файла нет).
- `src/quietline_shell/__main__.py` — подкоманда `appearance [--set JSON] [--path PATH]`, docstring.
- `tests/helper/test_shell_config.py` — тесты чтения, частичной записи, отказов, `appearance.lua`, шагов применения.
- `config/hyprland/quietline.lua` — чтение `appearance.lua`, таблицы цветов двух тем, указатель.
- `shell/quietline/Appearance.qml`, `qmldir` — синглтон настроек оформления.
- `shell/quietline/Theme.qml` — токены по `Appearance.light`, новые токены вместо вписанных цветов.
- QML с вписанными цветами: `controls/SettingsGroup.qml`, `ShellScrollBar.qml`, `inputs/ShellSlider.qml`, `ShellSwitch.qml`, `ShellTextField.qml`, `notifications/NotificationCard.qml`, `NotificationCenter.qml`, `MonthCalendar.qml`, `search/SearchPanel.qml`, `clipboard/ClipboardPanel.qml`, `bar/TopBar.qml`, `osd/Osd.qml`, `dock/Dock.qml`, `panels/QuickSettings.qml`, `surfaces/HintPopup.qml`, `CenterDialog.qml`, `settings/SettingsWindow.qml`, `controls/SegmentedControl.qml`.
- `settings/SettingsWindow.qml` — раздел и страница «Оформление»; `panels/QuickSettings.qml` — кнопка «Тёмная тема».
- `logic/Strings.js` — строки `settingsAppearance*`, `appearance*` на двух языках.
- Документы: `DESIGN.md`, `CHANGELOG.md`, `AGENTS.md` (CLI и файлы настроек), `scripts/smoke-shell-redesign.md`, `docs/backlog.md`, шапка спеки.

## Шаги

- [ ] 1. CLI `appearance` и тесты: чтение без файла — `{"theme": "dark", "cursor": "dark", "cursorSize": 24}`; `--set` частично, проверка значений (тема и цвет — `dark | light`, размер — 24, 36, 48), неверное — `{"error"}` без записи, повреждённый файл не перезаписывается; `appearance.lua`; применение: `gsettings set … color-scheme`, `gtk-theme`, `hyprctl reload`, `hyprctl setcursor` с таймаутом; вне Hyprland — только gsettings, `applied: false`.
- [ ] 2. `quietline.lua`: `pcall(dofile, …/quietline/appearance.lua)` с проверкой полей, цвета двух тем для рамок, теней, hyprbars и кнопок, `XCURSOR_THEME` / `XCURSOR_SIZE` из выбора. Проверка — `hyprctl reload` в живом сеансе с обеими темами, `hyprctl configerrors` пуст, кнопки не удваиваются.
- [ ] 3. `Appearance.qml` и `Theme.qml`: токены двух тем; перевод вписанных цветов на токены; `tests/shell` зелёные.
- [ ] 4. Страница «Оформление» и кнопка в пункте управления, строки в `Strings.js`.
- [ ] 5. Живая проверка: оболочка из репозитория (`scripts/run-shell`) в обеих темах снимками, переключение из «Настроек» и пункта управления, Chrome/GTK меняют схему; непроверенное — в `docs/backlog.md` и сценарий.
- [ ] 6. Документы: `DESIGN.md` (светлая палитра), `CHANGELOG.md`, `AGENTS.md`, шапка спеки.

## Review Focus

- Применение при `--set` не ломает сохранение: ошибка `hyprctl` или `gsettings` даёт `applied: false`, файлы уже записаны.
- В Lua-литерал `appearance.lua` попадают только проверенные значения.
- Все цвета QML вне экрана блокировки берутся из `Theme`; в тёмной теме значения прежние.
