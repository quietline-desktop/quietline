# Системные панели и окно «Настройки»

**Статус:** перенос на новую оболочку (ветка `feature/system-panels`): план записан, реализация не начата.
**Цель:** сетевая панель с Ethernet-профилями объекта и откатом через контрольную точку NetworkManager, быстрые настройки звука, яркости, Wi-Fi и Bluetooth и окно «Настройки» с боковой навигацией поверх того же состояния.
**Спецификация:** `docs/superpowers/specs/2026-10-19-quietline-desktop-design.md` — разделы «Оболочка и внешний вид» (сетевая панель, быстрые настройки, окно «Настройки»), «Сочетания клавиш» (`Super+I`) и «Ошибки, проверка и готовность», пункт 4. Внешний вид — `DESIGN.md`, сетевая панель — `docs/design/quiet-line-a.html`.
**Основа:** этап 2 в `main` (`docs/superpowers/plans/2026-10-19-quickshell.md`). Источник переноса — коммиты `adabf49`…`a2e8aa5` ветки `origin/feature/installer`, написанные под прежнюю оболочку и уже прошедшие ревью.

## Границы и решения

Python-помощник `quietline-shell network …` обслуживает NetworkManager: передаёт `nmcli` только списки аргументов, контрольные точки создаёт через `gdbus` к D-Bus NetworkManager, отвечает одной строкой JSON. Звук, Bluetooth, батарею и профили питания QML берёт из сервисов Quickshell (`Quickshell.Services.Pipewire`, `Quickshell.Bluetooth`, `Quickshell.Services.UPower`), яркость — через `brightnessctl`. Каждая область — один QML-сервис и один компонент управления; компонент вставляется и во всплывающую панель, и в страницу окна «Настройки», второй копии состояния нет.

- Профиль объекта по умолчанию — статический IPv4 без маршрута по умолчанию (`ipv4.never-default yes`), `connection.autoconnect no`, применяется к выбранному Ethernet-адаптеру, включая USB.
- Перед сменой активной конфигурации создаётся контрольная точка NetworkManager; без подтверждения через 30 секунд NetworkManager возвращает прежнюю конфигурацию.
- Ошибка адреса или недоступный адаптер показываются в той же панели без ложного «Подключено».
- Пароль Wi-Fi передаётся только через stdin (`passwd-file /dev/stdin`), не в аргументах и не в файлах.
- Ползунок яркости — только для экрана с подсветкой; блоки Bluetooth и батареи — только при наличии оборудования.
- Сетевая панель не закрывается от щелчка в другом окне, закрывается по `Esc` или своей кнопкой.
- Окно «Настройки»: разделы «Сеть», «Звук», «Экран и яркость», «Bluetooth», «Питание», «Клавиатура», «Сочетания клавиш», «О системе»; открывается из быстрых настроек, по `Super+I` и через IPC `settings SECTION` (поиск — этап 4). Тем, обоев и дашборда нет.
- Кнопка быстрых настроек открывает звук, яркость, Wi-Fi, Bluetooth и «Все настройки»; блокировка и выключение — кнопка питания этапа 4.

## Перенос на новую оболочку

Поведение и внешний вид — как на ветке-источнике. Что меняется при переносе:

1. **Пакет Python.** Сетевой помощник — `src/quietline_shell/network.py`, сводка «О системе» — `src/quietline_shell/system_info.py`, подкоманды подключаются в `src/quietline_shell/__main__.py`. Атомарная запись JSON выносится из `save_pins` в `config.atomic_write_json(path, value)` и используется для `pins.json` и `network.json`. Python ≥ 3.14, тесты — `uv run --python 3.14 pytest`.
2. **Язык сообщений.** Ошибки `quietline-shell` — по-английски, как у `pins` (`AGENTS.md`). Ошибка проверки формы профиля дополнительно несёт поле `field` (`name`, `method`, `address`, `prefix`, `gateway`, `dns`); панель показывает русский текст по `field` (`Models.profileErrorText`), остальные ошибки — русский префикс действия и подробность по-английски, как ошибки движка в панели (план этапа 2, «Решения при выполнении», п. 2).
3. **`network` без подкоманды убирается.** Прежняя сводка `quietline-shell network` заменяется `network status`; `Indicators.qml` больше не читает сеть и `Quickshell.Networking` — сеть, Bluetooth и батарею панель берёт из сервисов этого этапа.
4. **Раскладка папок QML** (правило папок `AGENTS.md`, не больше восьми записей):
   - `services/` — без изменений: `EngineClient`, `DesktopModel`, `Indicators`;
   - `system/` — сервисы оборудования: `NetworkService`, `AudioService`, `BrightnessService`, `BluetoothService`, `PowerService`;
   - `panels/` — компоненты управления и содержимое быстрых настроек: `NetworkControls`, `AudioControls`, `BrightnessControls`, `BluetoothControls`, `PowerControls`, `QuickSettings`;
   - `settings/` — окно `SettingsWindow`;
   - `inputs/` — поля форм: `ShellSlider`, `ShellSwitch`, `ShellTextField`; `controls/` остаётся с кнопками, пунктами меню, подсказками и всплывающими окнами.
