# Quietline

Quietline — личное рабочее окружение Linux поверх Hyprland: независимый для каждого рабочего пространства режим «Окна / Тайлы» (обычные плавающие окна или прокручиваемые колонки `scrolling`), собственная оболочка на Quickshell (панель, док, трей, поиск, буфер, быстрые настройки, уведомления) и установщик окружения поверх уже установленной системы. Источник идеи — Hyprstack; его интерфейсы и код можно брать по правилу о стороннем коде, нативный модуль не подключается.

> Общая проектная память для всех кодовых агентов (Claude Code, Codex/ChatGPT, DeepSeek и т.п.). Правки вносятся сюда; `CLAUDE.md` подключает файл через `@AGENTS.md` и содержит только специфику Claude Code.

## Текущее состояние

В репозитории спека, планы всех шести этапов, утверждённый макет и визуальный контракт `DESIGN.md`. Первый этап — движок пространств и окон на Python по плану `docs/superpowers/plans/2026-10-19-window-engine.md` — реализован: адаптер Hyprland, локальные пространства мониторов, режимы «Окна / Тайлы», сверка по событиям, диалоги по тегам, сервис с IPC и CLI, клавиши Hyprland. Второй этап — оболочка Quickshell по плану `docs/superpowers/plans/2026-10-19-quickshell.md` — перенесён на этот движок: верхняя панель, док, трей, показатели, `Super+Space`, CLI `quietline-shell`. Третий этап — системные панели по плану `docs/superpowers/plans/2026-10-20-system-panels.md` — перенесён на новую оболочку: сетевая панель с профилями объекта и откатом, быстрые настройки, окно «Настройки». Четвёртый этап — ежедневные действия по плану `docs/superpowers/plans/2026-10-28-daily-actions.md`: блокировка и меню питания, корректный выход из приложений, уведомления, снимки экрана, история буфера, поиск, клавиши окон. Пятый этап — языки и регион и установщик по спеке `docs/superpowers/specs/2026-10-28-language-and-installer-design.md`: часть «Языки и регион» (план `docs/superpowers/plans/2026-10-28-language-region.md`) написана — оболочка и уведомления на русском и английском, раздел «Язык и регион», раскладки `us,ru`, док и памятка без неустановленных программ; установщик (план `docs/superpowers/plans/2026-10-28-installer.md`) написан — `./install.sh` с выбором языков, каталогом программ, снимком корня Btrfs, продолжением и откатом, гайд установки Arch на Btrfs `docs/install/2026-10-20-arch-install.md`. Шестой этап — простой и сон, индикатор, заряд и центр уведомлений по спеке `docs/superpowers/specs/2026-10-30-idle-osd-notifications-design.md` и плану `docs/superpowers/plans/2026-10-30-idle-osd-notifications.md` — написан: автоблокировка и сон через hypridle, «Не засыпать», клавиши громкости и яркости с индикатором, предупреждения о заряде, история уведомлений и «Не беспокоить»; заимствования из Hyprstack — в `THIRD_PARTY.md`. Новый вид оболочки — вариант B по спеке `docs/superpowers/specs/2026-11-01-shell-redesign-design.md` и плану `docs/superpowers/plans/2026-11-01-shell-redesign.md`: тонкая панель с меню Quietline, пункт управления, прячущийся док, поиск и буфер по центру, уведомления с календарём, «Настройки» с группами, заголовки окон hyprbars через `hyprpm`, оформление окон Hyprland. Живые проверки не проведены — список в `docs/backlog.md`, порядок проверки — `scripts/smoke-window-engine.md`, `scripts/smoke-quickshell.md`, `scripts/smoke-system-panels.md`, `scripts/smoke-daily-actions.md`, `scripts/smoke-language.md`, `scripts/smoke-installer.md`, `scripts/smoke-idle-notifications.md`, `scripts/smoke-shell-redesign.md`.

## Базовая система и минимальные версии

