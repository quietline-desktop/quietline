# План: группы и плавный список поиска `Super+Space`

**Статус:** реализовано, живая проверка частичная (R41 в `scripts/smoke-shell-redesign.md`, `docs/backlog.md`). Спека — `docs/superpowers/specs/2026-11-03-search-groups-design.md`.

**Цель:** при пустом поле — меню групп в стиле Omarchy, при вводе — глобальный поиск без скачков, с анимациями и уважением к ограничению анимаций.

## Карта файлов

| Файл | Что меняется |
|---|---|
| `shell/quietline/logic/Models.js` | `searchGroups`, `searchGroupItems`, ключи строк в `searchSections`, `searchFileMatches`, `searchListHeight` |
| `shell/quietline/logic/Strings.js` | названия и пояснения групп, подсказки поля, «Ищу файлы…» — в обеих таблицах |
| `shell/quietline/search/SearchService.qml` | файлы не сбрасываются, `answered` — ответ на текущий запрос |
| `shell/quietline/search/SearchPanel.qml` | режимы «группы / группа / результаты», `ScriptModel`, переходы, подсветка, высота |
| `shell/quietline/surfaces/ShellPopup.qml` | `windowHeight` (высота поверхности) и `animateHeight` (плавная высота карточки) |
| `shell/quietline/bar/TopBar.qml` | поиску — наибольшая высота поверхности, плавная высота, `reducedMotion` |
| `tests/shell/models.test.cjs` | тесты новых функций |
| `DESIGN.md`, `CHANGELOG.md`, `docs/backlog.md`, `scripts/smoke-shell-redesign.md` | вид, запись для пользователя, непроверенное |

## Шаги

- [x] 1. Логика и строки: функции `Models.js`, тексты в обеих таблицах, тесты `node --test 'tests/shell/*.test.cjs'`.
- [x] 2. `SearchService` и `ShellPopup`: файлы без сброса, высота поверхности и плавная высота карточки.
- [x] 3. `SearchPanel`: группы, результаты на `ScriptModel`, подсветка, переходы, клавиши, указатель.
- [x] 4. Живая проверка: перезапуск `qs -c quietline`, снимки `grim` корня, группы и результатов; ограничение анимаций.
- [x] 5. Документы: `DESIGN.md`, `CHANGELOG.md`, `docs/backlog.md`, `scripts/smoke-shell-redesign.md`; тесты `uv run --python 3.14 pytest`; слияние в `main`.
