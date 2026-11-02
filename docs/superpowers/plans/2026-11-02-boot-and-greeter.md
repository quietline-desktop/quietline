# План: тема GRUB и экран входа Quietline

**Статус:** в работе с 2026-11-02, ветка `feature/boot-greeter`.

**Спека:** `docs/superpowers/specs/2026-11-02-boot-and-greeter-design.md`; макет — `docs/design/quiet-line-boot.html` (утверждён пользователем 2026-11-02).

## Цель

Меню GRUB и экран входа выглядят как остальное окружение Quietline: обои варианта B, Inter, капсула акцента. Графический экран входа на Quickshell заменяет tuigreet, а tuigreet остаётся запасным.

## Границы

- Входит: `quietline-shell greeter`, `Greeter.qml` и `greeter/`, сценарий `quietline-greeter`, конфигурация Hyprland экрана входа, правило tmpfiles, тема GRUB и генератор её PNG, шрифты `.pf2` в сборке пакета, шаг установщика «Тема меню загрузки», новый шаблон greetd, откат по журналу с `grub-mkconfig`, исключение о загрузчике в AGENTS.md.
- Не входит: Plymouth, вход по отпечатку, смена пароля, светлый вид, обои и масштаб пользователя.

## Карта файлов

- `src/quietline_shell/session.py` (в папке уже восемь модулей) — пользователи по `login.defs`, сеансы из `wayland-sessions`, `Exec` без кодов полей, чтение и запись последнего выбора.
- `src/quietline_shell/__main__.py` — подкоманда `greeter [--remember JSON] [--path PATH]`, docstring.
- `tests/helper/test_greeter.py` — тесты подкоманды.
- `shell/quietline/Greeter.qml` — корень процесса экрана входа: `Greetd`, данные `quietline-shell greeter`, вход и запуск сеанса.
- `shell/quietline/greeter/` — `GreeterSurface.qml` (поверхность на экране), `GreeterMenu.qml` (список пользователей и сеансов), `Wallpaper.qml` (обои Quietline), `qmldir`.
- `shell/quietline/lock/` — общие с экраном блокировки `LockStatus.qml`, `LockClock.qml`, `UserAvatar.qml`, `PasswordField.qml`.
- `shell/quietline/logic/Strings.js` — строки `greeter*` на двух языках.
- `config/greeter/quietline-greeter` — запуск Hyprland экрана входа и запасной tuigreet.
- `config/greeter/hyprland.lua` — конфигурация Hyprland экрана входа.
- `config/greeter/quietline-greeter.conf` — правило tmpfiles для `/var/lib/quietline-greeter`.
- `config/grub/theme.txt.in` — шаблон темы, `config/grub/make-theme.py` — PNG обоев, капсулы и подложки консоли, шрифты `.pf2` через `grub-mkfont`, `theme-ru.txt` / `theme-en.txt` из шаблона.
- `packaging/arch/PKGBUILD` — установка файлов экрана входа и темы, вызов `make-theme.py` в `build()`, `makedepends` / `depends`.
- `installer/files/greetd-config.toml` — `command = "quietline-greeter"`.
- `src/quietline_install/steps/session.py` — шаг greetd: замена прежнего шаблона Quietline, чужой tuigreet сохраняется.
- `src/quietline_install/steps/boot.py` — шаг «Тема меню загрузки».
- `src/quietline_install/steps/__init__.py`, `texts.py`, `snapshot.py` (`rollback_journal`: запись `grub`).
- `scripts/preview-grub-theme` — предпросмотр темы в QEMU.
- `tests/install/test_install_session.py`, `tests/install/test_install_boot.py`, `tests/install/test_install_snapshot.py`.
- Документы: `AGENTS.md` (исключение о загрузчике, Layout, CLI), `README.md` (папки `config/`), `CHANGELOG.md`, `DESIGN.md` (экран входа и GRUB), спека установщика (строка о загрузчике), `scripts/smoke-boot-greeter.md`, `docs/backlog.md`, `THIRD_PARTY.md` — не нужен (заимствований нет).

## Шаги

