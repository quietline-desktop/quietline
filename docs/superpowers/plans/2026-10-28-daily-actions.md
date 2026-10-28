# Ежедневные действия

**Статус:** выполняется (ветка `feature/daily-actions`): части 1–6 написаны, документация и ревью — впереди.
**Цель:** блокировка и меню питания, корректный выход из приложений, уведомления, снимки экрана, история буфера, общий поиск и оставшиеся сочетания клавиш спеки — то, без чего окружение не годится для ежедневной работы.
**Спецификация:** `docs/superpowers/specs/2026-10-19-quietline-desktop-design.md` — «Основа и границы компонентов» (п. 4), «Оболочка и внешний вид» (кнопка питания, уведомления, службы Wayland), «Ежедневные действия и сочетания клавиш», «Ошибки, проверка и готовность» (п. 4). Внешний вид — `DESIGN.md`.
**Основа:** этапы 1–3 в `main`: движок и `config/hyprland/quietline.lua`, оболочка `shell/quietline`, `quietline-shell`.

## Границы и решения

Части идут в порядке пользы для ежедневной работы; каждая часть — коммиты с зелёными тестами, независимое ревью — по всей ветке в конце.

1. **Сеанс:** `Super+L`, кнопка питания и меню «Заблокировать / Выйти из сеанса / Перезагрузить / Выключить».
2. **Выход из приложений:** `Super+W`, `Super+Q`, `Super+Shift+Q`, запуск приложений оболочки в отдельной группе процессов.
3. **Уведомления и снимки экрана:** сервер уведомлений оболочки, `PrintScreen`, `Super+Shift+S`.
4. **История буфера:** запись через cliphist в `$XDG_RUNTIME_DIR`, `Super+V`, пауза и очистка, очистка при блокировке и выходе.
5. **Поиск:** `Super+Space` — приложения, файлы домашнего каталога, системные действия и разделы настроек, простые вычисления.
6. **Клавиши окон и памятка:** стрелки, `Super+F`, `Alt+Tab`, `Super+E`, `Super+Alt+Space`, `Super+F1`, перетаскивание с `Super`.

Решения:

