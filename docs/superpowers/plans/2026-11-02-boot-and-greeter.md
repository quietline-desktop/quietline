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
- `config/grub/theme.txt.in` — шаблон темы, `config/grub/make-theme.py` — PNG обоев и капсулы, `theme-ru.txt` / `theme-en.txt` из шаблона.
- `packaging/arch/PKGBUILD` — установка файлов экрана входа и темы, `grub-mkfont`, `makedepends` / `depends`.
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
- [ ] 3. `config/greeter/`: сценарий с запасным tuigreet, `hyprland.lua` (без логотипа, раскладки, `qs -p` и выход Hyprland), tmpfiles. Первая проверка — `qs -p Greeter.qml` в текущем сеансе: вне greetd (`Greetd.available` ложно) экран показывает форму и списки, а вход отвечает «экран входа запущен не из greetd». Полная проверка — после установки пакета.
- [ ] 4. Тема GRUB: шаблон, генератор PNG на стандартной библиотеке Python, шрифты `grub-mkfont` с кириллицей; PKGBUILD. Проверка — `scripts/preview-grub-theme`: `grub-mkstandalone` с темой во встроенном диске, запуск в QEMU с OVMF без доступа к настоящему загрузчику, снимок экрана монитора QEMU на 1920×1200.
- [ ] 5. Установщик: шаблон greetd, шаг темы GRUB (пропуск без GRUB, `GRUB_THEME`, `GRUB_TERMINAL_OUTPUT`, `grub-mkconfig`, возврат при ошибке), откат по журналу, тесты; `FORBIDDEN` не тронут.
- [ ] 6. Документы и сценарий живой проверки `scripts/smoke-boot-greeter.md`, пункты в `docs/backlog.md`.
- [ ] 7. Живая проверка на машине пользователя: пакет из клона (`./install.sh update`), перезагрузка — меню GRUB, экран входа, вход и хранилище паролей, выход из сеанса, запасной tuigreet.

## Review Focus

- Вход не должен потеряться: при любой ошибке экрана входа запускается tuigreet; проверить код возврата `qs` при ошибке QML.
- Пароль не попадает в журнал, файлы и аргументы процессов; поле очищается после отправки.
- `grub-mkconfig` при ошибке — файл возвращён, конфигурация пересобрана; в журнале изменений порядок записей даёт `grub-mkconfig` после возврата файла.
- Установщик не вызывает `grub-install`, `efibootmgr`, `bootctl` (тест `FORBIDDEN`).
- Строки на двух языках, кириллицы в QML нет.

## Решения по ходу

- Чужой `config.toml` greetd с tuigreet (без строки-отметки шаблона Quietline) сохраняется, как раньше; прежний шаблон Quietline с tuigreet заменяется новым с копией.
