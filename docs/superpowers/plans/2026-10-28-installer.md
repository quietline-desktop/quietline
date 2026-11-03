# Установщик Quietline — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Статус:** выполнен, ждёт живой проверки (ветка `feature/installer-v2`): `./install.sh`, каталог, снимок и откат, гайд — `scripts/smoke-installer.md`, `docs/backlog.md`.

**Goal:** `./install.sh` на Arch после archinstall (Minimal, корень на Btrfs) спрашивает язык установщика и язык системы, даёт выбрать программы из каталога, делает снимок корня, ставит окружение Quietline и при падении предлагает «Продолжить» или «Откатить».

**Architecture:**
- `install.sh` включает консольный шрифт с кириллицей, проверяет Arch, не-root, Python ≥ 3.14 и запускает `python -m quietline_install` из клона (`PYTHONPATH=src`). Пакет установщика в wheel не входит.
- Сначала текстовые экраны (curses, стандартная библиотека): язык установщика → проверки → язык системы → каталог → сводка. Экраны — тонкий слой над чистыми моделями, модели покрыты тестами.
- Затем упорядоченные шаги с проверкой «уже сделано» (`check`) и действием (`run`), как в старой ветке. Состояние, выбор и журнал изменений — в `~/.local/state/quietline/install.json` (в `@home`, переживает откат корня); журнал команд — английский, без секретов.
- Перед первым изменяющим шагом — снимок `@` только для чтения в `@snapshots/quietline-pre-<время>` и пункт в меню GRUB через `grub-btrfs` с хуком `grub-btrfs-overlayfs`. Откат подменяет `@` копией снимка и возвращает файлы в `~` из копий. Без Btrfs — откат по журналу изменений.
- Quietline ставится локальным pacman-пакетом `quietline` из клона (PKGBUILD); язык, раскладки и закрепления пишутся тем же `quietline-shell region|pins --set`, что и в оболочке.

