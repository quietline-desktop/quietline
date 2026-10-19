# Quietline Window Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Рабочий сервис, который на каждом мониторе открывает локальные пространства `1`–`10` и независимо переключает их между обычными окнами и прокручиваемыми колонками.

**Architecture:** Python-сервис хранит состояние только в текущем сеансе и принимает команды через Unix-сокет. Адаптер Hyprland читает снимки композитора и применяет действия; контроллер рассчитывает переходы и публикует подтверждённое состояние. Quickshell в следующих планах станет клиентом этого API, а не вторым владельцем режима.

**Tech Stack:** Arch Linux, стабильный Hyprland с Lua API и встроенным `scrolling`, Python 3 (стандартная библиотека), pytest для разработки, Unix domain sockets.

**Spec:** `docs/superpowers/specs/2026-10-19-quietline-desktop-design.md`

## Global Constraints

- Сеанс устанавливается поверх Arch Linux после Archinstall Minimal; установщик и разметка диска в этот план не входят.
- Использовать встроенный `scrolling` Hyprland и поддерживаемые команды Lua; не копировать Hyprstack и не подключать нативный модуль.
- Режим нового пространства — `windows`; режимы и геометрия существуют только в текущем сеансе в `$XDG_RUNTIME_DIR`.
- У каждого монитора локальные пространства `1`–`10`; цифровые сочетания действуют только на монитор с фокусом.
- Отключённые пространства остаются доступными на оставшемся мониторе и возвращаются при повторном подключении своего монитора.
- Собственный код Quietline — GPL-3.0; секреты и личные файлы в репозиторий не добавлять.
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
- `tests/` — модульные тесты и поддельный адаптер; `scripts/smoke-window-engine.md` — проверка в живом сеансе.

## Контракт между частями

`Monitor.key` выбирается по производителю, модели и непустому серийному номеру; при отсутствии номера — по имени разъёма. Если идентичный серийный номер повторяется, имя разъёма добавляется к ключу. Ключ при отключении сохраняется до конца сеанса. `workspace_id` — числовой ID Hyprland; существующее активное пространство можно принять как локальное `1`, новые ID выделяются из диапазона `1001+` без пересечения с видимыми ID. При потере монитора назначение `workspace_id` не меняется, меняется только физический монитор показа. Файл состояния привязывается к `HYPRLAND_INSTANCE_SIGNATURE`: перезапуск сервиса сохраняет состояние, новый сеанс его сбрасывает.

Сокет: `$XDG_RUNTIME_DIR/quietline/engine.sock`; каталог `0700`, сокет `0600`. Один запрос — одна JSON-строка с `id`, `method`, `params`; ответ содержит тот же `id` и либо `result`, либо `error {code,message}`. Методы: `switch {number,monitor?}`, `move {number}`, `toggle {monitor?}`, `state {}`, `subscribe {}`. `monitor` применяется к кнопке панели; без него используется монитор фокуса. `subscribe` сначала выдаёт полный `state`, затем события с монотонным `revision`. Ответ `toggle` возвращает уже подтверждённое новое состояние; ошибка оставляет предыдущий режим. Число вне `1`–`10` отвергается без действий Hyprland.

## Task 1: Совместимый адаптер Hyprland

**Files:** Create `pyproject.toml`, `LICENSE`, `src/quietline_engine/__init__.py`, `src/quietline_engine/types.py`, `src/quietline_engine/hyprland.py`, `tests/test_hyprland.py`.

**Interfaces:** `Hyprland.snapshot() -> CompositorSnapshot`; `Hyprland.apply(actions: Sequence[HyprAction]) -> None`; `Hyprland.events() -> AsyncIterator[HyprEvent]`. `CompositorSnapshot` содержит `monitors`, `workspaces`, `windows`, `active_window`, `cursor_position`; `HyprAction` задаёт действие без готовой shell-строки. Команды исполняются через `subprocess` со списком аргументов и таймаутом, без `shell=True`.

