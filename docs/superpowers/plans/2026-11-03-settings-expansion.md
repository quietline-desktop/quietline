# План: расширение окна «Настройки»

**Статус:** в работе. Спека — `docs/superpowers/specs/2026-11-03-settings-expansion-design.md`.

**Цель:** мониторы с разрешением, частотой, расположением, поворотом и VRR; новые разделы «Мышь и тачпад», «Клавиатура», «Дата и время», «Приложения по умолчанию», «Панель и док»; сроки блокировки и сна; микрофон и громкость приложений; страницы шире и по центру.

**Границы:** `shell/quietline/bar/`, экран блокировки и входа не меняются (их правит другая сессия). Процент заряда переезжает только как элемент «Настроек» — панель читает его из `Appearance`, как раньше.

## Карта файлов

| Файл | Что меняется |
|---|---|
| `src/quietline_shell/config.py` | `display` v2 (мониторы, режимы, миграция v1), `input`, `idle settings` и `hypridle.conf`, `dockAutohide` в `appearance`, `time` (timedatectl), `defaults` (desktop-файлы, `mimeapps.list`); в пакете уже восемь модулей, новый не заводится |
| `src/quietline_shell/__main__.py` | подкоманды `input`, `idle settings`, `time`, `defaults`, поля `display --set`; docstring |
| `config/hyprland/quietline.lua` | `display.lua` с таблицами, `input.lua`, пользовательский `hypridle.conf` |
| `config/polkit/50-quietline-time.rules`, `packaging/arch/PKGBUILD` | правило часового пояса и NTP |
| `shell/quietline/settings/` | делится на `window/` (окно, страница, пояснение) и `pages/` (новые страницы) |
| `shell/quietline/inputs/ShellSelect.qml` | выпадающий список |
| `shell/quietline/panels/AudioControls.qml`, `PowerControls.qml` | микрофоны, приложения, 150 %; сроки простоя |
| `shell/quietline/dock/Dock.qml`, `shell/quietline/Appearance.qml` | док без автоскрытия |
| `shell/quietline/logic/Models.js`, `Strings.js` | разрешения и частоты, подписи, разделы, строки в обеих таблицах |
| `tests/helper/`, `tests/shell/` | тесты бэкенда и моделей |
| `DESIGN.md`, `CHANGELOG.md`, `AGENTS.md`, `docs/backlog.md`, `scripts/smoke-settings.md` | документы |

## Шаги

- [ ] 1. Бэкенд `display` v2 и `quietline.lua`; тесты.
- [ ] 2. Бэкенд `input` и `quietline.lua`; тесты.
- [ ] 3. Бэкенд `idle settings`, `hypridle.conf` и `quietline.lua`; тесты.
- [ ] 4. Бэкенд `time` с правилом polkit и `defaults`; тесты.
- [ ] 5. `dockAutohide` в `appearance`, `Appearance.qml`, `Dock.qml`.
- [ ] 6. Оболочка: деление `settings/`, вёрстка по центру, `ShellSelect`, разделы, строки и модели; тесты Node.
- [ ] 7. Страницы: «Экран» с подтверждением, «Мышь и тачпад», «Клавиатура», «Питание», «Дата и время», «Приложения по умолчанию», «Панель и док», «Звук».
- [ ] 8. Живая проверка снимками; LG на 75 Гц с подтверждением и откатом.
- [ ] 9. Документы, `uv run --python 3.14 pytest`, `node --test 'tests/shell/*.test.cjs'`, слияние в `main`.