**Tech Stack:** Python 3.14 (стандартная библиотека: `curses`, `tomllib`, `subprocess`, `json`), pytest, POSIX sh, pacman/makepkg, Flatpak, btrfs-progs, grub-btrfs, mkinitcpio, systemd, greetd + tuigreet, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-28-language-and-installer-design.md` — «Часть 2. Установщик»; основная спека `docs/superpowers/specs/2026-10-19-quietline-desktop-design.md` («Установка на текущем компьютере», «Приложения и инструменты», «Ошибки, проверка и готовность»). Источник кода и решений — `origin/feature/installer` (смотреть через `git show origin/feature/installer:<путь>`), не основа для слияния.

**Основа:** `main` с этапами 1–4 и частью 1 этапа 5 («Языки и регион»). Ветка — `feature/installer-v2` (имя `feature/installer` занято старой веткой на `origin`).

## Решения плана

Принятые при планировании (по исследованию источников 2026-10-28); спека оставляла их сборщику:

1. **Источники каталога** — таблица в Task 3. Brave и ONLYOFFICE — Flathub (verified); Slack — AUR `slack-desktop`, WeChat — AUR `wechat-bin` (оба скачивают выпуск разработчика; на Flathub не verified); AUR `wechat` (обёртка-песочница) не используется.
2. **Node.js — всегда через `fnm`** (extra): по умолчанию `fnm install --lts` и он же по умолчанию; в «Расширенных» — дополнительные мажорные версии. Системный `nodejs*` не ставится, чтобы не было двух Node. `pnpm` — пакет Arch.
3. **.NET** — по умолчанию `dotnet-sdk aspnet-runtime aspnet-targeting-pack` (последний, 10); в «Расширенных» — `dotnet-sdk-8.0`+`aspnet-runtime-8.0`, `dotnet-sdk-9.0`+`aspnet-runtime-9.0`. 6.0 не предлагается (закончилась поддержка).
4. **Python** — системный `python`, `python-pip`, `uv`; дополнительные версии — `uv python install 3.12|3.13`.
5. **Снимки без snapper:** `btrfs subvolume snapshot -r` в неподключённый подтом `@snapshots` верхнего уровня; `grub-btrfs` (extra) без демона, `grub-mkconfig` после снимка. Если хук overlayfs недоступен (в `HOOKS` есть `systemd`) — снимок без `-r`.
6. **Подключение конфигурации Hyprland** — `dofile("/usr/share/quietline/hyprland/quietline.lua")` (работало в старой ветке на Hyprland 0.56); шапка `quietline.lua` меняется с `require("quietline")` на эту строку. Чужой `hyprland.lua` (в том числе пример Hyprland с `SUPER+M` → выход) заменяется шаблоном Quietline с копией; файл, где строка уже есть, не трогается.
7. **Английские домашние папки:** нет `~/.config/user-dirs.dirs` — установщик пишет английские пути и создаёт каталоги; файл уже есть (в том числе с русскими путями) — папки с данными не переносятся и не переименовываются, путь называется в итоге. `~/.config/user-dirs.conf` с `enabled=False` пишется всегда.
8. **Консольный шрифт** — `setfont cyr-sun16` (пакет `kbd`, есть в базовой системе) в `install.sh`, если запущен в виртуальной консоли (`TERM=linux`).
9. **Пакеты Arch** — один `sudo pacman -Syu` после снимка, дальше только `pacman -S --needed` (без `-y`, без частичных обновлений). Подготовка снимка ставит `grub-btrfs` через `pacman -S --needed` без `-y`.
10. **Тесты установщика** — `tests/install/`, файлы с префиксом `test_install_*` (в `tests/helper/` уже есть `test_session.py`; `__init__.py` в тестах не используются).
11. **CI** — `.github/workflows/tests.yml`: pytest (Python 3.14 через uv), `node --test 'tests/shell/*.test.cjs'`, проверка имён пакетов каталога в контейнере `archlinux:latest`; триггер — только `push`.

## Global Constraints

- Установщик не создаёт, не удаляет и не форматирует разделы: в коде и `install.sh` нет `parted`, `sfdisk`, `fdisk`, `mkfs`, `wipefs`, `sgdisk`, `grub-install`, `bootctl`, `efibootmgr`; `btrfs` вызывается только для снимков (`subvolume snapshot|create|list|show`) и отката (`subvolume snapshot`, `mv` подтома). Проверяется тестом.
- Минимальные версии — Hyprland 0.55, Quickshell 0.3.2; Hyprland, Quickshell и их зависимости — только из `extra`, не из AUR и не `-git`.
- Источник программы: репозиторий Arch → Flathub только verified → AUR только с выпуском разработчика; Chrome, VS Code, 1Password — AUR всегда. Инструкции AUR показываются и подтверждаются перед сборкой.
- Экраны установщика — на выбранном языке установщика (ru/en); журнал `install.log`, тексты ошибок в журнале и вывод `install.sh` до выбора языка — английские.
- Пароль `sudo` вводит пользователь в терминале; секреты в журнал и репозиторий не попадают (`redact`).
- Повторный запуск продолжает с упавшего шага, не повторяет готовые и не плодит одинаковые копии; копия заменяемого файла — `<файл>.quietline-<YYYYmmdd-HHMMSS>`.
- Закрепления дока пишутся только при первой установке (нет `pins.json`); повторный запуск только добавляет программы, ничего не удаляет.
- Состояние установщика — `$XDG_STATE_HOME/quietline/install.json` (по умолчанию `~/.local/state/quietline/`), журнал — `install.log` там же, права 0600.
- Папка держит не больше восьми записей: пакет `src/quietline_install/` — 7 модулей и подпакет `steps/`.
- Комментарии и docstring — по-русски; тесты без настоящих `pacman`, `btrfs`, `sudo`, сети — через поддельный `System`. Живые проверки — `scripts/smoke-installer.md` и `docs/backlog.md`.

## Review Focus

1. **Обрыв посреди установки (сеть во время pacman, отказ от PKGBUILD, Ctrl+C):** повторный `./install.sh` показывает «Продолжить / Откатить», готовые шаги не повторяются, выбор программ и языки берутся из состояния. Тесты `test_resume_starts_at_failed_step`, `test_rerun_offers_continue_or_rollback`.
2. **Корень не на Btrfs, `@` не корень, `/boot` на отдельном разделе, в `HOOKS` есть `systemd`, загружен снимок (overlay):** установщик называет причину и либо предупреждает о неполном откате и ждёт согласия, либо меняет вид снимка, но не делает снимок, который не восстановит ядро. Тест `test_snapshot_plan_follows_root_layout` (параметризованный).
3. **Откат после частичной установки:** на Btrfs подменяется `@`, из `fstab` нового `@` убирается `subvolid=` у строки `/`, файлы в `~` возвращаются из копий, созданные файлы удаляются; без Btrfs удаляются только поставленные установщиком пакеты (не бывшие до него). Тесты `test_btrfs_rollback_commands`, `test_journal_rollback_keeps_preexisting_packages`.
4. **Пользовательские конфиги уже есть** (`hyprland.lua` с примером Hyprland, свой `config.fish`, `pins.json`, `user-dirs.dirs` с русскими путями): копия, свои данные не теряются, `pins.json` не перезаписывается, папки с данными не переименовываются. Тесты `test_example_hyprland_config_is_replaced_with_backup`, `test_existing_pins_are_not_overwritten`, `test_existing_user_dirs_are_left_as_is`.
5. **Программа каталога пропала из репозитория или переименована:** установка останавливается до любых изменений и называет пакет. Тест `test_missing_package_stops_before_install` и проверка каталога в CI.

---

## Файлы

```
install.sh                                 — вход: шрифт, проверки, запуск пакета
installer/catalog.toml                     — каталог: основа, разделы, варианты, источники, desktop ID
installer/files/                           — шаблоны: hyprland.lua, quietline.fish, greetd-config.toml, user-dirs.dirs, user-dirs.conf
packaging/arch/PKGBUILD                    — локальный пакет quietline
src/quietline_install/__init__.py
src/quietline_install/__main__.py          — CLI: run (по умолчанию), status, check, rollback, update
src/quietline_install/runner.py            — Step, Ctx, Runner, System, StepFailed, состояние, журнал изменений, redact
src/quietline_install/texts.py             — строки экранов ru/en
src/quietline_install/screens.py           — модели экранов и их отрисовка curses
src/quietline_install/catalog.py           — загрузка и проверка каталога, выбор, пакеты выбора, закрепления
src/quietline_install/snapshot.py          — проверка корня, подготовка grub-btrfs, снимок, откат
src/quietline_install/steps/__init__.py    — упорядоченный список шагов для выбора
src/quietline_install/steps/packages.py    — pacman, графика, локали, службы, Flatpak, версии .NET/Node/Python
src/quietline_install/steps/aur.py         — сборка AUR с показом инструкций
src/quietline_install/steps/configs.py     — пакет quietline, файлы пользователя, язык, закрепления, папки
src/quietline_install/steps/session.py     — greetd, fish по умолчанию, группа docker, ручные шаги
src/quietline_install/steps/checks.py      — проверка готовности
scripts/check-catalog.py                   — все имена пакетов каталога есть в репозиториях (CI)
tests/install/conftest.py, tests/install/test_install_*.py
.github/workflows/tests.yml
docs/install/2026-10-20-arch-install.md, docs/install/updating.md, scripts/smoke-installer.md
```

---

### Task 1: Ядро — шаги, состояние, журнал изменений, команды

**Files:**
- Create: `src/quietline_install/__init__.py`, `runner.py`, `tests/install/conftest.py`, `tests/install/test_install_runner.py`
- Источник: `origin/feature/installer:src/quietline_install/{steps,system}.py`, `tests/install/{conftest,test_steps}.py`

**Interfaces:**
- Produces:
  - `System(log)`: `run(args: list[str], sudo=False, cwd=None, input=None, interactive=False, check=True, env=None) -> str`, `ok(args) -> bool` — только списки аргументов; нет программы → `CalledProcessError(127)` при `check`, иначе `""`.
  - `StepFailed(message: str, action: str = "")`.
  - `@dataclass Ctx(system, home: Path, repo: Path, ask: Callable[[str], bool], out=print, dry_run=False, root: Path = Path("/"), language="en", state: State)`; метод `Ctx.t(key, **values)` добавляет Task 2.
  - `@dataclass Step(id, title_key, source, check: Callable[[Ctx], bool], run: Callable[[Ctx], None], manual=False)`.
  - `State` — `install.json` `{"version": 1, "installerLanguage", "systemLanguage", "selection": {...}, "snapshot": {"kind": "btrfs-ro"|"btrfs-rw"|"none", "name"} | null, "done": {id: iso}, "failed": id|null, "error": str|null, "changes": [...], "finished": bool}`; `State.load(path) -> State` (повреждённый файл → пустое состояние, файл переименовывается в `.broken-<время>`), `State.save()` атомарно, 0600.
  - Журнал изменений `changes` — записи `{"kind": "file", "path", "backup": str|null}` (null — файл создан установщиком), `{"kind": "package", "name"}`, `{"kind": "flatpak", "id"}`, `{"kind": "service", "unit"}`; `Ctx.record(change: dict)` дописывает и сохраняет.
  - `Runner(steps, ctx, log_path)`: `run(start: str | None = None) -> bool` (неизвестный `start` — `StepFailed`), `status() -> list[tuple[str, str]]` (`done|failed|pending`).
  - `redact(text) -> str`; замок `install.lock` (`fcntl.flock`) — второй запуск получает `StepFailed("another installer is running")`.
- Журнал `install.log` — английский: `YYYY-mm-dd HH:MM:SS <redact(строка)>`, команды `$ …`, результаты `<id> [<source>]: skipped (already done) | will run | running | done | failed: <причина>`.

- [x] **Step 1: Перенести и дописать тесты** `test_install_runner.py`: из старых `test_steps.py` — `test_done_steps_are_not_repeated`, `test_resume_starts_at_failed_step`, `test_dry_run_changes_nothing`, `test_log_redacts_secrets`, `test_status_reports_each_step`, `test_missing_command_is_a_failed_command_not_a_crash`, `test_crashing_check_counts_as_not_done` (с английскими статусами журнала); новые — `test_unknown_start_step_is_an_error`, `test_second_runner_is_refused_while_locked`, `test_corrupt_state_is_kept_aside_and_starts_empty`, `test_changes_journal_survives_reload` (`record` трёх видов → `State.load` возвращает их в порядке), `test_state_and_log_are_private` (0600).
- [x] **Step 2: Убедиться, что тесты падают.** `uv run --python 3.14 pytest tests/install -v` → FAIL: нет модуля.
- [x] **Step 3: Реализовать** `runner.py` (атомарная запись — своя функция, без импорта `quietline_shell`).
- [x] **Step 4: Убедиться, что тесты проходят.** `uv run --python 3.14 pytest -q` → PASS.
- [x] **Step 5: Коммит** `feat(installer): ядро установщика с продолжением и журналом изменений`.

### Task 2: Тексты и экраны

**Files:**
- Create: `src/quietline_install/texts.py`, `screens.py`, `tests/install/test_install_screens.py`
- Modify: `src/quietline_install/runner.py` (`Ctx.t`)

**Interfaces:**
- Consumes: `Ctx` (Task 1); модель каталога из Task 3 — только через аргументы (`sections: list[Section]`, см. Task 3), чтобы задачи не зависели по порядку: экраны получают каталог как данные.
- Produces:
  - `TEXTS = {"ru": {...}, "en": {...}}`, `text(language, key, **values) -> str` (нет ключа в `ru` → `en`); `Ctx.t(key, **values) = text(ctx.language, key, **values)` (модуль `runner.py`).
  - Чистые модели: `Choice(options: list[str], index=0)` с `move(delta)`; `Checklist(items: list[Item])` — `Item(id, label, checked, locked: bool, children: list[Item], expanded=False)`, методы `move(delta)`, `toggle()` (на заблокированном ничего), `expand()`, `selected() -> set[str]`, `apply_recommended(ids: set[str])`.
  - Экраны (curses, `run_*` возвращают результат; `stdscr` передаётся): `ask_language(stdscr) -> "ru"|"en"` (экран двуязычный: «Русский / English»), `show_checks(stdscr, ctx, results) -> bool`, `ask_system_language(stdscr, ctx, current) -> "ru"|"en"`, `choose_programs(stdscr, ctx, checklist) -> set[str] | "recommended"`, `confirm_summary(stdscr, ctx, lines) -> bool`, `ask_resume(stdscr, ctx, failed_step) -> "continue"|"rollback"|"quit"`.
  - Клавиши: стрелки, пробел — отметить, Enter — дальше/раскрыть, `r` или кнопка «Рекомендуемый набор — установить» первой строкой, Esc — назад, `q` — выход без изменений.
- Ключи текстов: экраны, названия разделов каталога (`sectionBrowsers`, `sectionMessengers`, `sectionFiles`, `sectionCode`, `sectionPasswords`, `sectionVpn`, `sectionRemote`, `sectionDocuments`, `sectionContainers`, `sectionDotnet`, `sectionNode`, `sectionPython`, `sectionDevTools`, `advanced`), проверки, предупреждение без Btrfs, сводка, итог, выбор «Продолжить/Откатить», названия шагов (`step.<id>`), действия при ошибке.

- [x] **Step 1: Написать тесты:** `test_both_languages_have_the_same_keys_and_placeholders`; `test_locked_item_cannot_be_unchecked` (установленная программа отмечена и неактивна); `test_recommended_selection_checks_only_recommended`; `test_advanced_children_are_hidden_until_expanded`; `test_selected_includes_checked_children` (выбранная версия .NET в «Расширенных» попадает в выбор); `test_moving_past_the_ends_stays_in_range`.
- [x] **Step 2: Убедиться, что тесты падают.** `uv run --python 3.14 pytest tests/install/test_install_screens.py -v` → FAIL.
- [x] **Step 3: Реализовать** тексты, модели и отрисовку (отрисовка — без логики выбора; длинные списки прокручиваются; строки обрезаются по ширине экрана).
- [x] **Step 4: Убедиться, что тесты проходят.** `uv run --python 3.14 pytest -q` → PASS.
- [x] **Step 5: Коммит** `feat(installer): экраны установщика на русском и английском`.

### Task 3: Каталог программ

**Files:**
- Create: `installer/catalog.toml`, `src/quietline_install/catalog.py`, `scripts/check-catalog.py`, `tests/install/test_install_catalog.py`

**Interfaces:**
- Produces:
  - `catalog.toml`: `[core] packages = [...]`, `services = [...]`; `[[section]] id, title_key, multiple = true|false, advanced = false`; `[[section.item]] id, name, source = "repo"|"flatpak"|"aur"|"manual"|"fnm"|"uv", packages = [...], desktop = "<desktop ID>"|"", recommended = bool, services = [...], pin = "files"|"browser"|"code"|"terminal"|"messenger"|""`.
  - `load_catalog(path) -> Catalog`; `Catalog.validate()` — уникальные id, известные источники, у `flatpak` — один id приложения, у `pin` — непустой `desktop`; ошибка — `ValueError` с id.
  - `Catalog.sections -> list[Section]` (для экранов), `Catalog.recommended() -> set[str]`, `Catalog.plan(selection: set[str]) -> Plan` — `Plan(repo: list[str], flatpak: list[str], aur: list[str], manual: list[str], fnm: list[str], uv: list[str], services: list[str], pins: list[str])`; `core` всегда в `repo`; порядок пакетов стабилен; дубликаты убраны.
  - `pins` — desktop ID в порядке files, browser (первый выбранный), code, terminal, messenger (первый выбранный); невыбранное пропускается.
  - `scripts/check-catalog.py` — `pacman -Si` для всех `repo`-пакетов, `flatpak remote-info flathub <id>` не проверяется (нет сети к Flathub в CI); пропуски — `missing: …`, код 1.
- Содержимое каталога (имена — по исследованию 2026-10-28; desktop ID с пометкой «?» — не подтверждены, пункт в backlog):

| Раздел | Вариант | Источник и пакеты | desktop | рекоменд. |
|---|---|---|---|---|
| core | основа | repo: `hyprland quickshell greetd greetd-tuigreet xdg-desktop-portal-hyprland xdg-desktop-portal-gtk hyprpolkitagent qt6-wayland polkit pipewire pipewire-pulse wireplumber networkmanager bluez bluez-utils power-profiles-daemon brightnessctl upower libnotify glib2 xdg-user-dirs xdg-utils flatpak ttf-ibm-plex ttf-jetbrains-mono-nerd noto-fonts noto-fonts-emoji grim slurp satty wl-clipboard cliphist plocate ghostty fish fisher micro git openssh curl unzip`; службы `NetworkManager.service bluetooth.service power-profiles-daemon.service` | — | всегда |
| browsers (несколько) | chrome / firefox / brave / chromium | aur `google-chrome` / repo `firefox` / flatpak `com.brave.Browser` / repo `chromium` | `google-chrome` / `firefox` / `com.brave.Browser` / `chromium` | chrome |
| messengers (несколько) | telegram / slack / wechat | repo `telegram-desktop` / aur `slack-desktop` / aur `wechat-bin` + repo `noto-fonts-cjk` | `org.telegram.desktop` / `slack` / `wechat?` | telegram |
| files | dolphin | repo `dolphin` | `org.kde.dolphin` | да |
| code | vscode | aur `visual-studio-code-bin` | `code?` | да |
| passwords | 1password | aur `1password` | `com.onepassword.OnePassword` | да |
| vpn | amneziavpn | manual | — | да |
| remote | remmina | repo `remmina freerdp libvncserver gtk-vnc libsecret` | `org.remmina.Remmina` | да |
| documents | onlyoffice | flatpak `org.onlyoffice.desktopeditors` + repo `ttf-carlito ttf-caladea ttf-liberation` | `org.onlyoffice.desktopeditors` | да |
| containers | docker / docker-desktop | repo `docker docker-buildx docker-compose`, служба `docker.socket` / manual | — | docker — да, desktop — нет |
| dotnet | latest; advanced: 8.0, 9.0 | repo `dotnet-sdk aspnet-runtime aspnet-targeting-pack` / `dotnet-sdk-8.0 aspnet-runtime-8.0` / `dotnet-sdk-9.0 aspnet-runtime-9.0` | — | latest |
| node | lts; advanced: 22, 24, 26 | repo `fnm pnpm` + fnm `lts-latest` / `22` / `24` / `26` | — | lts |
| python | system; advanced: 3.12, 3.13 | repo `python python-pip uv` / uv `3.12` / `3.13` | — | system |
| devtools | tools | repo `base-devel jq ripgrep fzf` | — | да |

- [x] **Step 1: Написать тесты:** `test_catalog_is_valid`; `test_recommended_set_matches_the_spec` (ровно chrome, telegram, dolphin, vscode, 1password, amneziavpn, remmina, onlyoffice, docker, dotnet latest, node lts, python system, devtools); `test_plan_always_contains_core`; `test_plan_splits_sources` (brave → flatpak, slack → aur, docker-desktop → manual); `test_pins_follow_selection_order` (firefox+brave, без code → `["org.kde.dolphin", "firefox", "com.mitchellh.ghostty", "org.telegram.desktop"]`); `test_unknown_source_is_rejected`; `test_no_aur_package_for_hyprland_or_quickshell` (ни один `aur`-вариант не содержит `hyprland*`/`quickshell*`).
- [x] **Step 2: Убедиться, что тесты падают.** `uv run --python 3.14 pytest tests/install/test_install_catalog.py -v` → FAIL.
- [x] **Step 3: Реализовать** каталог, `catalog.py` и `scripts/check-catalog.py`.
- [x] **Step 4: Убедиться, что тесты проходят.** `uv run --python 3.14 pytest -q` → PASS.
- [x] **Step 5: Коммит** `feat(installer): каталог программ с источниками и рекомендуемым набором`.

### Task 4: Снимок Btrfs и откат

**Files:**
- Create: `src/quietline_install/snapshot.py`, `tests/install/test_install_snapshot.py`

**Interfaces:**
- Consumes: `Ctx`, `System`, журнал `changes` (Task 1).
- Produces:
  - `inspect_root(ctx) -> RootInfo` — `RootInfo(fstype, device, subvol, boot_inside: bool, systemd_hook: bool, overlay: bool, swapfile_in_root: bool)` по `findmnt -no FSTYPE,SOURCE,OPTIONS /`, `findmnt -no SOURCE /boot` (пусто или тот же источник — внутри), `/etc/mkinitcpio.conf` (`HOOKS=(...)`), `/proc/swaps`.
  - `snapshot_plan(info) -> "btrfs-ro"|"btrfs-rw"|"none"` и причина (`text` ключ): `btrfs-ro` — Btrfs, `subvol=/@`, `/boot` внутри, нет `systemd` в HOOKS; `btrfs-rw` — то же, но хук недоступен; `none` — не Btrfs, `subvol` не `/@`, `/boot` отдельно, загружен снимок (`overlay`) или swap-файл в `@`.
  - `prepare(ctx)` — `pacman -S --needed --noconfirm grub-btrfs` (без `-y`), `grub-btrfs-overlayfs` в конец `HOOKS` (идемпотентно, с копией `/etc/mkinitcpio.conf`), `mkinitcpio -P`; только для `btrfs-ro`.
  - `take(ctx, kind) -> str` — монтирует верх (`mount -o subvolid=5 <device> <tmp>`), создаёт `@snapshots` при отсутствии, `btrfs subvolume snapshot [-r] <tmp>/@ <tmp>/@snapshots/quietline-pre-<YYYYmmdd-HHMMSS>`, размонтирует, `grub-mkconfig -o /boot/grub/grub.cfg`; имя — в `State.snapshot`.
  - `rollback_btrfs(ctx, name)` — монтирует верх, `mv @ @broken-<время>`, `btrfs subvolume snapshot <tmp>/@snapshots/<name> <tmp>/@`, удаляет `subvolid=N` только из строки `/` в `<tmp>/@/etc/fstab`, размонтирует; затем `rollback_home(ctx)`; перезагрузку предлагает экран, а не функция.
  - `rollback_home(ctx)` — для записей `file` под `ctx.home` в обратном порядке: есть `backup` → вернуть, нет → удалить.
  - `rollback_journal(ctx)` — всё из журнала в обратном порядке: `file` (в том числе системные через `sudo`), `service` → `systemctl disable`, `flatpak` → `flatpak uninstall --user`, `package` → один `pacman -Rns` для пакетов, которых не было до установки.
  - Устройство при `overlay` берётся из `root=UUID=` в `/proc/cmdline`.

- [x] **Step 1: Написать тесты:** `test_snapshot_plan_follows_root_layout` (параметры: btrfs `/@` → ro; с `systemd` в HOOKS → rw; ext4 → none; `/boot` отдельно → none; `subvol=/` → none; overlay → none; swap-файл в корне → none); `test_prepare_adds_hook_once_and_never_syncs_databases` (повтор не дублирует хук; нет `-Sy`); `test_snapshot_commands_use_top_level_and_regenerate_grub` (порядок: mount subvolid=5, create @snapshots, snapshot -r, umount, grub-mkconfig); `test_btrfs_rollback_commands` (mv @, snapshot из имени, fstab: из `UUID=x / btrfs rw,noatime,subvolid=256,subvol=/@ 0 0` → `…rw,noatime,subvol=/@…`, строка `/home` не тронута); `test_rollback_restores_home_files_and_removes_created`; `test_journal_rollback_keeps_preexisting_packages`; `test_installer_never_touches_partitions` (регулярка запрещённых команд по `src/quietline_install/**/*.py` и `install.sh`).
- [x] **Step 2: Убедиться, что тесты падают.** `uv run --python 3.14 pytest tests/install/test_install_snapshot.py -v` → FAIL.
- [x] **Step 3: Реализовать** `snapshot.py`; временный каталог — `/run/quietline-top.XXXXXX` через `mktemp -d` под `sudo`.
- [x] **Step 4: Убедиться, что тесты проходят.** `uv run --python 3.14 pytest -q` → PASS.
- [x] **Step 5: Коммит** `feat(installer): снимок корня Btrfs и откат установки`.

### Task 5: Пакеты Arch, Flatpak, службы, локали, версии разработки и пакет quietline

**Files:**
- Create: `src/quietline_install/steps/__init__.py` (пока пустой список — заполняет Task 8), `steps/packages.py`, `packaging/arch/PKGBUILD`, `tests/install/test_install_packages.py`
- Modify: `.gitignore` (`packaging/arch/src/`, `packaging/arch/pkg/`, `*.pkg.tar.*`)
- Источник: `origin/feature/installer:src/quietline_install/packages.py`, `packaging/arch/PKGBUILD`, `tests/install/test_packages.py`

**Interfaces:**
- Consumes: `Plan` (Task 3), `Ctx.record` (Task 1).
- Produces шаги (фабрики `-> Step`):
  - `upgrade_step()` — `sudo pacman -Syu` (interactive), id `system-upgrade`; выполняется один раз за установку (отметка в состоянии).
  - `repo_step(packages)` — до установки `pacman -Si` каждого (нет → `StepFailed` с именем, ничего не ставится), затем `sudo pacman -S --needed <все>` одной транзакцией; в журнал — пакеты, которых не было (`pacman -Qq` до).
  - `graphics_step()` — как в старой ветке (intel: `mesa vulkan-intel intel-media-driver`; amd: `mesa vulkan-radeon`; nvidia — `StepFailed` с указанием; прочее — `mesa`).
  - `locales_step()` — раскомментировать `en_US.UTF-8 UTF-8` и `ru_RU.UTF-8 UTF-8` в `/etc/locale.gen` (копия), `sudo locale-gen`; check — обе строки активны.
  - `services_step(units)` — `systemctl enable --now` каждой; check — `is-enabled` каждой; журнал `service`.
  - `flatpak_step(ids)` — `flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo`, `flatpak install --user -y flathub <id>`; журнал `flatpak`.
  - `fnm_step(versions)` — `fnm install <v>` для каждой (`lts-latest` → `--lts`), `fnm default <первая>`; `uv_step(versions)` — `uv python install <v…>`.
  - `quietline_package_step()` — PKGBUILD в `~/.cache/quietline/build`, `makepkg -si --cleanbuild` с `QUIETLINE_REPO`; check — `pacman -Q quietline` равна ожидаемой версии `<version>.r<count>.g<hash>`.
- PKGBUILD: `license=('GPL-3.0-only')`, `makedepends=('git' 'python-build' 'python-installer' 'python-hatchling')`, `depends=('python' 'hyprland' 'quickshell' 'networkmanager' 'brightnessctl' 'power-profiles-daemon' 'bluez' 'pipewire' 'wireplumber' 'glib2' 'libnotify' 'wl-clipboard' 'cliphist' 'grim' 'slurp' 'satty' 'plocate' 'polkit')`; ставит wheel (`quietline-engine`, `quietline-shell`), `/usr/share/quietline/shell/` ← `shell/quietline/.`, `/usr/share/quietline/hyprland/quietline.lua`, `/usr/share/quietline/fish/quietline-locale.fish`, `/usr/share/polkit-1/rules.d/50-quietline-network.rules`, `LICENSE`; исходник — `git archive HEAD` клона.

- [x] **Step 1: Перенести и написать тесты:** из старых — `test_missing_package_stops_before_install`, `test_installed_group_is_skipped`, `test_gpu_packages_follow_detected_vendor`, `test_nvidia_stops_with_instructions`, `test_gpu_vendor_reads_drm_and_virtualization`, `test_onlyoffice_comes_from_flathub_per_user` (→ `test_flatpak_apps_install_per_user`), `test_package_is_rebuilt_for_new_commits`; новые — `test_repo_packages_install_in_one_transaction_without_sync` (`-S --needed`, без `-y`), `test_full_upgrade_runs_once`, `test_new_packages_are_journaled_but_preexisting_are_not`, `test_both_locales_are_enabled_once`, `test_fnm_installs_versions_and_sets_default`, `test_pkgbuild_installs_expected_paths` (пути выше, `GPL-3.0-only`, `python-hatchling`).
- [x] **Step 2: Убедиться, что тесты падают.** `uv run --python 3.14 pytest tests/install/test_install_packages.py -v` → FAIL.
- [x] **Step 3: Реализовать.**
- [x] **Step 4: Убедиться, что тесты проходят.** `uv run --python 3.14 pytest -q` → PASS.
- [x] **Step 5: Коммит** `feat(installer): пакеты Arch, Flatpak, локали и пакет quietline`.

### Task 6: AUR

**Files:**
- Create: `src/quietline_install/steps/aur.py`, `tests/install/test_install_aur.py`
- Источник: `origin/feature/installer:src/quietline_install/aur.py`, `tests/install/test_aur.py`

**Interfaces:**
- Produces: `aur_step(name) -> Step` (id `aur-<name>`, source `AUR: <name>`); `aur_install(ctx, name)` — клон или `git pull --ff-only` в `~/.cache/quietline/aur/<name>` (с таймаутом), показ `PKGBUILD`, всех `*.install` и списка остальных файлов клона, вопрос, для `1password` — `curl -fsS https://downloads.1password.com/linux/keys/1password.asc` → `gpg --import`, затем `makepkg -si --cleanbuild` (interactive, без `--noconfirm`); журнал `package`; `aur_outdated(ctx, names, fetch) -> list[str]` — сетевые ошибки RPC дают пустой список и строку в журнале, не traceback.

