# Новый вид оболочки и окон: вариант B

**Статус:** утверждён к выполнению 2026-11-01 (ветка `feature/shell-redesign`).
**Цель:** оболочка и окна выглядят и ведут себя как утверждённый макет `docs/design/quiet-line-b.html`: тонкая панель, меню Quietline, пункт управления, прячущийся док, поиск по центру, новые уведомления и «Настройки», заголовки окон hyprbars в режиме «Окна».
**Архитектура:** внешний вид — токены `Theme.qml` и общие элементы `controls/`, `inputs/`; поверхности переписываются по одной, каждая задача оставляет оболочку рабочей. Окна и размытие — конфигурация Hyprland; заголовки — плагин hyprbars через `hyprpm`; сворачивание — специальное пространство Hyprland.
**Стек:** Hyprland 0.55+ (Lua; живая машина — 0.57), hyprland-plugins/hyprbars через `hyprpm`, Quickshell 0.3.2 (QML), Python ≥ 3.14, Node ≥ 22.
**Спецификация:** `docs/superpowers/specs/2026-11-01-shell-redesign-design.md` — источник всех значений; исполнитель читает её целиком. Макет — `docs/design/quiet-line-b.html` (`#N` в адресе открывает сцену N).

## Global Constraints

- Минимальные версии не меняются: hyprbars с `hl.plugin.hyprbars.add_button` и `inactive_button_color` есть в закреплённых `hyprpm` коммитах для 0.55 (`3aa21f2`) и 0.56 (`7644cec`) — проверено по исходникам.
- Новые пакеты — только из `extra`: `hyprpm`, `inter-font`, `ttf-material-symbols-variable`. `ttf-ibm-plex` и `ttf-jetbrains-mono-nerd` остаются в основе, пока ими пользуются памятка клавиш и терминал; из оболочки они уходят.
- Видимый текст — в обеих таблицах `Strings.js`; кириллица в QML и `Models.js` запрещена тестом. Новые ключи добавляются, неиспользуемые — удаляются из обеих таблиц.
- Комментарии — по-русски и только о текущем поведении. Папка — не больше восьми записей: `controls/` (7) делится, когда появляется девятая.
- IPC `quietline` сохраняет все функции и сигнатуры (`launcher`, `showApplications`, `showSummary`, `clipboard`, `notifications`, `settings`, `confirmKill`, `focusDock`, `toggle`, `movePin`, `dnd`, `osd`, `status`); `status` может получать новые поля.
- Проверки после каждой задачи: `node --test 'tests/shell/*.test.cjs'`, `uv run --python 3.14 pytest`; QML — живой запуск из репозитория: установленная оболочка останавливается (`pkill -x qs` по процессу `qs -c quietline`), `scripts/run-shell` в фоне, вызовы `qs -p shell/quietline ipc call quietline …`, снимок `grim`; по окончании — `qs -c quietline -d` возвращает установленную. Снимки сравниваются со сценами макета.
- Коммит — на логический шаг; сообщения — по `AGENTS.md`.

## Review Focus

1. **Без плагина всё работает.** Конфигурация Hyprland без загруженного hyprbars не падает, окна без заголовков, сворачивание доступно из дока. Проверка — Task 3 вживую (`hyprpm disable hyprbars`).
2. **Свёрнутое окно не теряется.** Оно в доке (полая точка), возвращается щелчком на активное пространство монитора дока, закрывается «Выйти» из меню дока; движок окна на `special:` не переставляет. Тест движка — Task 3.
3. **Док не мешает и не пропадает.** Без резерва места; выезжает у нижнего края, не прячется при открытом меню, перетаскивании, навигации с клавиатуры и на пустом пространстве; в «Тайлах» и в полноэкранном режиме его нет. Логика видимости — чистая функция `Models.dockRevealed` с тестом — Task 6.
4. **Меню Quietline сохраняет поток сеанса.** Выход, перезагрузка, выключение — тот же `SessionService` с корректным закрытием приложений, отказами и отсчётом; блокировка — сразу. Task 4.
5. **Двуязычие и узкий экран.** Новые строки в обеих таблицах; на ширине < 820 px панель не переполняется (порядок ухода элементов — спека). Task 4.

## Файлы

