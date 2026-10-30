# Простой и сон, индикатор, заряд, центр уведомлений

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Статус:** выполняется (ветка `feature/idle-osd-notifications`): задачи 1–6 написаны; живые проверки не проведены — `scripts/smoke-idle-notifications.md`, `docs/backlog.md`.
**Цель:** ноутбук сам блокируется и засыпает, клавиши громкости и яркости работают с индикатором, о низком заряде приходит предупреждение, уведомления остаются в истории с режимом «Не беспокоить».
**Архитектура:** простоем управляет hypridle — отдельный процесс с конфигурацией из пакета; клавиши меняют громкость и яркость утилитами напрямую, оболочка только показывает индикатор; заряд и история уведомлений — сервисы оболочки, чистая логика — в `Models.js`.
**Стек:** Hyprland 0.55 (Lua), hypridle, Quickshell 0.3.2 (QML), Python ≥ 3.14 (`quietline-shell`), Node ≥ 22 для тестов моделей.
**Спецификация:** `docs/superpowers/specs/2026-10-30-idle-osd-notifications-design.md` — источник всех значений ниже; исполнитель читает её целиком. Внешний вид — `DESIGN.md`.

## Global Constraints

- Минимальные версии не меняются: Hyprland 0.55, Quickshell 0.3.2; новый пакет — только `hypridle` из `extra`.
- Проверено по исходникам до плана: `hypridle -c|--config <path>`; `hl.dsp.dpms({ action = "enable"|"disable" })`; флаги `hl.bind` `locked` и `repeating`; `hl.dsp.exec_cmd` выполняет строку через `/bin/sh -c` (`&&` работает).
- Комментарии — по-русски и только о текущем поведении; ответы CLI и ошибки — по-английски, одна строка JSON, ошибка — `{"error": …}` и код 1.
- Каждый видимый текст — в обеих таблицах `shell/quietline/logic/Strings.js` с одинаковыми ключами; кириллица в QML и `Models.js` запрещена (`tests/shell/strings.test.cjs`).
- Папка — не больше восьми записей: `src/quietline_shell/` уже полна (8), новая подкоманда живёт в `session.py`.
- Тесты: `uv run --python 3.14 pytest`, `node --test 'tests/shell/*.test.cjs'`; QML, hypridle и клавиши проверяются только вживую — пункты в `docs/backlog.md` и `scripts/smoke-idle-notifications.md`.
- Сроки hypridle: 300 с — `loginctl lock-session`; 330 с — экраны выключить/включить; 900 с — `quietline-shell idle suspend`. Пороги заряда 20, 10, 5 (5 — критическое). История — не больше 100. Индикатор скрывается через 1500 мс, собственные изменения громкости оболочки пропускаются 600 мс, шаг клавиш — 5 %, предел громкости 150 %.

## Review Focus

1. **Зарядка через USB-C и батареи периферии:** зарядное устройство USB-C видно в `/sys/class/power_supply` как `type = USB`, а батарея мыши — как `Battery` со `scope = Device`. Ноутбук от USB-C зарядки не должен засыпать, а компьютер без своей батареи — засыпать из-за мыши. Тесты — Task 1.
2. **Заряд прыгает около порога:** 20 → 21 → 20 % без зарядки не даёт второго предупреждения; после подключения и отключения зарядки предупреждения начинаются заново. Тесты — Task 4.
3. **Критическое уведомление при «Не беспокоить»:** всплывает; при открытом центре уведомлений не всплывает ничего. Тесты — Task 5.
4. **Индикатор и собственные ползунки:** перетаскивание громкости в быстрых настройках не вызывает индикатор, клавиша сразу после — вызывает. Тест — Task 3.
5. **Переполнение и закрытие приложением:** 101-е уведомление закрывает самое старое; уведомление, закрытое приложением, исчезает из истории; `transient` в историю не попадает. Тест модели — Task 5, остальное — сценарий проверки.

## Файлы