- **Блокировка — отдельный процесс Quickshell.** `quietline-shell lock` запускает `qs -p $XDG_CONFIG_HOME/quickshell/quietline/lock/LockScreen.qml`, если блокировка ещё не запущена, и выходит. Экран блокировки — `WlSessionLock` (Quickshell 0.3.2, `Quickshell.Wayland`) с поверхностью на каждом экране и проверкой пароля через `PamContext` (`Quickshell.Services.Pam`) по системной конфигурации PAM `login` (умолчание `PamContext`). Падение панели блокировку не трогает, `Super+L` привязан в Lua напрямую к `quietline-shell lock`. Если упадёт сам процесс блокировки, Hyprland оставляет экран заблокированным; повторный `Super+L` запускает новый экран блокировки: `misc.allow_session_lock_restore = true` (есть в 0.55, по умолчанию выключено).
- **Выход, перезагрузка, выключение** — `quietline-shell session logout|reboot|poweroff`: корректно закрывает все окна (`hyprctl dispatch 'hl.dsp.window.close({window = "address:…"})'`), ждёт до 20 с и только без оставшихся окон выполняет действие: выход — `hl.dsp.exit()`, перезагрузка и выключение — `systemctl reboot|poweroff` (logind разрешает активному локальному пользователю без пароля и учитывает блокировки `systemd-inhibit`). Оставшиеся окна возвращаются списком приложений; меню показывает их и не выключает компьютер. Подтверждение — в том же меню, второй строкой.
- **Приложения оболочки запускаются в своей группе процессов**: док и поиск запускают `DesktopEntry.command` через `Quickshell.execDetached` с `systemd-run --user --scope --collect --unit=app-quietline-<id>-<случайно>`. `quietline-shell app quit` закрывает все окна процесса активного окна, ждёт их закрытия и, если процесс остался без окон и он из группы `app-quietline-*`, посылает `SIGTERM` её процессам (`systemctl --user kill`). Пока у процесса есть окно (в том числе диалог сохранения), сигнал не посылается. Процесс не из группы Quietline после закрытия окон не трогается: оболочка сообщает, что приложение осталось в фоне, и предлагает `Super+Shift+Q`. `Super+Shift+Q` — подтверждение во всплывающем окне панели, затем `quietline-shell app kill --pid P` (`SIGKILL`). Таблица известных команд выхода (`KNOWN_QUIT`) начинается пустой; приложение добавляется после проверки его команды вживую.
- **Уведомления** — `NotificationServer` (`Quickshell.Services.Notifications`) в оболочке: всплывают справа под панелью на мониторе с фокусом, не больше трёх; обычные исчезают через 6 с (или `expireTimeout` приложения, если он короче), критические остаются до закрытия. Текст — только `Text.PlainText`; действия уведомлений — кнопками. Истории уведомлений и режима «Не беспокоить» нет.
- **Снимки** — `quietline-shell screenshot output|region`. `output`: `grim -o <монитор с фокусом> -` → файл `Screenshot_ГГГГ-ММ-ДД_ЧЧ-ММ-СС.png` в `$(xdg-user-dir PICTURES)/Screenshots` → `wl-copy --type image/png`; уведомление «Снимок сохранён и скопирован» — только после обоих шагов, ошибка называет неудавшийся шаг. `region`: `slurp` (отмена — тихий выход) → `grim -g <область> -` → `satty --filename - --output-filename <тот же шаблон> --copy-command wl-copy --early-exit all`; Enter копирует, `Ctrl+S` сохраняет, `Esc` отменяет (умолчания Satty 0.22). Каталог создаётся заранее.
- **Тексты уведомлений из `quietline-shell`** (снимки, буфер) — по-русски через `notify-send`: это интерфейс окружения, а не вывод в консоль. Ответы CLI и ошибки в stdout — по-английски, как у остальных подкоманд.
- **История буфера** — `wl-paste --type text --watch quietline-shell clipboard store` и то же для `image`, запуск из `hl.on("hyprland.start", …)`. `store` пропускает запись при паузе (файл-флаг в `$XDG_RUNTIME_DIR/quietline/`), при `CLIPBOARD_STATE=sensitive` и когда активное окно — 1Password (класс `1password`); остальное передаёт `cliphist -db-path $XDG_RUNTIME_DIR/quietline/clipboard.db store`. Подкоманды `list`, `restore ID`, `delete ID`, `wipe`, `pause --on|--off`. Блокировка и выход из сеанса вызывают `wipe`. Панель `Super+V` — поиск по истории, превью картинок через `decode` во временный файл в `$XDG_RUNTIME_DIR`.
- **Поиск** заменяет меню приложений `Super+Space` (IPC `launcher` остаётся и открывает поиск): приложения — из `DesktopModel`; системные действия — блокировка, выход, перезагрузка, выключение, снимок, история буфера; разделы окна «Настройки»; вычисления — собственный разбор арифметики в `Models.js` (числа, `+ - * / % ^`, скобки), без `eval`; файлы — `quietline-shell files QUERY` по личной базе plocate `$XDG_CACHE_HOME/quietline/home.db` (`updatedb -l 0 -U ~ -o …`), база обновляется при входе и не чаще раза в час при поиске. Интернет-поиска нет.
- **Клавиши окон** привязываются в `config/hyprland/quietline.lua` Lua-диспетчерами 0.55 (`hl.dsp.focus({direction})`, `hl.dsp.window.move({direction})`, `hl.dsp.focus({monitor})`, `hl.dsp.window.fullscreen({mode})`, `hl.dsp.window.cycle_next()`, `hl.dsp.window.float({action = "toggle"})`). Сдвиг плавающего окна небольшим шагом в «Окнах» и взаимодействие `Super+Alt+Space` с движком (окно, сделанное плавающим в «Тайлах», не возвращается в колонку до смены режима) проверяются по коду движка и Lua API перед шагом; расхождение — стоп и правка плана. Жесты тачпада — вне этапа (пункт в `docs/backlog.md`).
- **Блокировка перед сном и по бездействию** спекой не требуется и в этап не входит.