- [ ] Написать `test_snapshot_parses_two_monitors_and_clients`, `test_eval_escapes_only_validated_ids`, `test_hyprctl_failure_raises_without_success_state`: тесты проверяют разобранные поля, безопасные аргументы и ошибку при ненулевом коде.
- [ ] Запустить `python -m pytest tests/test_hyprland.py -v`; ожидается FAIL из-за отсутствующего адаптера.
- [ ] Реализовать типы и адаптер с `hyprctl -j monitors/workspaces/clients/activewindow/cursorpos`, `hyprctl eval` и чтением `$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock`; валидировать адреса окон и числовые ID до генерации Lua. Добавить текст GPL-3.0 в `LICENSE`.
- [ ] Повторить команду теста; ожидается PASS.
- [ ] Зафиксировать файлы коммитом `feat: add Hyprland adapter`.

## Task 2: Локальные пространства мониторов

**Files:** Create `src/quietline_engine/workspaces.py`, `tests/test_workspaces.py`.

**Interfaces:** `WorkspaceRegistry.reconcile(snapshot: CompositorSnapshot) -> list[HyprAction]`; `WorkspaceRegistry.resolve(number: int, monitor_key: str, snapshot: CompositorSnapshot) -> WorkspaceRef`; `focused_monitor(snapshot: CompositorSnapshot) -> str`. `WorkspaceRef` содержит `monitor_key`, `display_monitor_key`, `number`, `workspace_id`, `mode='windows'` при создании. Состояние реестра записывается атомарно в `$XDG_RUNTIME_DIR/quietline/state.json`.

- [ ] Написать `test_two_monitors_have_independent_local_one`, `test_duplicate_serial_uses_connector`, `test_pointer_selects_monitor_without_active_window`, `test_switch_rejects_zero_and_eleven`, `test_new_hyprland_instance_discards_old_state`; тесты проверяют ID, ключи, границы и отсутствие состояния прошлого сеанса.
- [ ] Запустить `python -m pytest tests/test_workspaces.py -v`; ожидается FAIL.
- [ ] Реализовать ключи мониторов, выделение ID без коллизий, выбор фокуса, локальные номера и атомарное сохранение состояния сеанса.
- [ ] Повторить команду теста; ожидается PASS.
- [ ] Зафиксировать файлы коммитом `feat: add monitor-local workspaces`.

## Task 3: Переход режимов и восстановление раскладки

**Files:** Create `src/quietline_engine/layout.py`, `src/quietline_engine/controller.py`, `tests/test_layout.py`, `tests/test_controller.py`.

**Interfaces:** `LayoutPlanner.to_tiles(workspace: WorkspaceRef, snapshot: CompositorSnapshot) -> TransitionPlan`; `LayoutPlanner.to_windows(workspace: WorkspaceRef, snapshot: CompositorSnapshot) -> TransitionPlan`; `WindowController.toggle(monitor_key: str | None = None) -> PublicState`. `TransitionPlan` хранит список действий и обратный план; `PublicState` имеет `revision`, `monitors`, `workspaces`, `error?`. Служебные окна и диалоги исключаются из массового изменения.

- [ ] Написать `test_windows_to_tiles_preserves_floating_geometry`, `test_tiles_to_windows_restores_geometry_clamped_to_work_area`, `test_reenter_tiles_restores_column_order_and_widths`, `test_dialog_and_fullscreen_not_rearranged`, `test_failed_or_interrupted_transition_keeps_old_mode`; проверить последовательность действий и итоговый `PublicState` с поддельным адаптером.
- [ ] Запустить `python -m pytest tests/test_layout.py tests/test_controller.py -v`; ожидается FAIL.
- [ ] Реализовать снимки окон, расчёт переходов и последовательное выполнение под `asyncio.Lock`; после применения читать фактический снимок Hyprland и только затем повышать `revision`. При неудаче применить обратные действия, перечитать снимок и вернуть ошибку.
- [ ] Повторить команду теста; ожидается PASS.
- [ ] Зафиксировать файлы коммитом `feat: switch workspace window modes`.