- `config/hypridle/hypridle.conf` (новый) — `general` и три слушателя из спеки.
- `config/hyprland/quietline.lua` — запуск hypridle, `misc.key_press_enables_dpms`, `misc.mouse_move_enables_dpms`, клавиши `XF86…`, `Super+N`.
- `src/quietline_shell/session.py`, `__main__.py` — `idle suspend`.
- `packaging/arch/PKGBUILD` — `hypridle` в `depends`, установка `hypridle.conf`; `installer/catalog.toml` — `hypridle` в `[core]`.
- `shell/quietline/logic/Models.js`, `Strings.js` — чистые функции и строки.
- `shell/quietline/system/KeepAwake.qml` (новый), `PowerService.qml`, `AudioService.qml`, `BrightnessService.qml`.
- `shell/quietline/osd/Osd.qml`, `osd/qmldir` (новые).
- `shell/quietline/notifications/NotificationService.qml`, `NotificationPopups.qml`, `NotificationCenter.qml` (новый).
- `shell/quietline/bar/TopBar.qml`, `panels/QuickSettings.qml`, `shell.qml`.
- Тесты: `tests/helper/test_session.py`, `tests/engine/test_server.py`, `tests/shell/models.test.cjs`, `tests/install/test_install_catalog.py` при необходимости.
- Документы: `THIRD_PARTY.md` (новый), `scripts/smoke-idle-notifications.md` (новый), `docs/backlog.md`, основная спека, `DESIGN.md`, `AGENTS.md`, `README.md`, `CHANGELOG.md`.

## Task 1: Простой и сон

**Interfaces:**
- Produces: `session.idle_suspend(supplies: Path = Path("/sys/class/power_supply")) -> dict` — `{"suspended": True}`, `{"suspended": False, "reason": "ac"}` или `{"suspended": False, "reason": "no-battery"}`; ошибка `systemctl suspend` — `RuntimeError("systemctl suspend failed: …")`. CLI: `quietline-shell idle suspend`.
- Правило: сеть есть, если у любого источника `type` равен `Mains` или `USB` и `online` равен `1`; своя батарея есть, если у источника `type = Battery` и `scope` отсутствует или не равен `Device`.

- [x] Тесты в `tests/helper/test_session.py` на поддельном каталоге `tmp_path` и подменённом `subprocess.run`:
  - `test_idle_suspend_on_battery_suspends`: `BAT0` (Battery), `AC` (Mains, online 0) → `{"suspended": True}`, вызвана `["systemctl", "suspend"]`;
  - `test_idle_suspend_on_mains_stays_awake`: `AC` online 1 → `{"suspended": False, "reason": "ac"}`, `systemctl` не вызван;
  - `test_idle_suspend_on_usb_charger_stays_awake`: `ucsi-source-psy-USBC000:001` (USB, online 1) и `BAT0` → `reason` `"ac"`;
  - `test_idle_suspend_ignores_peripheral_batteries`: только `hidpp_battery_0` (Battery, scope Device) → `reason` `"no-battery"`;
  - `test_cli_idle_suspend_reports_systemctl_failure`: код возврата 1 → stdout `{"error": …}`, код 1.
- [x] Запустить `uv run --python 3.14 pytest tests/helper/test_session.py -k idle -v` → FAIL.
- [x] Реализовать `idle_suspend` в `session.py` и подкоманду `idle` с действием `suspend` в `__main__.py` (docstring модуля — в список подкоманд).
- [x] Тесты → PASS.
- [x] `config/hypridle/hypridle.conf`: `general` — `lock_cmd = quietline-shell lock`, `before_sleep_cmd = loginctl lock-session`, `after_sleep_cmd = hyprctl dispatch 'hl.dsp.dpms({ action = "enable" })'`, `inhibit_sleep = 3`, три `ignore_*_inhibit = false`; слушатели 300/330/900 с, у 330 — `on-resume` с `"enable"`. Комментарии по-русски.
- [x] `quietline.lua`: в `hl.on("hyprland.start")` — `hl.exec_cmd("hypridle -c /usr/share/quietline/hypridle/hypridle.conf")`; в `hl.config` `misc` — `key_press_enables_dpms = true`, `mouse_move_enables_dpms = true`.
- [x] `PKGBUILD`: `hypridle` в `depends`, `install -Dm644 config/hypridle/hypridle.conf "$pkgdir/usr/share/quietline/hypridle/hypridle.conf"`; `catalog.toml` `[core]` — `hypridle` рядом с `hyprpolkitagent`.
- [x] Полный `uv run --python 3.14 pytest` → PASS (тесты PKGBUILD и каталога установщика).
- [x] Коммит `feat(installer): автоблокировка и сон по простою через hypridle`.

## Task 2: «Не засыпать»

**Interfaces:**
- Produces: `system/KeepAwake.qml` (`Scope`): `property bool active`, `function toggle()`; держит `IdleInhibitor { enabled: root.active; window: <окно> }` на собственном `PanelWindow` 0×0 с пустой маской (`mask: Region {}`), `WlrLayershell.layer: WlrLayer.Background`, `exclusionMode: ExclusionMode.Ignore`. `shell.qml` создаёт один экземпляр и добавляет его в `services` как `keepAwake`.

