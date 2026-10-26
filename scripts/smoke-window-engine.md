# Живая проверка движка пространств и окон

Модульные тесты проверяют движок с поддельным Hyprland. Здесь — то, что подтверждается только в живом сеансе: команды Hyprland из карты команд плана, клавиши, мониторы и перезапуск сервиса. Пока пункт не проверен, он числится в `docs/backlog.md`.

Нумерация: **РФ1–РФ5** — «Review Focus» плана `docs/superpowers/plans/2026-10-19-window-engine.md`, **Ж1–Ж8** — его «Живые проверки», **К** — клавиши и запуск, **П** — сервис и сокет.

**Стоп-условие.** Если Hyprland не даёт восстановить порядок или ширину колонок (Ж2, Ж3, Ж4) или вернуть пространство на монитор (Ж6), пункт не отмечается пройденным, а обещанное поведение молча не меняется: конкретное ограничение записывается в результаты ниже и в `docs/backlog.md`, план пересматривается с пользователем до подключения Quickshell.

## Стенд

- Arch Linux (VM или установленная система) после Archinstall Minimal, пакеты из `extra`.
- Два выхода. На железе — два монитора; для РФ1 — два одинаковых монитора без серийного номера. В VM (QEMU/virt-manager) — видеокарта `virtio-gpu` с двумя выходами (`max_outputs=2`); у виртуальных выходов серийного номера нет. Запасной вариант без второго экрана — виртуальный выход `hyprctl output create headless QL-2` и `hyprctl output remove QL-2`, если эти команды есть в установленной версии (записать в результаты, какой вариант использован).
- Один выход с масштабом ≠ 1 для Ж7 (например, `1.5` в настройке монитора).

## Подготовка

```sh
sudo pacman -S --needed hyprland ghostty python uv git jq socat
hyprctl version                    # после входа в Hyprland; записать в «Результаты»
git clone <адрес репозитория> ~/quietline && cd ~/quietline
uv run --python 3.14 pytest -W error
uv tool install --python 3.14 .    # ставит ~/.local/bin/quietline-engine
command -v quietline-engine
```

Hyprland запускается из входа в TTY: `~/.local/bin` должен быть в `PATH` этой оболочки до запуска Hyprland (иначе клавиши движка и автозапуск сервиса не найдут команду).

Конфигурация:

```sh
pacman -Ql hyprland | grep -E 'hyprland\.lua$'          # путь примера конфигурации из пакета
mkdir -p ~/.config/hypr
cp <путь из предыдущей команды> ~/.config/hypr/hyprland.lua
cp ~/quietline/config/hyprland/quietline.lua ~/.config/hypr/quietline.lua
```

В `~/.config/hypr/hyprland.lua` удалить привязку `mainMod .. " + M"` (в примере это выход из Hyprland), цикл `for i = 1, 10` с привязками пространств и строку `layout = "dwindle"`; в конец добавить `require("quietline")`. Войти в Hyprland заново.

Вспомогательные команды:

```sh
st() { quietline-engine state | jq -c '.monitors[] | {key, name, focused, active_number, active_workspace_id, mode}'; }
ws() { hyprctl -j workspaces | jq -c '.[] | {id, monitor, windows}'; }
cl() { hyprctl -j clients | jq -c '.[] | {address, ws: .workspace.id, at, size, floating, class}'; }
```

## К. Клавиши и запуск

| Шаг | Ожидается |
|---|---|
| После входа: `pgrep -af 'quietline-engine serve'` | ровно один процесс |
| `hyprctl -j workspaces \| jq '.[].tiledLayout'` | `"scrolling"` у всех пространств |
| `Super+Enter` | открывается Ghostty |
| `Super+3`, затем `st` | на мониторе с фокусом `active_number: 3`, `active_workspace_id` ≥ 1001, режим `windows` |
| `Super+0`, затем `st` | `active_number: 10` |
| Открыть Ghostty, `Super+Shift+2`, затем `st` и `cl` | окно на пространстве `2` того же монитора, фокус перешёл за ним |
| `Super+M`, затем `st` | режим активного пространства сменился (`windows` ↔ `tiles`) |

