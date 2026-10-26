# Quietline Window Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Рабочий сервис, который на каждом мониторе открывает локальные пространства `1`–`10` и независимо переключает их между обычными окнами и прокручиваемыми колонками.

**Architecture:** Python-сервис хранит состояние только в текущем сеансе и принимает команды через Unix-сокет. Адаптер Hyprland читает снимки композитора и применяет действия; контроллер рассчитывает переходы и публикует подтверждённое состояние. Quickshell в следующих планах станет клиентом этого API, а не вторым владельцем режима.

**Tech Stack:** Arch Linux, Hyprland ≥ 0.55 с Lua-конфигом и встроенным `scrolling`, Python ≥ 3.14 (стандартная библиотека), pytest для разработки, Unix domain sockets. Разработка на macOS идёт через `uv` (`uv run --python 3.14 pytest`), системный Python macOS не используется.

**Commit messages:** по правилу `AGENTS.md` — `<type>(engine): <описание по-русски>`; английские сообщения в задачах ниже — только смысл коммита.

**Spec:** `docs/superpowers/specs/2026-10-19-quietline-desktop-design.md`

## Global Constraints

- Сеанс устанавливается поверх Arch Linux после Archinstall Minimal; установщик и разметка диска в этот план не входят.
- Использовать встроенный `scrolling` Hyprland и поддерживаемые команды Lua; не копировать Hyprstack и не подключать нативный модуль.
- Режим нового пространства — `windows`; режимы и геометрия существуют только в текущем сеансе в `$XDG_RUNTIME_DIR`.
- У каждого монитора локальные пространства `1`–`10`; цифровые сочетания действуют только на монитор с фокусом.
- Отключённые пространства остаются доступными на оставшемся мониторе и возвращаются при повторном подключении своего монитора.
- Проект пока личный; добавить `LICENSE` с GPL-3.0 на будущее без отдельного лицензионного этапа. Секреты и личные файлы в репозиторий не добавлять.
- Ошибка перехода оставляет прежний режим и сообщает об ошибке; UI не получает неподтверждённое состояние.

## Review Focus

1. Два одинаковых монитора без серийного номера: локальные `1`–`10` не смешиваются; проверить в Task 2.
2. Активного окна нет, указатель на втором мониторе: `switch 1` меняет только второй; проверить в Task 2.
3. Во время переключения окно закрывается или Hyprland отклоняет действие: старый режим остаётся видимым, следующая команда не зависает; проверить в Task 3.
4. Сеанс Quickshell перезапущен или клиент IPC оборвал чтение: окна и сервис работают, новая подписка получает полный снимок; проверить в Task 5.
5. Монитор отключён посреди работы и снова подключён с другим разрешением: пространство возвращается, плавающие окна видны в доступной области; проверить в Task 4.

---

## Порядок остальных планов

1. Этот план: движок пространств и окон с проверяемым CLI. Он не зависит от панели.
2. Quickshell: верхняя панель варианта A, док, трей, показатели, режим и анимации; клиент только читает и вызывает API движка.
3. Системные панели: NetworkManager, Ethernet-профили и откат, звук, яркость, Bluetooth, питание.
4. Ежедневные действия: поиск, снимки с Satty, история буфера, уведомления, блокировка, выход из приложений и остальные сочетания.
5. Установщик и проверка на чистом Arch: сеанс greetd, пакеты, приложения, повторяемость установки, инструкции по сохранению Windows/NTFS и SSH.

Для каждого пункта 2–5 нужен отдельный подробный план перед его реализацией. Зависимость между пунктами — опубликованный IPC-контракт движка; отдельные приложения и установщик можно разрабатывать и проверять независимо от визуальной оболочки.

## Файловая карта этого плана