- [x] **Step 1: Перенести тесты** `test_pkgbuild_is_shown_and_must_be_confirmed`, `test_confirmed_build_runs_makepkg_in_clone`, `test_fresh_package_is_cloned_from_aur`, `test_1password_key_imported_before_build` (с `-f`), `test_update_lists_only_newer_aur_versions`; новые — `test_other_files_in_clone_are_listed`, `test_rpc_failure_is_not_a_crash`.
- [x] **Step 2: Убедиться, что тесты падают.** `uv run --python 3.14 pytest tests/install/test_install_aur.py -v` → FAIL.
- [x] **Step 3: Реализовать.**
- [x] **Step 4: Убедиться, что тесты проходят.** `uv run --python 3.14 pytest -q` → PASS.
- [x] **Step 5: Коммит** `feat(installer): сборка AUR с показом инструкций`.

### Task 7: Файлы пользователя, язык, закрепления, папки

**Files:**
- Create: `src/quietline_install/steps/configs.py`, `installer/files/{hyprland.lua,quietline.fish,user-dirs.dirs,user-dirs.conf}`, `tests/install/test_install_configs.py`
- Modify: `config/hyprland/quietline.lua` (шапка: подключение строкой `dofile("/usr/share/quietline/hyprland/quietline.lua")`)
- Источник: `origin/feature/installer:src/quietline_install/configs.py`, `tests/install/test_configs.py`, `test_review_fixes.py`

