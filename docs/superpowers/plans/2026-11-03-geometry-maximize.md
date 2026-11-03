# Разворачивание размером — план реализации

**Статус:** выполняется (ветка `feature/geometry-maximize`).

**Goal:** «Развернуть» в режиме «Окна» растягивает окно на рамку разворачивания вместо `maximized` Hyprland, чтобы диалоги поверх развёрнутого окна принимали ввод (спека `docs/superpowers/specs/2026-11-03-geometry-maximize-design.md`).

**Границы:** тайловые и полноэкранные окна — без изменений; анимации и вид заголовка — без изменений.

## Карта файлов

| Файл | Что меняется |
|---|---|
| `src/quietline_engine/types.py` | действие `SetMaximized`; `FrameExtents` (рамка окна и заголовок) в снимке |
| `src/quietline_engine/hyprland.py` | `getoption` рамки и заголовка в снимке; `SetMaximized` → `hl.dsp.window.fullscreen({ mode = "maximized", action = "set" \| "unset", window })` |
| `src/quietline_engine/layout.py` | `maximized`, `maximizing` в данных записи; `LayoutPlanner.maximize`; перевод `maximized` Hyprland в разворачивание размером в сверке |
| `src/quietline_engine/controller.py` | `WindowController.maximize(address)` |
| `src/quietline_engine/server.py` | метод `maximize {address?}`, код `invalid_request` для неверного адреса |
| `src/quietline_engine/__main__.py` | `quietline-engine maximize [--window ADDRESS]` |
| `config/hyprland/quietline.lua` | кнопка, двойной щелчок hyprbars и `Super+F` → `quietline-engine maximize` |
| `shell/quietline/services/DesktopModel.qml` | `toggleMaximize` → `quietline-engine maximize --window` |
| `shell/quietline/logic/Models.js` | памятка клавиш узнаёт `quietline-engine maximize` |
| `tests/engine/*`, `tests/shell/*` | планировщик, сверка, рендер действия, IPC, CLI, памятка |
| `AGENTS.md`, `CHANGELOG.md`, `docs/backlog.md`, план движка | команда, контракт IPC, запись для пользователя, живые проверки |

## Шаги

- [ ] Типы, адаптер и рендер `SetMaximized`, рамка разворачивания в снимке; тесты адаптера.
- [ ] Планировщик: `maximize` (переключение, восстановление, тайловое окно, полноэкранное — ошибка) и перевод запроса приложения в сверке; тесты.
- [ ] Контроллер, IPC, CLI; тесты.
- [ ] Вызовы в Hyprland и оболочке, памятка клавиш; тесты моделей.
- [ ] Документация, CHANGELOG, backlog; все тесты.

## Проверки

- `uv run --python 3.14 pytest`, `node --test 'tests/shell/*.test.cjs'`.
- Вживую: развернуть Claude кнопкой «□», вызвать запрос 1Password — запрос нажимается; повторное «□» возвращает размер; `Super+F`, двойной щелчок, пункт меню; приложение, открывшееся развёрнутым (Brave), получает рамку размером.