- [x] `KeepAwake.qml` по интерфейсу; `qmldir` папки `system/`.
- [x] `QuickSettings.qml`: `ShellSwitch` «Не засыпать» под Bluetooth.
- [x] `TopBar.qml`: при `services.keepAwake.active` — значок чашки цветом `Theme.muted` слева от часов, подсказка и доступное имя «Не засыпать включено».
- [x] `shell.qml` `status()`: поле `keepAwake`.
- [x] Строки обоих языков; `node --test 'tests/shell/*.test.cjs'` → PASS.
- [x] Коммит `feat(shell): переключатель «Не засыпать»`.

## Task 3: Клавиши и индикатор

**Interfaces:**
- Produces в `Models.js`:
  - `osdView(kind: "volume"|"mic"|"brightness"|"layout", value: number|string, muted: bool) -> {icon: string, fill: number, text: string}`: `fill` — доля 0…1 (громкость выше 1 даёт 1), для `layout` — `-1` (полосы нет), `text` — `"120%"` или код раскладки; `icon` — глиф Nerd Font, у `muted` — перечёркнутый.
  - `OSD_HIDE_MS = 1500`, `OSD_LOCAL_MS = 600`, `osdSuppressed(localUntil: number, now: number) -> bool` (`now < localUntil`).
- Produces: `AudioService.localUntil` (мс; `setVolume`, `toggleMute`, `setMicVolume`, `toggleMicMute` ставят `Date.now() + Models.OSD_LOCAL_MS`); `BrightnessService.refresh()` — перечитать и после чтения испустить `signal refreshed()`; `osd/Osd.qml` (`PanelWindow`): `required property var services; required property var desktop; function show(kind)`.
- IPC в `shell.qml`: `osd(kind: string)` — для `brightness` вызывает `brightness.refresh()`, индикатор показывается по `refreshed`.

- [x] Тесты в `models.test.cjs`:
  - `osdView("volume", 1.2, false)` → `fill` 1, `text` `"120%"`; `osdView("volume", 0.35, true)` → `fill` 0.35 и иконка выключенного звука, отличная от `osdView("volume", 0.35, false).icon`;
  - `osdView("brightness", 0.05, false).text === "5%"`; `osdView("layout", "RU", false)` → `fill` −1, `text` `"RU"`;
  - `osdSuppressed(1600, 1000) === true`, `osdSuppressed(1600, 1600) === false` (Review Focus 4).
- [x] Запустить `node --test 'tests/shell/*.test.cjs'` → FAIL; реализовать; → PASS.
- [x] `quietline.lua`: шесть привязок из таблицы спеки, команды дословно; яркость — `brightnessctl -c backlight --min-value=1 set 5%+ && qs -c quietline ipc call quietline osd brightness` (и `5%-`). Громкость и яркость вверх/вниз — `{ locked = true, repeating = true }`, выключение звука и микрофона — `{ locked = true }`.
- [x] `tests/engine/test_server.py::test_shortcuts_target_expected_cli_calls`: список `locked` — `SUPER + L` и шесть клавиш `XF86…`; проверка команд новых привязок; разбор флагов принимает `{ locked = true, repeating = true }`. Запуск → PASS.
- [x] `Models.bindAction` и строки памятки: описания шести клавиш (команда `wpctl …` и `brightnessctl …` → подпись); тест в `models.test.cjs`.
- [x] `osd/Osd.qml`: монитор с фокусом, низ по центру, нижний край на 16 px выше верхнего края дока (высота дока — по `Dock.qml` и токенам `Theme.dock*`) в любом режиме, около 240×44, вид из `Models.osdView`, появление/исчезновение `Theme.motionDuration` со сдвигом 8 px, мгновенно при `reducedMotion`, скрытие через `OSD_HIDE_MS` после последнего `show`, пустая маска, `WlrKeyboardFocus.None`, `ExclusionMode.Ignore`, слой `Overlay`. Источники: `Connections` на `audio.sink.audio` (`volume`, `muted`) и `audio.source.audio` (`muted`, `volume`) с пропуском по `osdSuppressed` и при смене узла (запомнить `id` узла: другой узел — не показывать, только запомнить); `desktop.keyboardLayout` (первое значение после запуска не показывать); `brightness.refreshed`.
- [x] `shell.qml`: экземпляр `Osd`, IPC `osd`.
- [x] Коммит `feat(shell): клавиши громкости и яркости с индикатором`.

## Task 4: Низкий заряд