**Interfaces:**
- Consumes: `Ctx.record`, `State.selection`, `State.systemLanguage`, `Plan.pins`.
- Produces:
  - `install_file(ctx, source, target, sudo=False) -> str` — `created | unchanged | updated, backup <путь>`; копия только если содержимое отличается и от последней копии; журнал `file`.
  - `hyprland_step()` — нет файла, или в нём нет строки `dofile("/usr/share/quietline/hyprland/quietline.lua")` → шаблон с копией; строка есть → ничего.
  - `fish_step()` — `~/.config/fish/conf.d/quietline.fish` (`EDITOR`/`VISUAL=micro`, при выбранном Node — `fnm env --use-on-cd --shell fish | source`) и `~/.config/fish/conf.d/quietline-locale.fish` ← `/usr/share/quietline/fish/quietline-locale.fish`.
  - `tide_step()` — нет `~/.config/fish/functions/tide.fish` → `fish -c 'fisher install ilancosman/tide@v6'` от пользователя; без терминала мастер Tide не запускается, включается стиль Lean.
  - `micro_step()` — слияние `{"clipboard": "external", "mouse": true}` в `~/.config/micro/settings.json`.
  - `quickshell_link_step()` — `~/.config/quickshell/quietline` → `/usr/share/quietline/shell` (существующий каталог — в копию).
  - `user_dirs_step()` — нет `~/.config/user-dirs.dirs` → английский шаблон и каталоги `Desktop Documents Downloads Music Pictures Public Templates Videos`; есть → не трогается, в итог — строка с путями; `user-dirs.conf` с `enabled=False` пишется всегда (с копией).
  - `region_step()` — `quietline-shell region --set '{"language": "<ru|en>", "clock": …, "date": …}'` (clock/date по языку: ru — `24h`/`dmy`, en — `12h`/`mdy`) при первой установке; при повторной — только если язык системы изменён на экране.
  - `pins_step(pins)` — только если нет `$XDG_CONFIG_HOME/quietline/pins.json`: `quietline-shell pins --set '<JSON список>'`.