- `pyproject.toml` — пакет `quietline-engine`, CLI и тестовая зависимость; `LICENSE` — GPL-3.0.
- `src/quietline_engine/types.py` — типы монитора, окна, пространства, геометрии, режима и снимка.
- `src/quietline_engine/hyprland.py` — единственный адаптер к `hyprctl -j`, `hyprctl eval` и сокету событий Hyprland.
- `src/quietline_engine/workspaces.py` — соответствие `(monitor_key, local_number) → workspace_id` и состояние отключённых мониторов.
- `src/quietline_engine/layout.py` — расчёт переходов `windows ↔ tiles` и снимков геометрии.
- `src/quietline_engine/controller.py` — последовательное выполнение команд, согласование событий и публикация подтверждённого снимка.
- `src/quietline_engine/server.py` — протокол JSON Lines поверх Unix-сокета, подписки и клиент.
- `src/quietline_engine/__main__.py` — `quietline-engine serve|switch|move|toggle|state`.
- `config/hyprland/quietline.lua` — минимальные клавиши движка и независимый запуск терминала.
- `tests/engine/` — модульные тесты и поддельный адаптер; `scripts/smoke-window-engine.md` — проверка в живом сеансе.

## Контракт между частями

`Monitor.key` выбирается по производителю, модели и непустому серийному номеру; при отсутствии номера — по имени разъёма. Если идентичный серийный номер повторяется, имя разъёма добавляется к ключу. Ключ при отключении сохраняется до конца сеанса. `workspace_id` — числовой ID Hyprland; существующее активное пространство можно принять как локальное `1`, новые ID выделяются из диапазона `1001+` без пересечения с видимыми ID. При потере монитора назначение `workspace_id` не меняется, меняется только физический монитор показа. Файл состояния привязывается к `HYPRLAND_INSTANCE_SIGNATURE`: перезапуск сервиса сохраняет состояние, новый сеанс его сбрасывает.

Режимы на стороне Hyprland: глобальная раскладка всех пространств — `scrolling` (`hl.config({ general = { layout = "scrolling" } })` в `config/hyprland/quietline.lua`). Режим `windows` — все обычные окна пространства плавающие; режим `tiles` — они же возвращены в раскладку и образуют колонки. Раскладка отдельных пространств не переключается.

Сокет: `$XDG_RUNTIME_DIR/quietline/engine.sock`; каталог `0700`, сокет `0600`. Один запрос — одна JSON-строка с `id`, `method`, `params`; ответ содержит тот же `id` и либо `result`, либо `error {code,message}`. Методы: `switch {number,monitor?}`, `move {number}`, `toggle {monitor?}`, `state {}`, `subscribe {}`. `monitor` применяется к кнопке панели; без него используется монитор фокуса. `subscribe` сначала выдаёт полный `state`, затем события с монотонным `revision`. Ответ `toggle` возвращает уже подтверждённое новое состояние; ошибка оставляет предыдущий режим. Число вне `1`–`10` отвергается без действий Hyprland.

## Карта команд Hyprland 0.55

Сверено с исходниками тега `v0.55.2` (`src/config/lua/bindings/LuaBindingsDispatchers.cpp`, `src/debug/HyprCtl.cpp`, `src/config/lua/objects/LuaWindow.cpp`). Адаптер использует только эти формы; всё остальное — через правку этой таблицы.

**Чтение — только `hyprctl -j`.** `hyprctl eval` возвращает строку `ok` или текст ошибки (`error: …`) и не отдаёт значений, поэтому ничего не читает.

| Что нужно | Команда | Поля ответа |
|---|---|---|
| Мониторы | `hyprctl -j monitors` | `id`, `name`, `make`, `model`, `serial`, `x`, `y`, `width`, `height`, `scale`, `reserved`, `activeWorkspace.id`, `focused` |
| Пространства | `hyprctl -j workspaces` | `id`, `name`, `monitor`, `monitorID`, `windows`, `tiledLayout` |
| Окна | `hyprctl -j clients` | `address` (`0x…`), `workspace.id`, `monitor`, `at`, `size`, `floating`, `fullscreen`, `class`, `title`, `pid`, `mapped`, `hidden`, `pinned`, `tags` (тег правила окна — с `*` в конце) |
| Активное окно | `hyprctl -j activewindow` | `{}` при отсутствии окна |
| Указатель | `hyprctl -j cursorpos` | `x`, `y` |

Порядок колонок `scrolling` и их ширины берутся из снимка `clients`: колонки — группы тайловых окон пространства с одинаковым `at[0]`, порядок — по возрастанию `at[0]`, ширина колонки — `size[0]` её окон, делённая на ширину рабочей области монитора (ширина минус `reserved` слева и справа).