- `config/hyprland/quietline.lua` — оформление окон, анимации, правила слоёв, hyprbars, `hyprpm reload -n`, правило `no_bar`.
- `installer/catalog.toml`, `packaging/arch/PKGBUILD`, `src/quietline_install/steps/` — пакеты и шаг `hyprpm`; `./install.sh update` → `hyprpm update`.
- `src/quietline_engine/` — только если тест покажет, что окна `special:` трогаются.
- `shell/quietline/Theme.qml` — токены варианта B.
- `shell/quietline/controls/`, `inputs/` — элементы: значок Material Symbols, кнопка, пункт меню, всплывающее окно, подсказка, полоса прокрутки, сегмент, переключатель, ползунок, поле.
- `shell/quietline/bar/TopBar.qml` (+ `bar/QuietlineMenu.qml`), `session/` — диалог подтверждения вместо меню питания.
- `shell/quietline/panels/QuickSettings.qml` и соседние — пункт управления.
- `shell/quietline/dock/Dock.qml` (+ полоса у края) — автоскрытие, свёрнутые окна.
- `shell/quietline/search/`, `clipboard/` — окна по центру.
- `shell/quietline/notifications/` — карточки, центр с календарём.
- `shell/quietline/settings/SettingsWindow.qml` — разделы и группы.
- `shell/quietline/osd/Osd.qml`, `lock/LockSurface.qml`, `LockScreen.qml`.
- `shell/quietline/services/DesktopModel.qml` — свёрнутые окна, сворачивание/возврат.
- `shell/quietline/logic/Models.js`, `Strings.js`; `tests/shell/*.test.cjs`, `tests/engine/`, `tests/install/`.
- Документация: `DESIGN.md`, основная спека, `AGENTS.md`, `README.md`, `CHANGELOG.md`, `docs/backlog.md`, `scripts/smoke-shell-redesign.md`.

## Task 0. Решения в репозитории

- [ ] Спека, план, макет B; `AGENTS.md`: роль `DESIGN.md` (стартовая точка; внешний вид оценивается вживую) и hyprbars через `hyprpm` в «Do not»/«Gotchas».

## Task 1. Живая проверка hyprbars и диспетчеров (стоп-условие)

Нужен пользователь: `sudo pacman -S hyprpm`, затем в терминале `hyprpm update && hyprpm add https://github.com/hyprwm/hyprland-plugins && hyprpm enable hyprbars` (hyprpm спрашивает пароль sudo).

- [ ] `hyprpm reload -n` загружает hyprbars на 0.57; `hl.plugin.hyprbars.add_button` и `hl.config({ plugin = { hyprbars = … } })` работают из `hyprctl eval`.
- [ ] Значки кнопок: кодовые точки Material Symbols (`U+E5CD`, `U+E3C6`, `U+E15B`) отрисовываются через подстановку шрифта; иначе — `✕ ▢ —`.
- [ ] Диспетчеры Lua: свернуть — переместить окно на `special:quietline-minimized` без перехода; вернуть — на пространство по id с фокусом; развернуть — `hl.dsp.window.fullscreen({ mode = "maximized", action = "toggle" })`. Точные имена записать сюда.
- [ ] Правило `hyprbars:no_bar` для не плавающих окон; рамка акцента для активного окна в «Тайлах» — правило по признаку плавающего окна или по тегу. Синтаксис записать сюда.
- [ ] Правило слоя с размытием по `namespace` (`quietline-*`) и `ignore_alpha`.
- [ ] Если что-то из этого недоступно — остановиться, поправить спеку и план вместе с пользователем.

## Task 2. Шрифты, токены, общие элементы

- [ ] `inter-font`, `ttf-material-symbols-variable`, `hyprpm` — в основу `catalog.toml` и `depends` PKGBUILD; тест каталога.
- [ ] `Theme.qml` — токены спеки (цвета, поверхности, скругления, длительности, кривая, шрифты `Inter`, `Material Symbols Rounded`, моно `JetBrains Mono`).
- [ ] `controls/Icon.qml` — значок по имени лигатуры, `filled`, `weight`, размер; `controls/` делится на `controls/` и `menus/` (или аналог), если записей больше восьми.
- [ ] `ShellButton` (плоская, подсветка `fillHover`, скругление 6), `ShellMenuItem` (26 px, выбор акцентом, сочетание справа), `HintPopup`, `ShellScrollBar` (тонкая, появляется при прокрутке), `ShellPopup` (поверхность `popup`, обводка `border`, скругление 14, появление 180 мс, `namespace` `quietline-popup`), сегмент `SegmentedControl`.
- [ ] `inputs/`: переключатель 38×22 (зелёный при включении), ползунок 24 px со значком внутри, поле с подложкой `fill`.
- [ ] Все глифы Nerd Font заменены на `Icon`; `Theme.icons`, `Theme.mono` для подписей — удалены. Живой снимок: оболочка запускается, ничего не рисуется квадратами.

## Task 3. Окна Hyprland, hyprbars, сворачивание