Quietline ставится поверх **Arch Linux** после Archinstall Minimal. Hyprland и Quickshell берутся из официального репозитория Arch `extra`; источники остальных приложений — таблица «Приложения и инструменты» в спеке.

| Компонент | Минимум | Что требует этой версии |
|---|---|---|
| Hyprland | 0.55 | Lua-конфиг и Lua API (с 0.55), встроенная раскладка `scrolling` (с 0.54) |
| Quickshell | 0.3.2 | формат адресов пространств актуального Hyprland |

- Код и конфигурация не используют возможности новее минимума. Если они нужны — минимум поднимается в этой таблице и `README.md` в том же коммите.
- Документацию читать для минимальной версии: у вики Hyprland есть переключатель версии, документация Quickshell — `https://quickshell.org/docs/v0.3.2/`. Последняя документация может описывать возможности новее минимума, а API и параметры раскладок меняются между минорными выпусками.
- Пакеты из AUR — только для приложений, перечисленных в спеке; Hyprland, Quickshell и их зависимости из AUR и `-git`-пакетов не ставятся.

## Куда смотреть по задаче

| Когда | Что прочитать |
|---|---|
| Любая задача по поведению окружения | `docs/superpowers/specs/2026-10-19-quietline-desktop-design.md` — что делает Quietline и критерии готовности первой версии |
| Движок пространств и окон | `docs/superpowers/plans/2026-10-19-window-engine.md` — файловая карта, контракт IPC, шаги и проверки |
| Оболочка Quickshell (панель, док, `quietline-shell`) | `docs/superpowers/plans/2026-10-19-quickshell.md` — границы, перенос на новый движок, файлы и проверки; `DESIGN.md` — внешний вид |
| Системные панели (сеть, звук, яркость, Bluetooth, питание, окно «Настройки») | `docs/superpowers/plans/2026-10-20-system-panels.md` — границы, контракт `quietline-shell network`, перенос, Review Focus |
| Ежедневные действия (блокировка, меню питания, выход из приложений, уведомления, снимки, буфер, поиск, клавиши окон) | `docs/superpowers/plans/2026-10-28-daily-actions.md` — решения, контракт подкоманд `quietline-shell`, Review Focus |
| Языки и регион (язык оболочки, «Язык и регион», раскладки, док без неустановленных программ) | `docs/superpowers/plans/2026-10-28-language-region.md` — таблицы строк, `quietline-shell region`, раскладки; `docs/superpowers/specs/2026-10-28-language-and-installer-design.md` — часть 1 |
| Установщик (`./install.sh`, каталог программ, снимок и откат, гайд установки Arch) | `docs/superpowers/plans/2026-10-28-installer.md` — решения, каталог, команды снимка и отката, Review Focus; `docs/superpowers/specs/2026-10-28-language-and-installer-design.md` — часть 2; `docs/install/` — гайд и обновление |
| Простой и сон, «Не засыпать», клавиши громкости и яркости с индикатором, предупреждения о заряде, центр уведомлений и «Не беспокоить» | `docs/superpowers/plans/2026-10-30-idle-osd-notifications.md` — интерфейсы, Review Focus, решения; `docs/superpowers/specs/2026-10-30-idle-osd-notifications-design.md` — поведение и почему; `THIRD_PARTY.md` — что взято из Hyprstack |
| Внешний вид панели, дока, всплывающих окон, заголовков окон, светлая тема и указатель | `docs/superpowers/specs/2026-11-01-shell-redesign-design.md` и план `docs/superpowers/plans/2026-11-01-shell-redesign.md` — вариант B; `docs/superpowers/specs/2026-11-02-appearance-design.md` — светлая тема и выбор указателя; `docs/superpowers/specs/2026-11-02-top-bar-design.md` — значки и окна верхней панели; `docs/design/quiet-line-b.html` и `quiet-line-b-light.html` — утверждённые макеты; `DESIGN.md` — токены и размеры. `DESIGN.md` — стартовая точка, а не жёсткий контракт: внешний вид оценивается вживую и по отзыву пользователя, после правки `DESIGN.md` обновляется под новое состояние |
| Задача с активной спекой или планом | `docs/superpowers/specs` и `plans` — статус в шапке файла; читать только относящиеся к задаче |
| Устройство репозитория для человека | `README.md` |
| Что изменилось для пользователя окружения | `CHANGELOG.md` |