**Действия — `hyprctl eval '<lua>'`.** Один вызов несёт несколько `hl.dispatch(...)` подряд. Успех — ответ ровно `ok`; любой другой ответ — ошибка всего вызова. Адрес окна подставляется только после проверки по шаблону `^0x[0-9a-f]+$`, ID пространства — только целое число, имя монитора — только по шаблону `^[A-Za-z0-9-]+$`; строки собираются без пользовательских кавычек.

| Действие | Lua |
|---|---|
| Сделать окно плавающим / вернуть в раскладку | `hl.dispatch(hl.dsp.window.float({ action = "enable" \| "disable", window = "address:0x…" }))` |
| Поставить окно в точку (пиксели; глобальные координаты макета — подтверждает живая проверка 7) | `hl.dispatch(hl.dsp.window.move({ x = X, y = Y, window = "address:0x…" }))` |
| Задать размер | `hl.dispatch(hl.dsp.window.resize({ x = W, y = H, window = "address:0x…" }))` |
| Сфокусировать окно | `hl.dispatch(hl.dsp.focus({ window = "address:0x…" }))` |
| Открыть или создать пространство на мониторе фокуса | `hl.dispatch(hl.dsp.focus({ workspace = "ID", on_current_monitor = true }))` |
| Сфокусировать монитор | `hl.dispatch(hl.dsp.focus({ monitor = "NAME" }))` |
| Перенести окно на пространство | `hl.dispatch(hl.dsp.window.move({ workspace = "ID", window = "address:0x…", follow = true \| false }))` |
| Перенести пространство на монитор | `hl.dispatch(hl.dsp.workspace.move({ workspace = "ID", monitor = "NAME" }))` |
| Ширина колонки окна в фокусе | `hl.dispatch(hl.dsp.layout("colresize 0.5"))` — доля рабочей области |
| Поменять колонку в фокусе с соседней | `hl.dispatch(hl.dsp.layout("swapcol l" \| "swapcol r"))` — есть в адаптере, движок не использует |

Порядок колонок при возврате в «Тайлы» задаёт порядок вызовов `float disable`: окна возвращаются в раскладку в сохранённом порядке колонок (совпадает ли порядок колонок с порядком вызовов — живая проверка 2). `colresize` действует только на окно в фокусе: ширины восстанавливаются последовательностью «фокус окна → `colresize`», после неё фокус возвращается к прежнему окну.

**События — сокет `$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock`.** Строки `EVENT>>DATA`; движок использует их только как сигнал «перечитать полный снимок».

## Живые проверки

Модульные тесты проверяют логику с поддельным адаптером. Следующее подтверждается только в живом сеансе Hyprland ≥ 0.55 и записывается в `scripts/smoke-window-engine.md` с версией Hyprland и результатом. Пока пункт не проверен, он заносится в `docs/backlog.md`, а не считается пройденным.

1. Ответ `hyprctl eval` на успешный вызов — ровно `ok`; на неверный адрес окна — строка с `error`.
2. Порядок колонок, в котором встают окна при последовательном `float disable`; совпадает ли он с порядком вызовов.
3. `colresize <доля>` даёт ширину колонки, совпадающую с `size[0]` окна из `clients` с точностью до промежутков.
4. Вычисление колонок по `at[0]` верно при прокрученной ленте (часть колонок за краем экрана).
5. `focus({ workspace, on_current_monitor = true })` создаёт пространство с ID `1001+` на мониторе фокуса и не трогает другой монитор.
6. После отключения монитора его пространства переезжают на оставшийся; после подключения `workspace.move` возвращает их назад.
7. `move` с `x`/`y` трактует их как глобальные координаты макета (те же, что `at` в `clients`), а не относительно монитора; плавающее окно после `move`/`resize` стоит в заданных координатах на мониторе с масштабом ≠ 1.
8. События `openwindow`, `closewindow`, `movewindow`, `monitoradded`, `monitorremoved`, `workspace` приходят в `.socket2.sock` в том формате, который разбирает адаптер.

Если пункт 2 или 3 не подтверждается — это стоп-условие плана (раздел в конце): восстановление колонок упрощается только после согласования с пользователем.