- [ ] `quietline.lua`: `decoration`, `general` (рамки, отступы), анимации, правила слоёв; запуск `hyprpm reload -n`; блок hyprbars под проверкой `hl.plugin and hl.plugin.hyprbars`; правило `no_bar`; кнопки (свернуть — команда сворачивания из Task 1).
- [ ] Шаг установщика `hyprbars`: `hyprpm update`, `add` (если нет в `hyprpm list`), `enable hyprbars`; повторный запуск ничего не ломает; `update` выполняет `hyprpm update`. Тесты установщика на поддельной системе.
- [ ] Тест движка: окно на специальном пространстве (отрицательный id) не попадает в план переходов и не возвращается движком на обычное пространство.
- [ ] `DesktopModel`: окна на `special:quietline-minimized` помечены `minimized`; `activate` приложения со свёрнутыми окнами возвращает последнее на активное пространство монитора и даёт фокус; `minimize(window)`.
- [ ] Живая проверка: заголовки в «Окнах», нет в «Тайлах»; кнопки; двойной щелчок; `hyprpm disable hyprbars` → конфигурация без ошибок.

## Task 4. Верхняя панель, меню Quietline, диалоги

- [ ] `TopBar.qml` по спеке: 30 px вплотную, `exclusiveZone` 30, `namespace` `quietline-bar`; элементы слева и справа; сегмент режима с прежней логикой занятости движка; батарея-ячейка; дата/время по `Lang`; порядок ухода на узком экране.
- [ ] `bar/QuietlineMenu.qml` — меню Quietline; IPC `showSummary` открывает пункт управления, `showApplications` — поиск.
- [ ] `session/`: `PowerMenu` → диалог подтверждения по центру (`SessionDialog`) с прежним потоком `SessionService`; `KillConfirm` — тем же диалогом; «Сон» — `systemctl suspend`.
- [ ] Строки обеих таблиц; тесты моделей для новых чистых функций (формат даты панели, порядок ухода элементов).

## Task 5. Пункт управления

- [x] `QuickSettings.qml` — сетка модулей по спеке: плитки (Wi‑Fi, Bluetooth, VPN; «Не беспокоить», «Не засыпать», «Снимок экрана»), развёртывание списков сетей и устройств, ползунки, профиль питания, CPU/RAM, строка батареи и «Настройки…».
- [x] Плитки VPN нет (спека, «Пункт управления»).

## Task 6. Док

- [ ] `Models.dockRevealed(state)` — чистая функция видимости (режим, полноэкранное окно, указатель у края, меню, перетаскивание, клавиатура, пустое пространство) с тестами.
- [ ] `Dock.qml`: без `exclusiveZone`; полоса 2 px у нижнего края (отдельное окно-слой без резерва); выезд 320 мс, скрытие через 400 мс; вид по спеке; полая точка у свёрнутых; `namespace` `quietline-dock`.

## Task 7. Поиск и буфер

- [ ] `SearchPanel` — окно по центру (своё `PanelWindow`-наложение или `ShellPopup` с центровкой), группы результатов, значки приложений, строка вычисления; `Models` — группировка результатов с тестом.
- [ ] `ClipboardPanel` — окно по центру: поле, список с типом и источником, предпросмотр.

## Task 8. Уведомления

- [ ] `NotificationPopups` — карточки по спеке (значок приложения, действия, крестик при наведении), `namespace` `quietline-notifications`.
- [ ] `NotificationCenter` — календарь месяца (`Models.monthGrid` с тестом), «Не беспокоить», стопки по приложению, «Очистить всё».

## Task 9. Окно «Настройки»

- [ ] Боковая панель с поиском и цветными значками разделов; группы-блоки; разделы VPN и «Уведомления»; прежние компоненты `panels/` в новом виде.

## Task 10. Индикатор и блокировка

- [ ] `Osd.qml` — капсула внизу по центру.
- [ ] `LockSurface.qml` — размытый снимок экрана, дата и время, аватар, поле-капсула, состояние справа сверху.

## Task 11. Документация и проверка

- [ ] `DESIGN.md` — переписан под вариант B; основная спека — пункты «Что переносится»; `README.md` (статус, этапы), `CHANGELOG.md` (Added/Changed/Removed и Breaking: кнопки питания и поиска на панели больше нет — меню Quietline и `Super+Space`).
- [ ] `scripts/smoke-shell-redesign.md`, `docs/backlog.md`; макет A остаётся как история в git, ссылка в спеке первой версии меняется на B.
- [ ] Ревью по Review Focus с запуском тестов; слияние в `main` по `AGENTS.md`.