## Layout

```
docs/backlog.md           — что не подтверждено в живом сеансе и где это проверить
docs/install/             — гайд установки Arch на этот ноутбук (Btrfs, `/efi`) и обновление по источникам
docs/design/              — утверждённые визуальные макеты (HTML)
docs/superpowers/specs/   — спеки: что строим и почему
docs/superpowers/plans/   — планы реализации по шагам
config/hyprland/          — Lua-конфигурация Hyprland: раскладка, запуск сервиса и оболочки, клавиши, теги диалогов
config/fish/              — `quietline-locale.fish`: сообщения программ в терминале fish остаются английскими
config/polkit/            — правило polkit для сетевых профилей и отката NetworkManager
config/hypridle/          — `hypridle.conf`: блокировка, отключение экрана и сон по простою, блокировка перед сном
config/fontconfig/        — `50-quietline-titlebar.conf`: шрифт заголовков окон «Quietline Titlebar» (Inter и значки Material Symbols)
scripts/                  — сценарии проверки в живом сеансе (`smoke-window-engine.md`, `smoke-quickshell.md`, `smoke-system-panels.md`, `smoke-daily-actions.md`, `smoke-language.md`, `smoke-installer.md`, `smoke-idle-notifications.md`, `smoke-shell-redesign.md`), запуск оболочки из репозитория `run-shell`, проверка имён пакетов каталога `check-catalog.py`
shell/quietline/          — конфигурация Quickshell (`qs -c quietline`): `shell.qml`, тема `Theme.qml`, стенд IPC `IpcHarness.qml`
shell/quietline/controls/ — общие элементы: значок Material Symbols, кнопка, сегменты, пункт меню, полоса прокрутки, группа и строка настроек
shell/quietline/surfaces/ — поверхности: всплывающее окно, диалог по центру, подсказка
shell/quietline/inputs/   — поля форм: текстовое поле, переключатель, ползунок
shell/quietline/bar/      — верхняя панель `TopBar.qml`
shell/quietline/dock/     — док `Dock.qml`
shell/quietline/services/ — клиент IPC движка, окна и приложения, показатели панели
shell/quietline/system/   — сервисы оборудования: сеть, звук, яркость, Bluetooth, питание
shell/quietline/panels/   — компоненты управления системой и быстрые настройки (общие для всплывающих панелей и окна «Настройки»)
shell/quietline/settings/ — окно «Настройки»
shell/quietline/session/  — меню кнопки питания и действия сеанса
shell/quietline/notifications/ — сервер уведомлений и история сеанса, всплывающие карточки, центр уведомлений
shell/quietline/osd/      — индикатор громкости, микрофона, яркости и раскладки
shell/quietline/clipboard/ — история буфера `Super+V`
shell/quietline/search/   — поиск `Super+Space`: приложения, файлы, действия, вычисления
shell/quietline/lock/     — поверхность экрана блокировки; корень его отдельного процесса — `shell/quietline/LockScreen.qml` (`qs -p …/LockScreen.qml`)
shell/quietline/Lang.qml  — синглтон языка: читает `quietline-shell region` и отдаёт таблицу строк `Lang.s`
shell/quietline/Appearance.qml — синглтон оформления: тема и указатель из `quietline-shell appearance`; по нему `Theme.qml` отдаёт цвета тёмной или светлой темы
shell/quietline/logic/    — чистые функции `Models.js` и таблицы строк `Strings.js` на русском и английском (общие для QML и тестов Node)
src/quietline_engine/     — Python-пакет движка пространств и окон
src/quietline_shell/      — Python-пакет `quietline-shell`: закрепления дока, ограничение анимаций, NetworkManager, «О системе», сеанс, снимки экрана, история буфера, поиск файлов
src/quietline_install/    — установщик (`./install.sh` → `python -m quietline_install`, в wheel не входит): ядро шагов и журнал изменений `runner.py`, экраны и тексты, каталог, снимок и откат, шаги в `steps/`
tests/engine/             — модульные тесты движка (pytest, без Hyprland)
tests/helper/             — тесты `quietline-shell` (pytest, без NetworkManager и Hyprland)
tests/shell/              — тесты моделей оболочки (`node --test`), правила polkit и контракта протокола движка
tests/install/            — тесты установщика (pytest, поддельная система: без pacman, btrfs, sudo и сети)
pyproject.toml            — пакет `quietline-engine` (CLI `quietline-engine` и `quietline-shell`), Python ≥ 3.14, тестовая зависимость pytest
install.sh                — вход установщика: шрифт консоли, проверки Arch, не-root и Python ≥ 3.14
installer/                — каталог программ `catalog.toml` и шаблоны файлов `files/`
packaging/arch/           — PKGBUILD локального пакета `quietline` из клона
.github/workflows/        — CI: pytest, тесты моделей оболочки, имена пакетов каталога в контейнере Arch
DESIGN.md                 — визуальный контракт оболочки; runtime-токены — `shell/quietline/Theme.qml`
LICENSE                   — GPL-3.0
THIRD_PARTY.md            — заимствованный сторонний код: источник, лицензия, что изменено
```