## Task 1: Совместимый адаптер Hyprland

**Files:** Create `pyproject.toml`, `LICENSE`, `src/quietline_engine/__init__.py`, `src/quietline_engine/types.py`, `src/quietline_engine/hyprland.py`, `tests/engine/test_hyprland.py`.

**Interfaces:** `Hyprland.snapshot() -> CompositorSnapshot`; `Hyprland.apply(actions: Sequence[HyprAction]) -> None`; `Hyprland.events() -> AsyncIterator[HyprEvent]`. `CompositorSnapshot` содержит `monitors`, `workspaces`, `windows`, `active_window`, `cursor_position`; `HyprAction` задаёт действие без готовой shell-строки. Команды исполняются через `subprocess` со списком аргументов и таймаутом, без `shell=True`.

- [x] Написать `test_snapshot_parses_two_monitors_and_clients`, `test_eval_escapes_only_validated_ids`, `test_hyprctl_failure_raises_without_success_state`: тесты проверяют разобранные поля, безопасные аргументы и ошибку при ненулевом коде.
- [x] Запустить `python -m pytest tests/engine/test_hyprland.py -v`; ожидается FAIL из-за отсутствующего адаптера.
- [x] Реализовать типы и адаптер с `hyprctl -j monitors/workspaces/clients/activewindow/cursorpos`, `hyprctl eval` и чтением `$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock`; валидировать адреса окон и числовые ID до генерации Lua. Добавить текст GPL-3.0 в `LICENSE`.
- [x] Повторить команду теста; ожидается PASS.
- [x] Зафиксировать файлы коммитом `feat: add Hyprland adapter`.

## Task 2: Локальные пространства мониторов

**Files:** Create `src/quietline_engine/workspaces.py`, `tests/engine/test_workspaces.py`.

**Interfaces:** `WorkspaceRegistry.reconcile(snapshot: CompositorSnapshot) -> list[HyprAction]`; `WorkspaceRegistry.resolve(number: int, monitor_key: str, snapshot: CompositorSnapshot) -> WorkspaceRef`; `focused_monitor(snapshot: CompositorSnapshot) -> str`. `WorkspaceRef` содержит `monitor_key`, `display_monitor_key`, `number`, `workspace_id`, `mode='windows'` при создании. Состояние реестра записывается атомарно в `$XDG_RUNTIME_DIR/quietline/state.json`.

- [x] Написать `test_two_monitors_have_independent_local_one`, `test_duplicate_serial_uses_connector`, `test_pointer_selects_monitor_without_active_window`, `test_switch_rejects_zero_and_eleven`, `test_new_hyprland_instance_discards_old_state`; тесты проверяют ID, ключи, границы и отсутствие состояния прошлого сеанса.
- [x] Запустить `python -m pytest tests/engine/test_workspaces.py -v`; ожидается FAIL.
- [x] Реализовать ключи мониторов, выделение ID без коллизий, выбор фокуса, локальные номера и атомарное сохранение состояния сеанса.
- [x] Повторить команду теста; ожидается PASS.
- [x] Зафиксировать файлы коммитом `feat: add monitor-local workspaces`.

## Task 3: Переход режимов и восстановление раскладки

**Files:** Create `src/quietline_engine/layout.py`, `src/quietline_engine/controller.py`, `tests/engine/test_layout.py`, `tests/engine/test_controller.py`.

**Interfaces:** `LayoutPlanner.to_tiles(workspace: WorkspaceRef, snapshot: CompositorSnapshot) -> TransitionPlan`; `LayoutPlanner.to_windows(workspace: WorkspaceRef, snapshot: CompositorSnapshot) -> TransitionPlan`; `WindowController.toggle(monitor_key: str | None = None) -> PublicState`. `TransitionPlan` хранит список действий и обратный план; `PublicState` имеет `revision`, `monitors`, `workspaces`, `error?`. Служебные окна и диалоги исключаются из массового изменения.