5. **Всплывающее окно.** `controls/ShellPopup.qml` получает `persistent: bool`: при `true` захват фокуса Hyprland выключен, клавиатура — `OnDemand`, закрытие — `Esc` и `close()`. Содержимое «summary» панели становится быстрыми настройками (`quick`); IPC `showSummary` и поле `summaryOpen` в `status` сохраняют имена и относятся к быстрым настройкам.
6. **Комментарии** в перенесённом коде — по-русски, интерфейс — по-русски, вывод в консоль — по-английски.
7. **Hyprland 0.55.** `Super+I` добавляется в `config/hyprland/quietline.lua` тем же `hl.bind(…, hl.dsp.exec_cmd(…))`, что и остальные клавиши; памятка сочетаний читает `hyprctl binds -j`. Поля `modmask`, `key`, `arg` в 0.55 и разбор `nmcli --escape yes` подтверждаются только вживую — пункты в `docs/backlog.md`.
8. **Результаты живой проверки** записываются в «Результаты» `scripts/smoke-system-panels.md` и в `docs/backlog.md`, отдельной папки `docs/verification/` нет.

## Контракт `quietline-shell network`

Каждая подкоманда печатает одну строку JSON и завершается с кодом 0; ошибка — `{"error": "<text>"}` (у ошибки формы ещё `"field"`) и код 1. Секреты читаются только из stdin.

| Подкоманда | Вход | Результат |
| --- | --- | --- |
| `network status` | — | `{devices, wifi, profiles, pendingCheckpoints}` |
| `network wifi-scan` | — | `{networks: [{ssid, signal, security, active, known}]}` |
| `network wifi-radio --on\|--off` | — | `{wifi: {enabled}}` |
| `network wifi-connect --ssid S [--device D]` | stdin: пароль одной строкой или пусто | `{connected: true}` |
| `network profile-save` | stdin: JSON профиля | `{profile}` |
| `network profile-delete --uuid U` | — | `{deleted: U}` |
| `network apply --uuid U --device D` | — | `{checkpoint, timeout: 30}` |
| `network dhcp --device D` | — | `{checkpoint, timeout: 30}` |
| `network confirm --checkpoint P` / `network rollback --checkpoint P` | — | `{checkpoint: P, result: "kept"\|"reverted"}` |

Устройство: `{device, type: "ethernet"|"wifi", state: "connected"|"connecting"|"disconnected"|"unavailable", cable: bool|null, profile, uuid, addresses: [..], gateway}`.
Профиль: `{uuid, name, method: "manual"|"auto", address: "10.42.0.5/24"|null, gateway: str|null, dns: [..], neverDefault: bool, lastUsed: int|null}`.
`quietline-shell about` → `{os, kernel, hostname, cpu, memoryGb, hyprland, quickshell}`; недоступная версия — `null`.

## Файлы

- `src/quietline_shell/network.py`, `src/quietline_shell/system_info.py`, `src/quietline_shell/config.py` (`atomic_write_json`), `src/quietline_shell/__main__.py`.
- `config/polkit/50-quietline-network.rules` — права NetworkManager для активного локального пользователя из `wheel`.
- `shell/quietline/system/`, `panels/`, `settings/`, `inputs/` — см. «Перенос», п. 4; правки `controls/ShellPopup.qml`, `bar/TopBar.qml`, `services/Indicators.qml`, `shell.qml`, `logic/Models.js`.
- `config/hyprland/quietline.lua` — `Super+I`.
- Тесты: `tests/shell/test_network.py`, `tests/shell/test_system_info.py`, `tests/shell/test_shell_config.py`, `tests/shell/models.test.cjs`, `tests/shell/polkit.test.cjs`, `tests/engine/test_server.py` (Lua-привязка).
- `scripts/smoke-system-panels.md`, `docs/backlog.md`, `README.md`, `DESIGN.md`, `CHANGELOG.md`, `AGENTS.md` (раскладка папок).

## Review Focus