## П. Сервис и сокет

| Шаг | Ожидается |
|---|---|
| `stat -c '%a %F' "$XDG_RUNTIME_DIR/quietline" "$XDG_RUNTIME_DIR/quietline/engine.sock"` | `700 directory`, `600 socket` |
| `quietline-engine serve; echo $?` при работающем сервисе | `quietline-engine: another quietline-engine is already running on …`, код `1` |
| `quietline-engine switch 11; echo $?` | `quietline-engine: workspace number must be an integer from 1 to 10, got 11`, код `1`; в мониторе событий (Ж8) нет новых строк |
| Перезапуск: запомнить `st`, `pkill -f 'quietline-engine serve'` | окна остаются на местах; `Super+Enter` открывает Ghostty; `quietline-engine state` — `cannot connect to quietline-engine …`, код `1` |
| `quietline-engine serve &`, затем `st` | те же пространства, номера и режимы, что до остановки |
| `pkill -9 -f 'quietline-engine serve'`, затем `quietline-engine serve &` | сервис стартует (файл сокета от убитого процесса заменён), `st` работает |
| Запомнить сигнатуру `echo $HYPRLAND_INSTANCE_SIGNATURE` и PID из `pgrep -af 'quietline-engine serve'`, `hyprctl dispatch 'hl.dsp.exit()'`, в TTY через 15 с `pgrep -af 'quietline-engine serve'` и `ls -la "$XDG_RUNTIME_DIR/hypr/<сигнатура>"` | процесса нет: сервис завершился вместе с сеансом; записать, какие файлы остались в каталоге экземпляра (`hyprland.lock`, `.socket2.sock`, `hyprland.log`) |
| Новый вход в Hyprland, затем `pgrep -af 'quietline-engine serve'` и `st` | один процесс с новым PID; состояние прошлого сеанса не подхвачено: только активные пространства мониторов как локальные `1`; `Super+1`…`Super+M` работают |
| Замена сервиса другого сеанса: `mkdir -p "$XDG_RUNTIME_DIR/hypr/smoke"; touch "$XDG_RUNTIME_DIR/hypr/smoke/hyprland.lock" "$XDG_RUNTIME_DIR/hypr/smoke/.socket2.sock"; HYPRLAND_INSTANCE_SIGNATURE=smoke quietline-engine serve &` | журнал нового: `replaced quietline-engine of another Hyprland session …`; прежний сервис завершился с `replaced by quietline-engine of another Hyprland session; stopping` |
| `rm "$XDG_RUNTIME_DIR/hypr/smoke/hyprland.lock"`, через 15 с `pgrep -af 'quietline-engine serve'`, затем `rm -r "$XDG_RUNTIME_DIR/hypr/smoke"; quietline-engine serve &` | сервис `smoke` завершился с `Hyprland instance smoke is gone (…/hyprland.lock no longer exists)`, код `1`; после запуска `st` и клавиши снова работают |

## Review Focus

**РФ1. Два одинаковых монитора без серийного номера.**

```sh
hyprctl -j monitors | jq -c '.[] | {name, make, model, serial}'
quietline-engine state | jq -r '.monitors[].key'          # KEY_A, KEY_B
quietline-engine switch 2 --monitor KEY_A
quietline-engine switch 2 --monitor KEY_B
quietline-engine state | jq -c '.workspaces[] | {monitor_key, number, workspace_id}'
```

Ожидается: ключи вида `connector:<разъём>` и различаются; у `KEY_A` и `KEY_B` разные `workspace_id` для номера `2`; `Super+1`/`Super+2` на каждом мониторе открывают только его пространства.

**РФ2. Активного окна нет, указатель на втором мониторе.** Закрыть все окна на обоих мониторах, увести указатель мышью на второй монитор, нажать `Super+1` (или `quietline-engine switch 1`), затем `st`. Ожидается: изменилось активное пространство только второго монитора, первый не тронут.