**Interfaces:**
- Produces в `Models.js`: `BATTERY_LEVELS = [20, 10, 5]`, `BATTERY_CRITICAL = 5`, `batteryWarning(warned: number|null, percent: number, charging: bool) -> number|null` — наименьший порог `L`, для которого `percent <= L` и (`warned === null` или `L < warned`); при зарядке — `null`.
- `PowerService`: `property var warned: null`; при `charging` → `warned = null`; при изменении `percent`/`charging`/готовности: `L = batteryWarning(warned, percent, charging)`; `L !== null` → `warned = L` и `notify-send --app-name=Quietline --urgency=<critical при L === BATTERY_CRITICAL, иначе normal> <заголовок> <текст>` через `Quickshell.execDetached`, тексты — `Lang.f(Lang.s.batteryLowTitle, L)` и `Lang.s.batteryLowBody` / `batteryCriticalBody`.

- [x] Тесты в `models.test.cjs`:
  - `batteryWarning(null, 20, false) === 20`; `batteryWarning(20, 19, false) === null`; `batteryWarning(20, 9, false) === 10`; `batteryWarning(null, 8, false) === 10`; `batteryWarning(10, 4, false) === 5`; `batteryWarning(null, 15, true) === null`; `batteryWarning(null, 50, false) === null`;
  - Review Focus 2: последовательность 21 → 20 → 21 → 20 без зарядки через `warned` даёт одно предупреждение (20); после зарядки (`warned = null`) 20 снова даёт 20.
- [x] → FAIL; реализовать; → PASS.
- [x] `PowerService.qml` по интерфейсу; строки обоих языков.
- [x] Коммит `feat(shell): предупреждения о низком заряде`.

## Task 5: Центр уведомлений и «Не беспокоить»

**Interfaces:**
- Produces в `Models.js`:
  - `NOTIFICATION_HISTORY_LIMIT = 100`;
  - `popupAllowed(urgency: number, dnd: bool, centerOpen: bool) -> bool`: `centerOpen` → `false`; `urgency === 2` → `true`; иначе `!dnd`;
  - `notificationAge(received: number, now: number) -> {kind: "now"|"minutes"|"today"|"earlier", minutes: number}` — меньше 60 с, меньше часа, тот же календарный день (местное время), раньше.
- Produces `NotificationService.qml`:
  - `property bool dnd`, `property bool centerOpen`, `readonly property int unread`, `property int revision` (растёт при любой смене сведений);
  - `readonly property var history` — `[{notification, received, read}]`, новые первыми, без `transient`;
  - `readonly property var popups` — уведомления с видимой карточкой, новые первыми, не больше `NOTIFICATION_LIMIT`;
  - `function popupTimedOut(n)` (у `transient` — `expire()`, иначе скрыть карточку), `function setDnd(on)` (включение скрывает некритические карточки), `function setCenterOpen(open)` (открытие отмечает все прочитанными и скрывает карточки), `function clearAll()` (`dismiss()` всем);
  - сведения — объект по `notification.id` (время прихода, прочитано, карточка видна), заполняется в `onNotification`, лишние ключи удаляются при пересчёте; при `trackedNotifications.values.length > NOTIFICATION_HISTORY_LIMIT` самое старое — `dismiss()`.
- `NotificationPopups.qml`: таймеры по `Models.notificationTimeout` вызывают `service.popupTimedOut`, работают только у видимых карточек; показывает `service.popups`.
- `NotificationCenter.qml`: `required property var service; signal done()`; заголовок «Уведомления», `ShellSwitch` «Не беспокоить», список по `service.history` (приложение · время по `notificationAge` и `Lang.time`/`Lang.longDate`, заголовок, текст до 4 строк, действия, «×»; нажатие на строку — действие `default`; критическое — рамка `Theme.danger`), «Очистить всё», пустое состояние. Прокрутка — общий `ShellScrollBar`.
- `TopBar.qml`: часы — `ShellButton` (`popout.toggle("notifications")`), точка 6 px `Theme.accent` при `unread > 0`, значок луны `Theme.muted` при `dnd`, подсказка с числом непрочитанных; `function toggleNotifications()`; содержимое `notifications` в `ShellPopup`, ширина 400; при смене `popout.opened`/`currentName` — `service.setCenterOpen(...)`. Сервис уведомлений передаётся в `services` как `notifications`.
- `QuickSettings.qml`: `ShellSwitch` «Не беспокоить». `shell.qml`: IPC `notifications()` (монитор с фокусом), `dnd(action: string)` (`on`, `off`, `toggle`), `status()` — `notifications: {count, unread, dnd}`. `quietline.lua`: `SUPER + N` → `qs -c quietline ipc call quietline notifications`; `bindAction` и строка памятки; `test_server.py` — новая привязка.