## Разработка и проверки

- Работа ведётся на macOS, окружение запускается только на Linux. Модульные тесты движка работают без Hyprland через поддельный адаптер и гоняются локально; живые проверки (Hyprland, мониторы, Quickshell, установщик) возможны только на Linux-машине.
- Непроведённая живая проверка не считается пройденной: агент прямо пишет, что не проверено, и заносит пункт в `docs/backlog.md`.
- Тесты: `uv run --python 3.14 pytest` (на macOS системный Python не используется; зависимости ставятся из `pyproject.toml`). Один файл — `uv run --python 3.14 pytest tests/engine/test_hyprland.py -v`.
- Тесты моделей оболочки: `node --test 'tests/shell/*.test.cjs'` (Node ≥ 22; шаблон в кавычках разворачивает сам Node, каталог аргументом не принимается). QML без Quickshell не запускается — проверяется только в живом сеансе.
- Оболочка: ссылка `ln -s "$PWD/shell/quietline" ~/.config/quickshell/quietline`, затем `qs -c quietline`; из репозитория без ссылки — `scripts/run-shell`. Состояние — `qs -c quietline ipc call quietline status`. Нужны Quickshell, шрифты IBM Plex Sans/Mono и JetBrainsMono Nerd Font Propo (пакет `ttf-jetbrains-mono-nerd`), `quietline-shell` в `PATH`.
- Сервис и CLI движка: `quietline-engine serve` (в сеансе Hyprland; журнал — в stderr), клиентские команды `quietline-engine switch N [--monitor KEY]`, `move N`, `toggle [--monitor KEY]`, `state`. Из репозитория без установки — `uv run --python 3.14 quietline-engine …`. Протокол сокета `$XDG_RUNTIME_DIR/quietline/engine.sock` и коды ошибок — в docstring `src/quietline_engine/server.py`.
- Установщик: `./install.sh` (экраны), `./install.sh --dry-run`, `status`, `check`, `rollback`, `update`, `--from ID`; состояние и журнал — `~/.local/state/quietline/install.json` и `install.log`. Тесты — `uv run --python 3.14 pytest tests/install`. Запускать установщик на машине разработчика нельзя: он меняет систему.
- Настройки оболочки: `quietline-shell pins [--set JSON] [--path PATH]`, `motion`, `about`, `lock`, `session logout|reboot|poweroff`, `app quit|kill`, `screenshot output|region`, `clipboard ACTION`, `files QUERY|--update`, `idle suspend`, `network ACTION`, `region [--set JSON] [--path PATH]`, `display [--set JSON] [--path PATH]`, `appearance [--set JSON] [--path PATH]` — одна строка JSON в stdout, ошибка — `{"error": …}` и код 1 (docstring `src/quietline_shell/__main__.py`; подкоманды `network` — docstring `src/quietline_shell/network.py`). Закрепления дока — `$XDG_CONFIG_HOME/quietline/pins.json`, недавние сетевые профили — `$XDG_CONFIG_HOME/quietline/network.json`, язык, форматы и раскладки — `$XDG_CONFIG_HOME/quietline/region.json` (при записи `region` обновляет также `$XDG_CONFIG_HOME/locale.conf` и `quietline/keyboard.lua`), масштаб мониторов — `$XDG_CONFIG_HOME/quietline/display.json` и рядом `display.lua` для конфигурации Hyprland, тема, указатель и процент батареи на панели — `$XDG_CONFIG_HOME/quietline/appearance.json` и рядом `appearance.lua` (при записи `appearance` меняет `color-scheme` и `gtk-theme` в gsettings, вызывает `hyprctl reload config-only` и `hyprctl setcursor`).