## Контракт новых подкоманд `quietline-shell`

Как у остальных: одна строка JSON в stdout, ошибка — `{"error": "<text>"}` и код 1.

| Подкоманда | Результат |
| --- | --- |
| `lock` | `{"locked": true}` — экран блокировки запущен или уже был; история буфера очищена |
| `session logout\|reboot\|poweroff [--timeout S]` | `{"action", "done": true}` или `{"action", "done": false, "remaining": [{"app", "title"}]}` |
| `app quit [--pid P] [--timeout S] [--notify]` | `{"closed", "remaining", "background"}` (+ `app` при `background`) — `background`: процесс остался без окон и не из группы Quietline; `--notify` сообщает об этом уведомлением |
| `app kill --pid P` | `{"killed": P}` |
| `screenshot output\|region` | `{"path", "copied": true}` / для `region` — `{"started": true}` или `{"cancelled": true}` |
| `clipboard store` (stdin) | `{"stored": bool, "reason"?}` |
| `clipboard list` | `{"entries": [{"id", "kind": "text"\|"image", "preview"}], "paused"}` |
| `clipboard restore\|delete --id ID`, `wipe`, `pause --on\|--off` | `{"ok": true}` |
| `clipboard image --id ID` | `{"path"}` — PNG во временном каталоге `$XDG_RUNTIME_DIR/quietline/` |
| `files QUERY [--limit N]` | `{"files": [path…], "indexedAt"}` |
| `files --update` | `{"indexedAt"}` |

## Файлы

Python (`src/quietline_shell/` не больше восьми записей):

- `session.py` — блокировка, выход/перезагрузка/выключение, выход и принудительное завершение приложений, запуск в группе процессов;
- `capture.py` — снимки экрана; `clipboard.py` — история буфера; `search.py` — личная база plocate;
- `system_info.py` переезжает в `config.py` (сведения для оболочки), `__main__.py` подключает подкоманды.

Тесты Python оболочки переезжают в `tests/helper/` (`test_shell_config.py`, `test_network.py`, `test_session.py`, `test_capture.py`, `test_clipboard.py`, `test_search.py`); в `tests/shell/` остаются модели и контракты (`models.test.cjs`, `polkit.test.cjs`, `engine-protocol.json`, `test_engine_protocol.py`).

QML (`shell/quietline/`):

- `lock/` — `LockScreen.qml` (корень отдельного процесса), `LockSurface.qml`;
- `session/` — `PowerMenu.qml` (меню кнопки питания), `SessionService.qml` (вызовы `quietline-shell session` и `app`), `KillConfirm.qml`;
- `notifications/` — `NotificationService.qml`, `NotificationPopups.qml`;
- `clipboard/` — `ClipboardService.qml`, `ClipboardPanel.qml`;
- `search/` — `SearchService.qml`, `SearchPanel.qml`;
- правки `bar/TopBar.qml` (кнопка питания последней, поиск вместо меню приложений, панели буфера и подтверждения), `services/DesktopModel.qml` (запуск через `app launch`), `shell.qml` (сервисы, IPC `clipboard`, `confirmKill`, `power`), `logic/Models.js` (вычисления, ранжирование поиска, подписи).

Конфигурация и документы: `config/hyprland/quietline.lua` (клавиши, наблюдатели буфера, индекс файлов), `scripts/smoke-daily-actions.md`, `docs/backlog.md`, `README.md`, `DESIGN.md`, `CHANGELOG.md`, `AGENTS.md`.

## Review Focus