- [x] **Step 1: Написать тесты:** перенесённые `test_existing_user_config_is_backed_up_once`, `test_new_config_is_created_without_backup`, `test_quickshell_link_points_to_package_shell`, `test_micro_settings_are_merged_not_replaced`; новые — `test_example_hyprland_config_is_replaced_with_backup`, `test_hyprland_config_with_quietline_line_is_untouched`, `test_fish_snippets_include_locale_and_fnm_only_when_node_selected`, `test_existing_user_dirs_are_left_as_is`, `test_fresh_user_dirs_are_english_and_rename_is_disabled`, `test_region_is_set_through_quietline_shell`, `test_existing_pins_are_not_overwritten`, `test_lua_header_names_the_dofile_line`.
- [x] **Step 2: Убедиться, что тесты падают.** `uv run --python 3.14 pytest tests/install/test_install_configs.py -v` → FAIL.
- [x] **Step 3: Реализовать.**
- [x] **Step 4: Убедиться, что тесты проходят.** `uv run --python 3.14 pytest -q` → PASS.
- [x] **Step 5: Коммит** `feat(installer): файлы пользователя, язык системы и закрепления дока`.

### Task 8: Сеанс входа, ручные шаги, проверка готовности

**Files:**
- Create: `src/quietline_install/steps/session.py`, `steps/checks.py`, `installer/files/greetd-config.toml`, `tests/install/test_install_session.py`
- Modify: `src/quietline_install/steps/__init__.py` — `build_steps(plan: Plan, state: State) -> list[Step]`
- Источник: `origin/feature/installer:src/quietline_install/{session,checks,plan}.py`, `tests/install/{test_session,test_check}.py`

