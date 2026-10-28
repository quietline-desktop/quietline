-- Quietline: движок пространств и окон, его клавиши и оболочка Quickshell для Hyprland ≥ 0.55.
-- Подключается из ~/.config/hypr/hyprland.lua строкой dofile("/usr/share/quietline/hyprland/quietline.lua").
--
-- Внимание: стандартный пример конфигурации Hyprland сам привязывает клавиши, которые
-- здесь заняты: SUPER + M (выход из Hyprland), SUPER + 1…0 и SUPER + SHIFT + 1…0,
-- SUPER + Q, C, E, V, стрелки, SUPER + мышь. Все привязки примера удаляются из
-- hyprland.lua до подключения этого файла: иначе SUPER + M закрывает сеанс, а остальные
-- клавиши конфликтуют с клавишами Quietline.

-- Все пространства в раскладке scrolling: режим «Окна» держит обычные окна плавающими,
-- режим «Тайлы» возвращает их в колонки. Новая колонка занимает половину рабочей области;
-- единственная колонка не растягивается на весь экран. Упавший экран блокировки можно
-- запустить заново: сеанс при этом остаётся заблокированным.
hl.config({
    general = { layout = "scrolling" },
    scrolling = { column_width = 0.5, fullscreen_on_one_column = false },
    misc = { allow_session_lock_restore = true },
})

-- Раскладки us и ru и сочетание их переключения. Оболочка пишет выбор в файл
-- quietline/keyboard.lua каталога настроек: он возвращает таблицу с kb_layout и kb_options.
-- Без файла или при ошибке в нём — us,ru и левые Alt+Shift.
local config_home = os.getenv("XDG_CONFIG_HOME")
if not config_home or config_home == "" then
    config_home = (os.getenv("HOME") or "") .. "/.config"
end
local keyboard = { kb_layout = "us,ru", kb_options = "grp:lalt_lshift_toggle" }
local loaded, chosen = pcall(dofile, config_home .. "/quietline/keyboard.lua")
if loaded and type(chosen) == "table"
    and type(chosen.kb_layout) == "string" and type(chosen.kb_options) == "string" then
    keyboard = chosen
end
hl.config({ input = { kb_layout = keyboard.kb_layout, kb_options = keyboard.kb_options } })

-- Модальные окна плавают и получают тег quietline-modal; движок видит теги в
-- hyprctl -j clients и такие окна не переставляет.
hl.window_rule({
    name = "quietline-modals",
    match = { modal = true },
    float = true,
    tag = "+quietline-modal",
})

-- Окно, которое Hyprland сам открыл плавающим (диалог, служебное окно фиксированного
-- размера), получает тег quietline-native-float: движок считает его диалогом.
hl.on("window.open", function (window)
    if window.floating then
        hl.dispatch(hl.dsp.window.tag({
            window = "address:" .. window.address,
            tag = "+quietline-native-float",
        }))
    end
end)

-- Сервис движка и оболочка стартуют вместе с Hyprland отдельными процессами: сбой
-- оболочки не останавливает движок и клавиши, оболочка сама переподключается к движку.
-- История буфера пишут наблюдатели wl-paste за текстом и картинками; индекс файлов
-- домашнего каталога для поиска строится при входе.
hl.on("hyprland.start", function ()
    hl.exec_cmd("quietline-engine serve")
    hl.exec_cmd("qs -c quietline")
    hl.exec_cmd("wl-paste --type text --watch quietline-shell clipboard store")
    hl.exec_cmd("wl-paste --type image --watch quietline-shell clipboard store")
    hl.exec_cmd("quietline-shell files --update")
end)

-- Терминал запускает сам Hyprland: работает без сервиса движка и без панели.
hl.bind("SUPER + Return", hl.dsp.exec_cmd("ghostty"))

-- Блокировка — отдельный процесс экрана блокировки, работает без панели; привязка
-- действует и на заблокированном экране, чтобы поднять упавший экран блокировки.
hl.bind("SUPER + L", hl.dsp.exec_cmd("quietline-shell lock"), { locked = true })

-- Закрыть активное окно; корректно выйти из приложения со всеми окнами; принудительно
-- завершить его процесс — только после подтверждения на панели.
hl.bind("SUPER + W", hl.dsp.window.close())
hl.bind("SUPER + Q", hl.dsp.exec_cmd("quietline-shell app quit --notify"))
hl.bind("SUPER + SHIFT + Q", hl.dsp.exec_cmd("qs -c quietline ipc call quietline confirmKill"))

-- История буфера: поиск по записям, выбранная возвращается в буфер.
hl.bind("SUPER + V", hl.dsp.exec_cmd("qs -c quietline ipc call quietline clipboard"))

-- Снимок монитора с фокусом в файл и буфер; область экрана с разметкой в Satty.
hl.bind("Print", hl.dsp.exec_cmd("quietline-shell screenshot output"))
hl.bind("SUPER + SHIFT + S", hl.dsp.exec_cmd("quietline-shell screenshot region"))

-- Dolphin; памятка сочетаний — раздел окна «Настройки».
hl.bind("SUPER + E", hl.dsp.exec_cmd("dolphin"))
hl.bind("SUPER + F1", hl.dsp.exec_cmd("qs -c quietline ipc call quietline settings shortcuts"))