1. **Блокировка не открывает сеанс:** падение панели и падение экрана блокировки не снимают блокировку; неверный пароль и `MaxTries` не разблокируют; повторный `Super+L` при запущенной блокировке не создаёт второй процесс.
2. **Выход и выключение не теряют документы:** окно с несохранённым документом (диалог сохранения) останавливает выход, перезагрузку и выключение; меню называет оставшиеся приложения; `SIGTERM` не посылается процессу с открытым окном; `Super+Q` никогда не посылает `SIGKILL`.
3. **Снимок не объявляется готовым раньше времени:** ошибка `grim`, записи файла или `wl-copy` даёт уведомление об ошибке нужного шага; `PrintScreen` снимает только монитор с фокусом.
4. **Секреты не попадают в историю:** запись с `CLIPBOARD_STATE=sensitive`, копирование из окна 1Password и запись на паузе не сохраняются; блокировка и выход очищают историю; база — только в `$XDG_RUNTIME_DIR`.
5. **Вычисления в поиске безопасны:** ввод вроде `constructor`, `1;alert(1)`, `2**1000`, деление на ноль не исполняет код и не роняет поиск.

## Task 1: Сеанс

- [x] Перенести `system_info.py` в `config.py`, Python-тесты оболочки — в `tests/helper/`; обновить `AGENTS.md`.
- [x] `session.py`: `lock` (единственный экземпляр, запуск `qs -p`), `session logout|reboot|poweroff` с ожиданием окон; тесты на поддельных `hyprctl`, `systemctl`, `qs`.
- [x] `lock/`: экран блокировки с полем пароля, `PamContext`, сообщениями PAM и часами; поверхность на каждом экране.
- [x] `session/PowerMenu.qml`, `SessionService.qml`, кнопка питания последней на панели цветом `danger`, подтверждение второй строкой, список оставшихся приложений.
- [x] Lua: `Super+L` → `quietline-shell lock`; проверка в `tests/engine/test_server.py`.
- [x] Тесты → PASS, статическая проверка QML.

## Task 2: Выход из приложений

- [x] `session.py`: `app launch|quit|kill`, распознавание группы `app-quietline-*` по `/proc/<pid>/cgroup`; тесты: окно с диалогом не получает сигнал, чужой процесс не получает сигнал, `quit` не посылает `SIGKILL`.
- [x] `DesktopModel.launch` и «Новое окно» запускают через `app launch`; меню дока «Выйти» — через `app quit` для окон приложения.
- [x] `session/KillConfirm.qml`, IPC `confirmKill`; Lua: `Super+W` → `hl.dsp.window.close()`, `Super+Q` → `quietline-shell app quit`, `Super+Shift+Q` → IPC `confirmKill`.
- [x] Тесты → PASS.

## Task 3: Уведомления и снимки экрана

- [x] `notifications/`: сервер, всплывающие уведомления на мониторе с фокусом, действия, сроки; функции сроков в `Models.js` с тестами.
- [x] `capture.py`: `screenshot output|region`, имя файла, порядок «файл → буфер → уведомление», ошибки по шагам; тесты.
- [x] Lua: `Print`, `SUPER + SHIFT + S`.
- [x] Тесты → PASS, статическая проверка QML.

## Task 4: История буфера

- [x] `clipboard.py`: `store` с фильтрами, `list|restore|delete|wipe|pause|image`; тесты фильтров и путей.
- [x] `clipboard/`: сервис и панель с поиском, превью картинок, «Приостановить запись», «Очистить»; IPC `clipboard`.
- [x] Lua: наблюдатели `wl-paste` при запуске, `Super+V`; `lock` и `session logout` очищают историю.
- [x] Тесты → PASS.

## Task 5: Поиск

- [x] `search.py`: `files QUERY`, `files --update`; тесты на поддельном `plocate`/`updatedb`.
- [x] `Models.js`: безопасный калькулятор, ранжирование результатов, системные действия и разделы настроек; тесты, в том числе Review Focus 5.
- [x] `search/`: сервис и панель вместо меню приложений; IPC `launcher` открывает поиск; Lua: индекс файлов при запуске.
- [x] Тесты → PASS.