## Общие конвенции

- **Язык: комментарии — по-русски, вывод в консоль — по-английски.** Комментарии и docstring — по-русски, в том числе в shell-скриптах, Lua- и QML-файлах (коротко и по делу). Всё, что видит пользователь в консоли и журналах (`echo`, сообщения CLI, ошибки установщика), — на простом английском. Документация в `docs/`, `README.md`, `CHANGELOG.md` и сообщения коммитов — по-русски. Исключение — экраны установщика: они на языке, выбранном в его первом экране; журнал установщика и вывод `install.sh` до выбора языка — по-английски.
- **Видимые тексты — на двух языках.** Тексты оболочки и уведомлений `quietline-shell` задаются таблицами строк на русском и английском (`shell/quietline/logic/Strings.js` через `Lang.s`, `NOTIFICATION_TEXTS` в `src/quietline_shell/config.py`) с одинаковыми ключами. Кириллица в строковых литералах QML и `Models.js` запрещена тестом `tests/shell/strings.test.cjs`; новый текст добавляется в обе таблицы.
- **Комментарии описывают только то, что код делает сейчас**: назначение, контракт, инвариант, наблюдаемое поведение. Никакой истории — ни исправленных багов, ни ссылок на обсуждение, ни отклонённых альтернатив, ни «почему так, а не иначе» (это в спеку или план).
- **Папка держит либо файлы, либо папки.** Когда записей больше восьми, папка делится по смыслу. Пустые папки ради сортировки не создаются; общих `helpers`/`utils` нет. Исключения — корень репозитория, `docs/` (держит `backlog.md` рядом с папками), корень конфигурации Quickshell `shell/quietline/` (Quickshell требует `shell.qml` в корне конфигурации; рядом лежат тема, `qmldir`, папки компонентов и корень процесса блокировки `LockScreen.qml`: синглтоны видны только процессу, чей корень — эта папка) и хронологические реестры `docs/superpowers/specs`, `docs/superpowers/plans`.
- **Секреты в репозиторий не попадают**: SSH-ключи, пароли Wi-Fi и удалённых соединений, настройки VPN, токены. Профили и примеры конфигураций — без значений секретов.
- **Сторонний код — по лицензии.** Код, интерфейсы и конфигурацию других проектов (в том числе Hyprstack и Caelestia shell) можно брать и менять, если их лицензия совместима с GPL-3.0 (GPL-3.0, LGPL-3.0, Apache-2.0, MIT, BSD и т.п.). В том же коммите заимствование записывается в `THIRD_PARTY.md` в корне (создаётся с первым заимствованием): компонент, источник с коммитом или версией, лицензия, что изменено и дата; текст лицензии источника, если она не GPL-3.0, кладётся рядом. Код без лицензии или с несовместимой лицензией не копируется — только идеи.

## README и CHANGELOG