**РФ3. Окно закрывается во время перехода.** На пространстве в режиме «Окна» открыть два окна Ghostty и третье, которое закроется само:

```sh
ghostty -e sleep 3 &
/bin/sleep 2.9; quietline-engine toggle; echo $?
st; cl
quietline-engine toggle; echo $?
```

Ожидается одно из двух: переход подтверждён (`0`) — или `quietline-engine: mode switch failed: window 0x… closed during the switch` (код `1`), режим прежний, окна в прежнем состоянии. В обоих случаях следующий `toggle` отвечает за секунды. Отказ Hyprland посреди перехода в живом сеансе не вызвать — он проверен модульными тестами.

**РФ4. Клиент IPC оборвал чтение, перезапуск панели.**

```sh
socat - UNIX-CONNECT:"$XDG_RUNTIME_DIR/quietline/engine.sock"
{"id":1,"method":"subscribe"}
```

Ожидается: первая строка — `{"id": 1, "result": {...полное состояние...}}`; после `Super+2`, `Super+M` приходят строки `{"event": "state", "state": {...}}` с растущим `revision`; повтор одной и той же ошибки не присылается. Нажать `Ctrl+C` посреди потока событий, затем `st` и `Super+1`/`Super+M` — сервис и окна работают; новый `socat` с `subscribe` снова получает полный снимок. Отдельно — клиент, который не читает: `(echo '{"id":1,"method":"subscribe"}'; sleep 600) | socat - UNIX-CONNECT:"$XDG_RUNTIME_DIR/quietline/engine.sock" | (sleep 600)`; после десятков переключений `Super+1`/`Super+2` клавиши продолжают работать, в журнале сервиса строка `IPC client is not reading; disconnecting it`.

**РФ5. Монитор отключён и подключён с другим разрешением.** На втором мониторе открыть пространства `1` и `2` с плавающими окнами у правого и нижнего края. Отключить монитор (кабель, вывод VM или `hyprctl output remove QL-2`), затем `st`, `ws`, `cl`. Подключить снова с меньшим разрешением (другой режим монитора; в VM — меньший размер окна вьюера), затем `st`, `ws`, `cl`.

Ожидается: после отключения пространства второго монитора показаны на оставшемся (`display_monitor_key` = ключ оставшегося, `monitor_key` прежний), `Super+…` открывает их там; после подключения они вернулись на свой монитор, а плавающие окна целиком внутри его рабочей области (`at` и `at + size` в пределах `x … x + width/scale`, `y … y + height/scale` за вычетом `reserved`).

## Живые проверки команд Hyprland

`A`, `B`, `C` — адреса окон из `cl`; `ID` — `workspace_id` активного пространства из `st`.

**Ж1. Ответ `hyprctl eval`.**

```sh
hyprctl eval "hl.dispatch(hl.dsp.focus({ workspace = \"$ID\", on_current_monitor = true }))"
hyprctl eval 'hl.dispatch(hl.dsp.window.float({ action = "enable", window = "address:0xdeadbeef" }))'
```

Ожидается: первая печатает ровно `ok`, вторая — строку с `error`.

**Ж2. Порядок колонок при последовательном `float disable`.** На пространстве в режиме «Окна» три плавающих окна:

```sh
hyprctl eval 'hl.dispatch(hl.dsp.window.float({ action = "disable", window = "address:A" }))
hl.dispatch(hl.dsp.window.float({ action = "disable", window = "address:B" }))
hl.dispatch(hl.dsp.window.float({ action = "disable", window = "address:C" }))'
cl
```

Ожидается: `at[0]` растёт в порядке `A`, `B`, `C`. Если нет — записать фактический порядок (стоп-условие).

**Ж3. `colresize`.**