**Interfaces:**
- Produces:
  - `greetd_step()` — `/etc/greetd/config.toml` из шаблона (`tuigreet --time --remember --remember-session --sessions /usr/share/wayland-sessions`, `user = "greeter"`), только если в файле нет `tuigreet`; копия; `systemctl enable greetd.service` без `--now`.
  - `default_shell_step()`, `docker_group_step()` — с вопросом и маркером отказа `declined-<id>`; в итоге — `docker context show`.
  - `docker_desktop_step()` — ручной: ссылка `https://docs.docker.com/desktop/setup/install/linux/archlinux/`, команда `sudo pacman -U ./docker-desktop-x86_64.pkg.tar.zst`, принятие условий при первом запуске, пояснение о контекстах `desktop-linux` и `default`; check — `pacman -Q docker-desktop`.
  - `amneziavpn_step()` — ручной: `https://github.com/amnezia-vpn/amnezia-client/releases` и страница `https://amnezia.org/en/downloads`; check — `/opt/AmneziaVPN` или `AmneziaVPN` в `PATH`.
  - `run_checks(ctx, plan, which=shutil.which) -> tuple[list[str], bool]` — команды основы и выбранного, службы, `pacman -Q quietline`, Flatpak выбранного, `~/.config/quickshell/quietline/lock/LockScreen.qml`, строка `dofile` в `hyprland.lua`, `region.json`, обе локали.
  - `build_steps(plan, state)` — порядок: `system-upgrade`, `repo-packages`, `graphics`, `locales`, `quietline-package`, `services`, `hyprland-config`, `fish`, `micro`, `quickshell-link`, `user-dirs`, `region`, `pins`, `greetd`, `flatpak`, `fnm`, `uv`, `aur-<name>`…, `default-shell`, `docker-group`, ручные шаги последними; шаги невыбранного в список не попадают.