- **`README.md`** описывает репозиторий как он есть сейчас: что это, статус, структура, где документация, порядок этапов. Обновляется в том же коммите, что меняет одно из этого (новая папка верхнего уровня, завершённый этап, смена минимальных версий). Планов и обещаний сверх утверждённых спек в нём нет.
- **`CHANGELOG.md`** — для пользователя окружения, формат [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/). Запись добавляется в `## [Unreleased]` **в том же коммите**, что меняет наблюдаемое поведение: сочетания клавиш, режимы окон, элементы оболочки, установка, конфигурация, CLI и IPC движка. Пишется результатом для пользователя, а не пересказом diff. Не попадают: рефакторинг без изменения поведения, тесты, правки процесса агентов.
- Разделы записи — `Added`, `Changed`, `Fixed`, `Removed`; до 1.0 несовместимое изменение (сочетание, формат конфигурации, протокол IPC) идёт в раздел **Breaking** с рецептом «было → стало».
- Версии — SemVer 0.x. Выпуск — раздел `## [<версия>] — <дата>` из накопленного `Unreleased` и аннотированный тег `v<версия>` на этом коммите. Выпуски делаются только по просьбе пользователя.

## Git & Superpowers workflow

Один разработчик — pull request'ы не используются, не создавать их ни через `gh`, ни на github.com. Это относится к любому агенту, ведущему задачу в этом репозитории.

### Когда включать Superpowers

Плагин Superpowers (`brainstorming`, `writing-plans`, `executing-plans`, `subagent-driven-development`, `systematic-debugging`, `test-driven-development`, `requesting-code-review` и т.д.) не включается автоматически на каждую задачу — это правило переопределяет дефолт скилла `using-superpowers` («вызывай при малейшей вероятности»):

- **Крупная или архитектурная задача** (новый компонент окружения, смена контракта IPC, источника пакетов или минимальных версий): перед вызовом плагина агент спрашивает пользователя, задействовать ли Superpowers. Без одобрения — работает без плагина, но спека/план в `docs/superpowers/{specs,plans}` всё равно пишутся, если масштаб их требует.
- **Повседневная или простая задача** (точечный фикс, правка в 2–3 файла, документация): Superpowers не вызывается вовсе.

### Роли агентов

Роль определяется этапом задачи, а не моделью или харнессом. Один агент может пройти несколько ролей подряд.

- **Planner** — исследует код, спеку и документацию компонентов (Hyprland, Quickshell, NetworkManager), готовит спеку и план. Не начинает реализацию, пока решения не зафиксированы в репозитории.
- **Executor** — реализует утверждённый план по шагам и отмечает их в плане. Если план разошёлся с реальностью (например, установленный Hyprland не даёт нужной команды) — остановиться и сначала поправить спеку/план.
- **Reviewer** — независимо сверяет результат со спекой, планом, этим файлом, diff и результатами проверок. Чужое «тесты прошли» проверкой не считается — Reviewer запускает их сам.

### Передача задачи между агентами

Источник истины — состояние репозитория, а не память предыдущего чата. Новый агент перед работой:

1. Читает этот `AGENTS.md`.
2. Читает только относящиеся к задаче спеки и планы (статус — в шапке файла).
3. Проверяет `git status`, `git worktree list`, текущую ветку и последние коммиты.
4. Сверяет план с текущим кодом, а не предполагает, что предыдущий агент оставил репозиторий в ожидаемом состоянии.

Решения, ограничения и отклонения фиксируются в спеке, плане или этом файле — не только в сообщении чата.

### Цикл: спека → план → выполнение → ревью

1. **Спека** — `docs/superpowers/specs/<дата>-<название>-design.md`: проблема, границы, выбранное решение и почему.
2. **План** — `docs/superpowers/plans/<дата>-<название>.md`: цель, границы, карта файлов, шаги и проверки. Спека и план коммитятся до реализации; план отмечается по ходу.
3. **Выполнение** — по шагам, коммит на логический шаг, каждый оставляет тесты зелёными.
4. **Ревью и verification** — с запуском проверок; непроведённые живые проверки — в `docs/backlog.md`.
5. **Завершение** — когда этап слит и проверен, его план удаляется (история остаётся в git). Спека, описывающая действующее поведение окружения, остаётся с этим статусом в шапке.