```sh
hyprctl eval 'hl.dispatch(hl.dsp.focus({ window = "address:A" }))
hl.dispatch(hl.dsp.layout("colresize 0.5"))'
hyprctl -j monitors | jq -c '.[] | {name, width, scale, reserved}'
cl
```

Ожидается: `size[0]` окна `A` ≈ `0.5 × (width / scale − reserved[0] − reserved[2])` с точностью до промежутков. Если нет — записать фактическое значение (стоп-условие).

**Ж4. Колонки при прокрученной ленте.** На пространстве в режиме «Тайлы» пять окон, у каждого `colresize 0.5` (как в Ж3), фокус на последнем — часть колонок за левым краем. Затем `Super+M` дважды и `cl` до и после.

Ожидается: порядок колонок по `at[0]` (в том числе отрицательным и за правым краем монитора) и их ширины после возврата в «Тайлы» те же, что до перехода.

**Ж5. Новое пространство на мониторе фокуса.** Фокус на первом мониторе:

```sh
hyprctl eval 'hl.dispatch(hl.dsp.focus({ workspace = "1050", on_current_monitor = true }))'
ws; st
```

Ожидается: пространство `1050` создано на первом мониторе, активное пространство второго не изменилось. То же через `quietline-engine switch 4`: новый ID ≥ 1001, второй монитор не тронут.

**Ж6. Отключение и возврат монитора.** Как в РФ5, плюс `ws` до отключения, после отключения и после подключения.

Ожидается: после отключения пространства второго монитора в `ws` числятся на оставшемся; после подключения сервис сам переносит их обратно (`workspace.move`), `ws` показывает их на втором мониторе без ручных команд. Если перенос отклонён — записать ответ `hyprctl eval` из журнала сервиса (стоп-условие).

**Ж7. Координаты `move`/`resize` на мониторе с масштабом ≠ 1.** Плавающее окно `A` на мониторе с масштабом `1.5`, `MX`, `MY` — его `x`, `y` из `hyprctl -j monitors`:

```sh
hyprctl eval "hl.dispatch(hl.dsp.window.move({ x = $((MX + 100)), y = $((MY + 100)), window = \"address:A\" }))
hl.dispatch(hl.dsp.window.resize({ x = 800, y = 600, window = \"address:A\" }))"
cl
```

Ожидается: `at` = `[MX + 100, MY + 100]`, `size` = `[800, 600]` — координаты глобальные, как `at` в `clients`, а не относительно монитора.

**Ж8. Формат событий.**

```sh
socat -u UNIX-CONNECT:"$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock" - \
  | grep -E '^(openwindow|closewindow|movewindow|monitoradded|monitorremoved|workspace)>>'
```

Открыть и закрыть окно, `Super+Shift+2`, `Super+2`, отключить и подключить монитор. Ожидается: строки `EVENT>>DATA` для каждого из шести событий.

## Результаты

| Поле | Значение |
|---|---|
| Версия Hyprland (`hyprctl version`) | не проверено |
| Дата | не проверено |
| Стенд (железо / VM, выходы, масштаб) | не проверено |

| Пункт | Результат |
|---|---|
| К. Клавиши и запуск | не проверено |
| П. Сервис и сокет | не проверено |
| РФ1. Одинаковые мониторы без серийного номера | не проверено |
| РФ2. Указатель на втором мониторе без активного окна | не проверено |
| РФ3. Окно закрылось во время перехода | не проверено |
| РФ4. Обрыв клиента IPC, повторная подписка | не проверено |
| РФ5. Отключение и подключение с другим разрешением | не проверено |
| Ж1. Ответ `hyprctl eval` | не проверено |
| Ж2. Порядок колонок при `float disable` | не проверено |
| Ж3. `colresize` | не проверено |
| Ж4. Колонки при прокрученной ленте | не проверено |
| Ж5. Новое пространство на мониторе фокуса | не проверено |
| Ж6. Отключение и возврат монитора | не проверено |
| Ж7. Координаты `move`/`resize` при масштабе ≠ 1 | не проверено |
| Ж8. Формат событий | не проверено |