- [x] 1. `quietline-shell greeter` и тесты: пользователи с UID в диапазоне `login.defs` и оболочкой не `nologin` / `false`, имя из GECOS; сеансы без `Hidden` / `NoDisplay`, `Exec` без `%f` и т.п., `DesktopNames`; последний выбор с проверкой, что пользователь и сеанс ещё есть; повреждённый файл — выбор по умолчанию; `--remember` пишет атомарно.
- [x] 2. `Greeter.qml`, `greeter/` и строки: форма на мониторе с фокусом, список пользователей и сеансов, `Greetd` — `createSession`, `respond`, `launch(argv, env, true)`, ошибки, перезагрузка и выключение. Тест строк зелёный.
- [x] 3. `config/greeter/`: сценарий с запасным tuigreet, `hyprland.lua` (без логотипа, раскладки, `qs -p` и выход Hyprland), tmpfiles. Первая проверка — `qs -p Greeter.qml` в текущем сеансе: вне greetd (`Greetd.available` ложно) экран показывает форму и списки, а вход отвечает «экран входа запущен не из greetd». Полная проверка — после установки пакета.
- [x] 4. Тема GRUB: шаблон, генератор PNG на стандартной библиотеке Python, шрифты `grub-mkfont` с кириллицей; PKGBUILD. Проверка — `scripts/preview-grub-theme`: `grub-mkstandalone` с темой во встроенном диске, запуск в QEMU с OVMF без доступа к настоящему загрузчику, снимок экрана монитора QEMU на 1920×1200.
- [x] 5. Установщик: шаблон greetd, шаг темы GRUB (пропуск без GRUB, `GRUB_THEME`, `GRUB_TERMINAL_OUTPUT`, `grub-mkconfig`, возврат при ошибке), откат по журналу, тесты; `FORBIDDEN` не тронут.
- [ ] 6. Документы и сценарий живой проверки `scripts/smoke-boot-greeter.md`, пункты в `docs/backlog.md`.
- [ ] 7. Живая проверка на машине пользователя: пакет из клона (`./install.sh update`), перезагрузка — меню GRUB, экран входа, вход и хранилище паролей, выход из сеанса, запасной tuigreet.

## Review Focus

- Вход не должен потеряться: при любой ошибке экрана входа запускается tuigreet; проверить код возврата `qs` при ошибке QML.
- Пароль не попадает в журнал, файлы и аргументы процессов; поле очищается после отправки.
- `grub-mkconfig` при ошибке — файл возвращён, конфигурация пересобрана; в журнале изменений порядок записей даёт `grub-mkconfig` после возврата файла.
- Установщик не вызывает `grub-install`, `efibootmgr`, `bootctl` (тест `FORBIDDEN`).
- Строки на двух языках, кириллицы в QML нет.

## Решения по ходу

- `qs -p` при ошибке загрузки QML завершается с кодом 255 — `hyprland.lua` экрана входа ставит метку, и `quietline-greeter` открывает tuigreet. Проверено 2026-11-02 вместе с `Hyprland --verify-config` для `config/greeter/hyprland.lua` и показом `Greeter.qml` в текущем сеансе.
- Чужой `config.toml` greetd с tuigreet (без строки-отметки шаблона Quietline) сохраняется, как раньше; прежний шаблон Quietline с tuigreet заменяется новым с копией.
- Шрифты `.pf2` делает `make-theme.py`, а не PKGBUILD: тот же сценарий нужен предпросмотру. `grub-mkfont` называет начертание только по флагам жирный/курсив, поэтому у Medium и SemiBold имя семейства задаётся `-n`, а имена шрифтов в теме подставляются из раздела NAME готовых `.pf2`.
- Геометрия меню по `gui_list.c` GRUB 2.16: картинка капсулы рисуется с полями 12 px вокруг пункта высотой `item_height`, шаг пунктов — `item_height + item_spacing`. Поэтому `item_height = 30`, `item_spacing = 24` и у обычного пункта прозрачная рамка `item_*.png` с теми же полями — капсула 54 px, текст всех пунктов на одной высоте.
- Консоль GRUB чёрная во весь экран, а не на затемнённых обоях, как в макете: поле текста gfxterm заливает цветом по умолчанию (`background_color`), тема его не задаёт, а `grub-mkconfig` эту команду не пишет. Предпросмотр в QEMU 2026-11-02: меню на русском и английском и консоль `c` на 1920×1200.
- Шаг «Тема меню загрузки» комментирует не только `GRUB_TERMINAL_OUTPUT`, но и `GRUB_TERMINAL` без `gfxterm`: `grub-mkconfig` подставляет `GRUB_TERMINAL` и во ввод, и в вывод. Шаг выполнен, когда `/etc/default/grub` уже совпадает с результатом замены; `grub.cfg` доступен только root и не читается.