- [x] Написать `test_windows_to_tiles_preserves_floating_geometry`, `test_tiles_to_windows_restores_geometry_clamped_to_work_area`, `test_reenter_tiles_restores_column_order_and_widths`, `test_dialog_and_fullscreen_not_rearranged`, `test_failed_or_interrupted_transition_keeps_old_mode`; проверить последовательность действий и итоговый `PublicState` с поддельным адаптером.
- [x] Запустить `python -m pytest tests/engine/test_layout.py tests/engine/test_controller.py -v`; ожидается FAIL.
- [x] Реализовать снимки окон, расчёт переходов и последовательное выполнение под `asyncio.Lock`; после применения читать фактический снимок Hyprland и только затем повышать `revision`. При неудаче применить обратные действия, перечитать снимок и вернуть ошибку.
- [x] Повторить команду теста; ожидается PASS.
- [x] Зафиксировать файлы коммитом `feat: switch workspace window modes`.

## Task 4: События, новые окна и мониторы

**Files:** Modify `src/quietline_engine/controller.py`, `src/quietline_engine/workspaces.py`; Create `tests/engine/test_reconciliation.py`.

**Interfaces:** `WindowController.reconcile(event: HyprEvent) -> PublicState | None`; `WindowController.switch(number: int, monitor_key: str | None = None) -> PublicState`; `WindowController.move(number: int) -> PublicState`. При событии всегда сверять полный снимок, поскольку очередь событий может пропустить промежуточное изменение.

- [x] Написать `test_new_window_floats_only_on_windows_workspace`, `test_moved_window_obeys_destination_mode`, `test_empty_inactive_workspace_is_removed`, `test_disconnected_workspace_is_accessible_and_returns`, `test_reconnected_smaller_monitor_clamps_geometry`; проверить также сохранение локальных номеров второго монитора.
- [x] Запустить `python -m pytest tests/engine/test_reconciliation.py -v`; ожидается FAIL.
- [x] Реализовать обработку открытия/закрытия/переноса окон, смены фокуса и подключения мониторов с повторной сверкой состояния. Для отсутствующего монитора выбрать доступный монитор показа, не меняя исходный `monitor_key` пространства.
- [x] Повторить команду теста; ожидается PASS.
- [x] Зафиксировать файлы коммитом `feat: reconcile window and monitor events`.

## Task 5: IPC, клавиши и проверка на живом сеансе

**Files:** Create `src/quietline_engine/server.py`, `src/quietline_engine/__main__.py`, `config/hyprland/quietline.lua`, `tests/engine/test_server.py`, `scripts/smoke-window-engine.md`; Modify `pyproject.toml`.

**Interfaces:** CLI `quietline-engine serve|switch N|move N|toggle|state`; JSON Lines контракт выше. Lua-конфигурация привязывает `Super+1`–`Super+9`/`Super+0`, соответствующие сочетания с `Shift`, `Super+M`; `Super+Enter` запускает Ghostty непосредственно через Hyprland даже при остановленном сервисе и панели.

- [x] Написать `test_ipc_rejects_invalid_number_and_survives_client_disconnect`, `test_subscribe_sends_snapshot_then_revision`, `test_restart_preserves_session_state`, `test_shortcuts_target_expected_cli_calls`; проверить права сокета и повторную подписку после разрыва.
- [x] Запустить `python -m pytest tests/engine/test_server.py -v`; ожидается FAIL.
- [x] Реализовать сокет, CLI и минимальные привязки, включая глобальную раскладку Hyprland `scrolling` и запуск сервиса. Добавить в `scripts/smoke-window-engine.md` точные команды для Arch VM/живого сеанса с двумя физическими или виртуальными выходами и ожидаемые результаты для каждого пункта проверки.
- [x] Запустить `python -m pytest -v`; ожидается PASS.
- [ ] Выполнить живую проверку по `scripts/smoke-window-engine.md` на установленной стабильной версии Hyprland: локальные пространства двух мониторов, `windows ↔ scrolling`, ширина/порядок колонок, диалоги, отключение/возврат монитора и перезапуск сервиса. Записать проверенные версии и результаты в тот же файл. Не выполнено: разработка идёт на macOS, Hyprland не запускался; порядок проверки — `scripts/smoke-window-engine.md`, непроверенные пункты — `docs/backlog.md`.
- [x] Зафиксировать файлы коммитом `feat: expose window engine through IPC`.