- [x] Тесты в `models.test.cjs`:
  - Review Focus 3: `popupAllowed(2, true, false) === true`; `popupAllowed(1, true, false) === false`; `popupAllowed(2, false, true) === false`; `popupAllowed(1, false, false) === true`;
  - `notificationAge` (правила по порядку: секунды, минуты, календарный день): 30 с → `now`; 5 мин → `minutes`, 5; 23:50 при «сейчас» 00:20 следующего дня → `minutes`, 30; 3 ч назад в тот же день → `today`; 22:00 при «сейчас» 01:00 следующего дня → `earlier`;
  - Review Focus 5: функция отбора `notificationsToDrop(count: number) -> number` (`max(0, count − NOTIFICATION_HISTORY_LIMIT)`): 100 → 0, 101 → 1.
- [x] → FAIL; реализовать; → PASS.
- [x] Сервис, всплывающие карточки, центр, панель, быстрые настройки, IPC, клавиша по интерфейсам; строки обоих языков.
- [x] `uv run --python 3.14 pytest tests/engine/test_server.py` и `node --test 'tests/shell/*.test.cjs'` → PASS.
- [x] Коммит `feat(shell): центр уведомлений и режим «Не беспокоить»`.

## Task 6: Документация, учёт заимствований, проверка

- [x] `THIRD_PARTY.md` в корне: Hyprstack shell 1.2.2, коммит `bef9187b14213532e801e51304d90a73eb20bae5`, GPL-3.0 (на основе Caelestia shell 2.5.0, GPL-3.0); что взято и изменено — таблица «Hyprstack: что берём» спеки; дата 2026-10-30. Лицензия совпадает с лицензией Quietline, отдельный файл лицензии не нужен.
- [x] `scripts/smoke-idle-notifications.md`: блокировка через 5 мин и экран через 5,5 мин; видео в браузере откладывает их; «Не засыпать»; крышка → блокировка до сна, после пробуждения экран горит; сон на батарее через 15 мин и его отсутствие от сети и от USB-C; клавиши с панелью и без неё; индикатор на мониторе с фокусом, над доком, без мигания при перетаскивании ползунка; раскладка; предупреждение 20/10/5 (через `upower` или разрядку); история, действия из истории, закрытие приложением, «Очистить всё», «Не беспокоить» и критическое, `Super+N`, два монитора.
- [x] `docs/backlog.md` — пункты живой проверки; основная спека — изменения из конца спеки этапа; `DESIGN.md` — строки «Индикатор», «Центр уведомлений», «Не засыпать», часы-кнопка, строка «Уведомления» обновлена; `AGENTS.md` — `config/hypridle/` и `THIRD_PARTY.md` в Layout, строка этапа в «Куда смотреть», «Текущее состояние»; `README.md` — структура и этапы; `CHANGELOG.md` — `Added`/`Changed` из спеки.
- [x] Полные `uv run --python 3.14 pytest` и `node --test 'tests/shell/*.test.cjs'` → PASS.
- [ ] Независимое ревью ветки по Review Focus и анти-целям спеки; существенные замечания — исправить с воспроизводящими тестами.
- [x] Коммит `docs: этап 6 — сценарий проверки, учёт заимствований Hyprstack, документы`.
- [ ] Живая проверка `scripts/smoke-idle-notifications.md` на Arch — вместе с этапами 1–5.

## Решения при выполнении

1. **`idle_suspend(supplies=None)`** читает каталог из константы `session.POWER_SUPPLIES`; без своей батареи ответ `{"suspended": false, "reason": "no-battery"}`.
2. **Окно «Не засыпать»** — слой 1×1 с пустой маской (слой нулевого размера без растяжки недопустим); чашка и луна на панели — `ShellButton` с подсказкой, нажатие выключает режим.
3. **Памятка** называет мультимедийные клавиши подписями (`KEY_LABEL_KEYS`: «Громкость +», «Звук»…), а не именами XKB.
4. **Яркость с клавиш:** `BrightnessService.refresh()` при идущем чтении ставит повтор, сигнал `refreshed` — по свежему чтению. Индикатор — на 100 px от низа (окно дока 84 px + 16).
5. **«×» и нажатие на всплывающей карточке** скрывают её и отмечают уведомление прочитанным; оно остаётся в центре. Уведомления, пришедшие при открытом центре, сразу прочитаны.