## Task 6: Клавиши окон и памятка

- [x] Сверить Lua API 0.55 для сдвига плавающего окна и поведение движка с окном, сделанным плавающим в «Тайлах».
- [x] Lua: `Super+←/→/↑/↓`, `Super+Shift+←/→/↑/↓`, `Super+Alt+←/→`, `Super+Alt+Space`, `Super+F`, `Super+Shift+F`, `Alt+Tab`, `Super+E`, `Super+F1` (окно «Настройки» на «Сочетаниях клавиш»), `Super` + левая/правая кнопка мыши; проверки в `tests/engine/test_server.py`, описания в `Models.bindAction`.
- [x] Тесты → PASS.

## Task 7: Документация и проверка

- [x] `scripts/smoke-daily-actions.md`, пункты в `docs/backlog.md`, `README.md`, `DESIGN.md`, `CHANGELOG.md`, `AGENTS.md`.
- [x] Полные `pytest` и `node --test` → PASS; аудит: нет `shell=True` и eval, секреты не в аргументах и журналах.
- [ ] Независимое ревью ветки по Review Focus; существенные замечания исправить с воспроизводящими тестами.
- [ ] Живая проверка `scripts/smoke-daily-actions.md` на Arch — вместе с этапами 1–3.

## Решения при выполнении

1. **PAM экрана блокировки** — системная конфигурация `login` из `/etc/pam.d` (умолчание `PamContext`): свой файл PAM не нужен, правила те же, что при входе.
2. **Цвет кнопки питания** — `ShellButton.foreground` (цвет текста доступной кнопки без выделения), у кнопки питания — `Theme.danger`.
3. **Подписи действий сеанса** — `Models.SESSION_LABELS`, `SESSION_QUESTIONS`, `remainingText`, `sessionErrorText`; меню питания — `session/PowerMenu.qml` во всплывающем окне панели (`power`).
4. **Запуск без подкоманды `app launch`.** Оболочка сама строит команду `Models.launchCommand(entry.command, Models.scopeUnit(id, token))` — у `DesktopEntry` и `DesktopAction` Quickshell 0.3.2 есть разобранная команда `command`. «Выйти» в доке вызывает `app quit --pid P --notify` для каждого процесса окон приложения.
5. **Подтверждение `Super+Shift+Q`** — `session/KillConfirm.qml` во всплывающем окне панели монитора с фокусом (IPC `confirmKill`), фокус по умолчанию — на «Отмена».
6. **Проверка комментариев Lua-конфига** в `tests/engine/test_server.py` смотрит строки, начинающиеся с `--`: аргументы вроде `--notify` в командах комментариями не считаются.
7. **Уведомления** — `notifications/NotificationService.qml` (сервер, все уведомления отслеживаются) и `NotificationPopups.qml` (окно на мониторе с фокусом, сроки у всех отслеживаемых). Сроки — `Models.notificationTimeout`: критическое — до закрытия, остальные — не дольше 6 с.
8. **Поиск** — `search/SearchPanel.qml` вместо меню приложений во всплывающем окне панели (имя содержимого `applications`, поле `applicationsOpen` в IPC `status` прежнее). Ранжирование и калькулятор — `Models.searchResults`, `Models.calculate`; выход, перезагрузка и выключение из поиска открывают меню питания с этим действием на подтверждении. Файлы ищутся с задержкой 250 мс и от двух символов (`search/SearchService.qml`).
9. **Клавиши окон.** Сдвиг на шаг — Lua-функция `move_or_nudge`: `hl.get_active_window().floating` → `hl.dsp.window.move({x, y, relative = true})` на 40 px, иначе `hl.dsp.window.move({direction})`. Движок окно, сделанное плавающим в «Тайлах», не возвращает в колонку до смены режима (`layout.py`: действия получают только новые окна). `Alt+Tab` — `cycle_next` и `bring_to_top`. Привязки стандартного примера Hyprland удаляются целиком — раздел **Breaking** в `CHANGELOG.md`.