- [x] **Step 1: Перенести и написать тесты:** `test_greetd_config_launches_wayland_sessions`, `test_greetd_is_enabled_not_started`, `test_user_greetd_config_with_tuigreet_is_kept`, `test_manual_steps_wait_for_confirmation_and_verify`, `test_docker_group_asks_and_explains_root_equivalence`, `test_declined_optional_step_is_not_asked_again`, `test_default_shell_changes_only_with_consent`, `test_check_reports_each_item_and_fails_on_missing`, `test_login_session_comes_before_aur_and_manual_steps_last`, `test_unselected_programs_have_no_steps`.
- [x] **Step 2: Убедиться, что тесты падают.** `uv run --python 3.14 pytest tests/install/test_install_session.py -v` → FAIL.
- [x] **Step 3: Реализовать.**
- [x] **Step 4: Убедиться, что тесты проходят.** `uv run --python 3.14 pytest -q` → PASS.
- [x] **Step 5: Коммит** `feat(installer): сеанс входа, ручные шаги и проверка готовности`.

### Task 9: Порядок экранов, `install.sh`, CLI

**Files:**
- Create: `install.sh`, `src/quietline_install/__main__.py`, `tests/install/test_install_flow.py`

**Interfaces:**
- Consumes: всё выше.
- Produces:
  - `install.sh` — `TERM=linux` → `setfont cyr-sun16` (ошибка не фатальна); отказ от root и не-Arch (английский текст); нет `python`/`git` → `sudo pacman -S --needed python git` (без `-y`; при ошибке — совет `sudo pacman -Syu`); `python -c 'import sys; sys.exit(sys.version_info < (3, 14))'`; `PYTHONPATH="$repo/src" exec python -m quietline_install --repo "$repo" "$@"`.
  - `main(argv=None, screens=<curses>) -> int`; команды: `run` (по умолчанию), `status`, `check`, `rollback`, `update`; флаги `--dry-run`, `--from <id>`.
  - `run`: незавершённое состояние → `ask_resume` («Продолжить / Откатить / Выйти»); иначе экраны по порядку спеки; при `snapshot_plan == "none"` — предупреждение и согласие; после сводки — `prepare` (только `btrfs-ro`) → `take` → шаги; при ошибке шага — `ask_resume`; в конце — итог, `run_checks`, предложение перезагрузиться.
  - `rollback`: `btrfs-*` → `rollback_btrfs` + предложение перезагрузки; `none` → `rollback_journal`; после отката состояние помечается `rolledBack`.
  - Слой экранов подменяется в тестах объектом с теми же методами.