1. **Статический профиль без шлюза при подключённом Wi-Fi:** маршрут в интернет остаётся через Wi-Fi (`test_new_static_profile_never_takes_default_route`, smoke S3).
2. **USB-адаптер выдернут или кабель не вставлен во время применения и отсчёта:** ошибка или «Нет кабеля», не «Подключено»; откат проходит (`test_status_reports_cable_and_activation_state`, `test_apply_to_missing_device_fails_before_checkpoint`, smoke S5).
3. **Оболочка перезапущена посреди отсчёта:** NetworkManager откатывает сам, новая панель видит незавершённую точку и предлагает «Оставить / Вернуть» (`test_status_lists_pending_checkpoint`, `pendingCheckpoint survives shell restart`, smoke S6).
4. **Некорректный ввод формы** (`10.0.0.300/24`, адрес без префикса, мусор в DNS, пустое и слишком длинное имя) отвергается до вызова `nmcli` с полем `field`; имена с пробелами, `:` и кавычками проходят через разбор `nmcli -t` (`test_profile_validation_rejects_bad_input`, `test_profile_names_with_colons_roundtrip`).
5. **Оборудования нет** (подсветки, Bluetooth-адаптера, батареи; только внешний монитор): фиктивных ползунков и переключателей нет, страницы окна показывают понятное состояние (`brightness parse yields null without backlight`, smoke S9).

## Task 1: Сетевой помощник

- [ ] Перенести `network.py` в `src/quietline_shell/` с английскими ошибками и полем `field` у ошибок формы, `atomic_write_json` в `config.py`, подкоманды `network …` в `__main__.py`; убрать `network_devices()` и `network` без подкоманды.
- [ ] Перенести правило polkit и `tests/shell/polkit.test.cjs`.
- [ ] Перенести тесты в `tests/shell/test_network.py` (состояние, профили, Wi-Fi, контрольные точки, DHCP, недавние профили, CLI) с проверкой `field`; старые тесты `network` в `test_shell_config.py` удалить.
- [ ] `uv run --python 3.14 pytest`, `node --test 'tests/shell/*.test.cjs'` → PASS.

## Task 2: Сетевая панель

- [ ] `inputs/` (`ShellTextField`, `ShellSwitch`), `system/NetworkService.qml`, `panels/NetworkControls.qml`, `ShellPopup.persistent`, кнопка сети в `bar/TopBar.qml`, один `NetworkService` в `shell.qml`; `Indicators.qml` без сети.
- [ ] `Models.secondsLeft`, `Models.deviceLabel`, `Models.pendingFromStatus`, `Models.profileErrorText` с тестами в `models.test.cjs`.
- [ ] `node --test 'tests/shell/*.test.cjs'` → PASS; статическая проверка QML (парность скобок, импорты и `qmldir`, токены `Theme`).

## Task 3: Звук, яркость, Bluetooth, питание и быстрые настройки

- [ ] `system/AudioService`, `BrightnessService`, `BluetoothService`, `PowerService`; `panels/AudioControls`, `BrightnessControls`, `BluetoothControls`, `PowerControls`, `QuickSettings`; `inputs/ShellSlider`.
- [ ] Кнопка быстрых настроек панели открывает `quick`; Bluetooth и батарея панели берутся из сервисов, `Indicators.qml` без Bluetooth и UPower.
- [ ] `Models.parseBrightness`, `Models.clampVolume`, `Models.isBuiltinOutput` с тестами.
- [ ] Тесты → PASS, статическая проверка QML.

## Task 4: Окно «Настройки»

- [ ] `settings/SettingsWindow.qml`, IPC `settings(section)` в `shell.qml`, `Super+I` в Lua-конфиге с проверкой в `tests/engine/test_server.py`.
- [ ] `system_info.py` и подкоманда `about` с `tests/shell/test_system_info.py`; `Models.describeBinds` с тестами.
- [ ] Тесты → PASS, статическая проверка QML.

## Task 5: Документация и проверка

- [ ] `scripts/smoke-system-panels.md` (S1–S10 ветки-источника, пути и команды нового репозитория), пункты в `docs/backlog.md`, `README.md` (статус, этапы, зависимости `brightnessctl power-profiles-daemon bluez bluez-utils networkmanager`, установка правила polkit), `DESIGN.md` (владельцы), `CHANGELOG.md`, раскладка папок в `AGENTS.md`.
- [ ] Полные `pytest` и `node --test` → PASS; аудит: нет `shell=True`, пароль не в аргументах, токены только из `Theme`.
- [ ] Независимое ревью ветки по Review Focus; существенные замечания исправить с воспроизводящими тестами.
- [ ] Живая проверка `scripts/smoke-system-panels.md` на Arch с Hyprland 0.55 и Quickshell 0.3.2 — после слияния, вместе с этапами 1–2.