**Совместимость как стоп-условие:** если установленный Hyprland не предоставляет достаточных команд для восстановления порядка или ширины колонок, либо переезда пространства обратно на монитор, не отмечать живую проверку как успешную и не менять обещанное поведение молча. Зафиксировать конкретное ограничение и пересмотреть эту часть плана с пользователем до подключения Quickshell.

## Решения при выполнении

Решения, принятые по ходу выполнения там, где план молчал или расходился с реальностью. Обязательны для следующих правок движка; отмена — через правку этого раздела.

1. **Синхронный адаптер.** `Hyprland.snapshot/apply` остаются синхронными (`subprocess` с таймаутом), `events()` — асинхронный итератор. Контроллер вызывает адаптер через `asyncio.to_thread`; все команды и сверки идут под одной `asyncio.Lock`.
2. **Где хранятся снимки раскладки.** Плавающая геометрия, порядок и ширины колонок, управляемые окна и диалоги — поля записи пространства в том же `state.json`, поэтому переживают перезапуск сервиса.
3. **Рабочая область в логических координатах.** Ширина = `width / scale` − `reserved` слева − `reserved` справа: `width`/`height` в `monitors` — пиксели режима, `at`/`size` окон и `reserved` — логические. Подтверждается живыми проверками 3 и 7.
4. **Диалоги и управляемые окна.** Диалог — окно, плавающее в момент, когда движок увидел его впервые, или окно с тегом `quietline-modal` / `quietline-native-float` (`DIALOG_TAGS` в `types.py`; теги ставит `config/hyprland/quietline.lua`: правило модальных окон и обработчик `window.open` для окон, которые Hyprland открыл плавающими). Тег классифицирует только окна, которых движок ещё не записал ни в один список: управляемое окно остаётся управляемым с любым тегом, в том числе `quietline-modal`, — Hyprland вызывает `window.open` при каждом показе окна, и управляемое окно режима «Окна», показанное снова, получает `quietline-native-float`. Движок управляет только окнами, впервые увиденными в раскладке, и хранит их адреса в записи пространства; переход в «Тайлы» возвращает в колонки только их. Закреплённые (`pinned`) и полноэкранные окна переходы не трогают.
5. **Колонки из нескольких окон — отклонение от спеки.** Колонка из нескольких окон при возврате в «Тайлы» восстанавливается отдельными колонками в порядке её окон: в карте команд нет объединения окон в колонку. Спека обещает «восстанавливаются порядок и ширины колонок»; отклонение ждёт решения пользователя (см. `docs/backlog.md`, «Колонки из нескольких окон»).
6. **Неудачный переход режима.** Режим остаётся прежним, `revision` не растёт, `PublicState.error` содержит причину.
7. **Окно без сохранённой геометрии** при переходе в «Окна» или при появлении в «Окнах» получает 60% рабочей области по центру.
8. **Переподключение к событиям.** Закрытый или недоступный `.socket2.sock` открывается снова в цикле `serve` с растущей паузой; адаптер этого не делает.
9. **Смена монитора показа и рабочей области.** Плавающая геометрия пространства в «Окнах» сдвигается на разницу начала рабочих областей и затем ограничивается рабочей областью.
10. **Границы самовосстановления.** Сверка повторяет только отклонённые Hyprland действия, применяет режим пространства к новым и перенесённым окнам и учитывает смену рабочей области. Окно, которое пользователь сам сделал плавающим или вернул в раскладку, остаётся как есть.
11. **Рассылка подписчикам.** Событие уходит только при росте `revision` или смене текста `error`.
12. **Смена и конец сеанса Hyprland.** Сервис другого сеанса, занявший сокет, получает служебный запрос `takeover` и завершается; сервис того же сеанса — отказ `already_running`. Сеанс считается законченным, когда поток событий закрылся и в `$XDG_RUNTIME_DIR/hypr/<сигнатура>` нет каталога, `hyprland.lock` или `.socket2.sock`; тогда `serve` завершается.
13. **Отказ возврата пространства.** Если Hyprland отклонил перенос пространства на вернувшийся монитор, сверка окон всё равно выполняется по перечитанному снимку, а обе ошибки возвращаются вместе.