-- Фокус соседнего окна: в «Тайлах» влево/вправо — соседняя колонка, вверх/вниз — окно в колонке.
hl.bind("SUPER + Left", hl.dsp.focus({ direction = "l" }))
hl.bind("SUPER + Right", hl.dsp.focus({ direction = "r" }))
hl.bind("SUPER + Up", hl.dsp.focus({ direction = "u" }))
hl.bind("SUPER + Down", hl.dsp.focus({ direction = "d" }))

-- Плавающее окно сдвигается на NUDGE пикселей, окно в колонках переставляется в сторону.
local NUDGE = 40
local function move_or_nudge(direction, dx, dy)
    return function ()
        local window = hl.get_active_window()
        if window and window.floating then
            hl.dispatch(hl.dsp.window.move({ x = dx, y = dy, relative = true }))
        else
            hl.dispatch(hl.dsp.window.move({ direction = direction }))
        end
    end
end
hl.bind("SUPER + SHIFT + Left", move_or_nudge("l", -NUDGE, 0))
hl.bind("SUPER + SHIFT + Right", move_or_nudge("r", NUDGE, 0))
hl.bind("SUPER + SHIFT + Up", move_or_nudge("u", 0, -NUDGE))
hl.bind("SUPER + SHIFT + Down", move_or_nudge("d", 0, NUDGE))

-- Фокус соседнего монитора.
hl.bind("SUPER + ALT + Left", hl.dsp.focus({ monitor = "l" }))
hl.bind("SUPER + ALT + Right", hl.dsp.focus({ monitor = "r" }))

-- Временно вынуть окно из колонки и вернуть обратно; движок не трогает такое окно до смены режима.
hl.bind("SUPER + ALT + Space", hl.dsp.window.float({ action = "toggle" }))

-- Развернуть в рабочей области / настоящий полноэкранный режим.
hl.bind("SUPER + F", hl.dsp.window.fullscreen({ mode = "maximized" }))
hl.bind("SUPER + SHIFT + F", hl.dsp.window.fullscreen({ mode = "fullscreen" }))

-- Следующее окно текущего пространства, поверх остальных.
hl.bind("ALT + Tab", function ()
    hl.dispatch(hl.dsp.window.cycle_next())
    hl.dispatch(hl.dsp.window.bring_to_top())
end)

-- Super + левая кнопка мыши двигает окно, правая — меняет размер.
hl.bind("SUPER + mouse:272", hl.dsp.window.drag(), { mouse = true })
hl.bind("SUPER + mouse:273", hl.dsp.window.resize(), { mouse = true })

-- Локальные пространства 1–10 монитора с фокусом; клавиша 0 — пространство 10.
hl.bind("SUPER + 1", hl.dsp.exec_cmd("quietline-engine switch 1"))
hl.bind("SUPER + 2", hl.dsp.exec_cmd("quietline-engine switch 2"))
hl.bind("SUPER + 3", hl.dsp.exec_cmd("quietline-engine switch 3"))
hl.bind("SUPER + 4", hl.dsp.exec_cmd("quietline-engine switch 4"))
hl.bind("SUPER + 5", hl.dsp.exec_cmd("quietline-engine switch 5"))
hl.bind("SUPER + 6", hl.dsp.exec_cmd("quietline-engine switch 6"))
hl.bind("SUPER + 7", hl.dsp.exec_cmd("quietline-engine switch 7"))
hl.bind("SUPER + 8", hl.dsp.exec_cmd("quietline-engine switch 8"))
hl.bind("SUPER + 9", hl.dsp.exec_cmd("quietline-engine switch 9"))
hl.bind("SUPER + 0", hl.dsp.exec_cmd("quietline-engine switch 10"))

-- Активное окно переезжает на локальное пространство того же монитора, фокус — за ним.
hl.bind("SUPER + SHIFT + 1", hl.dsp.exec_cmd("quietline-engine move 1"))
hl.bind("SUPER + SHIFT + 2", hl.dsp.exec_cmd("quietline-engine move 2"))
hl.bind("SUPER + SHIFT + 3", hl.dsp.exec_cmd("quietline-engine move 3"))
hl.bind("SUPER + SHIFT + 4", hl.dsp.exec_cmd("quietline-engine move 4"))
hl.bind("SUPER + SHIFT + 5", hl.dsp.exec_cmd("quietline-engine move 5"))
hl.bind("SUPER + SHIFT + 6", hl.dsp.exec_cmd("quietline-engine move 6"))
hl.bind("SUPER + SHIFT + 7", hl.dsp.exec_cmd("quietline-engine move 7"))
hl.bind("SUPER + SHIFT + 8", hl.dsp.exec_cmd("quietline-engine move 8"))
hl.bind("SUPER + SHIFT + 9", hl.dsp.exec_cmd("quietline-engine move 9"))
hl.bind("SUPER + SHIFT + 0", hl.dsp.exec_cmd("quietline-engine move 10"))

-- Режим текущего пространства: «Окна» ↔ «Тайлы».
hl.bind("SUPER + M", hl.dsp.exec_cmd("quietline-engine toggle"))

-- Поиск оболочки на мониторе с фокусом: приложения, файлы, действия, вычисления.
hl.bind("SUPER + Space", hl.dsp.exec_cmd("qs -c quietline ipc call quietline launcher"))

-- Окно «Настройки» оболочки на последнем открытом разделе.
hl.bind("SUPER + I", hl.dsp.exec_cmd("qs -c quietline ipc call quietline settings ''"))