### Git-цикл

1. Новая ветка `feature/<название>` от свежего `main`. Не коммитить напрямую в `main`.
2. Worktree разрешён только для выполнения плана и только внутри `.worktrees/` (папка в `.gitignore`): `git worktree add .worktrees/<название> -b feature/<название> main`. Одна задача — один worktree.
3. Спека/план, если нужны, коммитятся до реализации; дальше — коммиты по логическим шагам.
4. После ревью — `git switch main && git merge feature/<название>` (fast-forward; если не выходит — `--no-ff`).
5. Уборка: `git worktree remove .worktrees/<название>`, если был; `git branch -d feature/<название>`.
6. `git push origin main`.

### Commit messages

Формат: `<type>(<scope>): <описание на русском языке>`

- Префикс типа — латиницей, как в Conventional Commits: `feat`, `fix`, `chore`, `refactor`, `docs`, `test`, `perf`, `build`, `ci`, `style`, `revert`.
- Scope — опционально, латиницей: `engine`, `shell`, `hyprland`, `installer`, `design`, `agents`.
- Всё после `:` — **только на русском**, тело тоже. Стиль — факт совершённого действия («добавлен», «устранена»). Заголовок — одна строка, один факт.
- Тело — только когда без него непонятно, зачем правка. В теле нет результатов проверок, пересказа diff и отметок о шагах плана.

```text
feat(engine): добавлен адаптер Hyprland
fix(engine): устранено смешение пространств двух одинаковых мониторов
docs(agents): описан порядок ведения CHANGELOG
```

Коммиты до 2026-10-26 и примеры сообщений в плане движка — на английском; новые пишутся по правилу выше.

## Do not

- **Не трогать разметку дисков и загрузчик.** Ни команд, ни скриптов, меняющих разделы, EFI или GRUB на машине пользователя; установщик окружения этого тоже не делает.
- **Не копировать код без лицензии или с лицензией, несовместимой с GPL-3.0** — правило о стороннем коде в «Общих конвенциях».
- **Не подключать нативный модуль Hyprstack**: он привязывает обновления к ABI Hyprland. Единственный нативный плагин Quietline — hyprbars через `hyprpm` из форка `quietline-desktop/hyprland-plugins` (решения пользователя 2026-11-01 и 2026-11-02: форк добавляет кнопкам цвета под указателем, плавный переход и центровку значков); новые плагины — только с согласия пользователя.
- **Не создавать pull request'ы** — ни в этом репозитории, ни в форке, ни в hyprwm.

## Gotchas

- **Hyprland меняет API между выпусками.** Перед использованием команды `hyprctl`, Lua API или свойства `scrolling` проверять, что они есть в минимальной версии из таблицы выше; несовместимость — стоп-условие плана, а не повод для обходного хака.
- **hyprbars пересобирается под каждый Hyprland.** После обновления Hyprland плагин не грузится до `hyprpm update`; конфигурация Quietline настраивает его только под проверкой `hl.plugin and hl.plugin.hyprbars` и без него работает.
- **Форк hyprland-plugins догоняет апстрим.** `quietline-desktop/hyprland-plugins` — `main` апстрима и поверх него коммиты Quietline. После выпуска Hyprland, под который hyprwm поправил плагины, форк перебазируется на `hyprwm/main` (порядок — `docs/install/updating.md`), иначе `hyprpm update` не соберёт hyprbars. Правки форка в hyprwm не отправляются: политика hyprwm запрещает PR с кодом, написанным ИИ, без полного понимания автором.
- **Не амендь коммит, от которого уже ответвлена другая ветка.** `--amend` меняет хеш, и merge затянет оба коммита.

---

Файл обновляется при изменении команд, добавлении папок или смене конвенций и инвариантов — не при смене статуса задач (для этого шапки спек и планов).