## Task 4: События, новые окна и мониторы

**Files:** Modify `src/quietline_engine/controller.py`, `src/quietline_engine/workspaces.py`; Create `tests/test_reconciliation.py`.

**Interfaces:** `WindowController.reconcile(event: HyprEvent) -> PublicState | None`; `WindowController.switch(number: int, monitor_key: str | None = None) -> PublicState`; `WindowController.move(number: int) -> PublicState`. При событии всегда сверять полный снимок, поскольку очередь событий может пропустить промежуточное изменение.

- [ ] Написать `test_new_window_floats_only_on_windows_workspace`, `test_moved_window_obeys_destination_mode`, `test_empty_inactive_workspace_is_removed`, `test_disconnected_workspace_is_accessible_and_returns`, `test_reconnected_smaller_monitor_clamps_geometry`; проверить также сохранение локальных номеров второго монитора.
- [ ] Запустить `python -m pytest tests/test_reconciliation.py -v`; ожидается FAIL.
- [ ] Реализовать обработку открытия/закрытия/переноса окон, смены фокуса и подключения мониторов с повторной сверкой состояния. Для отсутствующего монитора выбрать доступный монитор показа, не меняя исходный `monitor_key` пространства.
- [ ] Повторить команду теста; ожидается PASS.
- [ ] Зафиксировать файлы коммитом `feat: reconcile window and monitor events`.

## Task 5: IPC, клавиши и проверка на живом сеансе

**Files:** Create `src/quietline_engine/server.py`, `src/quietline_engine/__main__.py`, `config/hyprland/quietline.lua`, `tests/test_server.py`, `scripts/smoke-window-engine.md`; Modify `pyproject.toml`.

**Interfaces:** CLI `quietline-engine serve|switch N|move N|toggle|state`; JSON Lines контракт выше. Lua-конфигурация привязывает `Super+1`–`Super+9`/`Super+0`, соответствующие сочетания с `Shift`, `Super+M`; `Super+Enter` запускает Ghostty непосредственно через Hyprland даже при остановленном сервисе и панели.

- [ ] Написать `test_ipc_rejects_invalid_number_and_survives_client_disconnect`, `test_subscribe_sends_snapshot_then_revision`, `test_restart_preserves_session_state`, `test_shortcuts_target_expected_cli_calls`; проверить права сокета и повторную подписку после разрыва.
- [ ] Запустить `python -m pytest tests/test_server.py -v`; ожидается FAIL.
- [ ] Реализовать сокет, CLI и минимальные привязки, включая глобальную раскладку Hyprland `scrolling` и запуск сервиса. Добавить в `scripts/smoke-window-engine.md` точные команды для Arch VM/живого сеанса с двумя физическими или виртуальными выходами и ожидаемые результаты для каждого пункта проверки.
- [ ] Запустить `python -m pytest -v`; ожидается PASS. Затем выполнить живую проверку по `scripts/smoke-window-engine.md` на установленной стабильной версии Hyprland: локальные пространства двух мониторов, `windows ↔ scrolling`, ширина/порядок колонок, диалоги, отключение/возврат монитора и перезапуск сервиса. Записать проверенные версии и результаты в тот же файл.
- [ ] Зафиксировать файлы коммитом `feat: expose window engine through IPC`.

**Совместимость как стоп-условие:** если установленный Hyprland не предоставляет достаточных команд для восстановления порядка или ширины колонок, либо переезда пространства обратно на монитор, не отмечать живую проверку как успешную и не менять обещанное поведение молча. Зафиксировать конкретное ограничение и пересмотреть эту часть плана с пользователем до подключения Quickshell.