- [x] **Step 1: Написать тесты:** `test_first_run_walks_screens_in_spec_order` (язык → проверки → язык системы → программы → сводка); `test_quit_before_summary_changes_nothing` (ни одной команды `System`); `test_snapshot_is_taken_before_first_changing_step`; `test_rerun_offers_continue_or_rollback`; `test_rollback_uses_btrfs_when_snapshot_exists_and_journal_otherwise`; `test_non_btrfs_requires_explicit_consent`; `test_install_sh_refuses_root_and_non_arch` (через `sh` с подменёнными `id` и `/etc/os-release` во временном каталоге).
- [x] **Step 2: Убедиться, что тесты падают.** `uv run --python 3.14 pytest tests/install/test_install_flow.py -v` → FAIL.
- [x] **Step 3: Реализовать.**
- [x] **Step 4: Убедиться, что тесты проходят.** `uv run --python 3.14 pytest -q` → PASS.
- [x] **Step 5: Коммит** `feat(installer): порядок экранов, install.sh и команды установщика`.

### Task 10: Гайд установки Arch, документация, CI

**Files:**
- Create: `docs/install/2026-10-20-arch-install.md` (из старой ветки с правками), `docs/install/updating.md`, `scripts/smoke-installer.md`, `.github/workflows/tests.yml`
- Modify: основная спека («Установка на текущем компьютере», «Приложения и инструменты» — каталог и источники, расширенный список AUR, Flatpak Brave), спека этапа 5 (статус части 2), `AGENTS.md`, `README.md`, `CHANGELOG.md`, `docs/backlog.md`, этот план

- [x] **Step 1: Гайд** — `p8` форматируется в Btrfs; подтома `@ @home @log @pkg @snapshots` (последний не монтируется); `p6` монтируется в `/efi` без форматирования, `/boot` — каталог в `@`; в archinstall Pre-mount и «No bootloader»; вручную в chroot: `pacman -S grub efibootmgr os-prober btrfs-progs`, `grub-install --target=x86_64-efi --efi-directory=/efi --bootloader-id=Arch` (без `--removable`), `GRUB_DISABLE_OS_PROBER=false`, `grub-mkconfig -o /boot/grub/grub.cfg`; ожидаемый `fstab`; `rm -r /efi/EFI/ubuntu` после проверки; восстановление GRUB с `/efi`; «После установки» — `./install.sh`; устаревшее про репозиторий без remote убрать; локали генерирует установщик. Гайд — для человека, агент команды разметки не выполняет.
- [x] **Step 2: `updating.md`, `smoke-installer.md`** — сценарии: чистый Arch в VM (Btrfs по гайду); язык установщика en и ru (кириллица в консоли); каталог с «Рекомендуемым набором» и с «Расширенными»; обрыв сети посреди пакетов → «Продолжить»; «Откатить» на Btrfs → перезагрузка в прежний `@`; загрузка снимка из меню GRUB (overlay, изменения пропадают); корень ext4 → предупреждение и откат по журналу; свой `hyprland.lua` с примером → заменён с копией; вход через greetd, `Super+Enter` без панели; английские папки и `locale` в Ghostty; закрепления по выбору; ноутбук. В `backlog.md` — те же пункты плюс непроверенные desktop ID (`code`, `wechat`, `docker-desktop`, `AmneziaVPN`), Flatpak Brave и расширение 1Password, `rw` в строке ядра для снимка только для чтения, `--boot-directory` archinstall, `cyr-sun16` в консоли, `greetd` + `source_profile` → `locale.conf`, `fnm` в fish.
- [x] **Step 3: CI** `.github/workflows/tests.yml` — задачи `python` (`astral-sh/setup-uv`, `uv run --python 3.14 pytest -q`), `shell-models` (Node 22, `node --test 'tests/shell/*.test.cjs'`), `catalog` (контейнер `archlinux:latest`, `pacman -Syu --noconfirm python`, `python scripts/check-catalog.py`); триггер `push`.
- [x] **Step 4: `AGENTS.md`** — Layout (`install.sh`, `installer/`, `packaging/`, `.github/`, `docs/install/`, `src/quietline_install/`, `tests/install/`), исключение из «консоль — по-английски» для экранов установщика (журнал английский), команды запуска установщика и тестов, «Текущее состояние», «Куда смотреть»; `README.md` — статус и структура; `CHANGELOG.md` `Unreleased` — Added: установщик (языки, каталог, снимок и откат, гайд); основная спека — таблица приложений с источниками этого плана; статусы спеки этапа 5 и плана.
- [x] **Step 5: Полная проверка** `uv run --python 3.14 pytest -q`, `node --test 'tests/shell/*.test.cjs'` → PASS; коммит `docs(installer): гайд установки Arch на Btrfs, сценарии проверки и CI`. Независимое ревью ветки — по Review Focus.
