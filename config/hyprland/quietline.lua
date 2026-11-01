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
-- запустить заново: сеанс при этом остаётся заблокированным. Погашенные по простою
-- экраны включаются любым нажатием клавиши или движением мыши.
hl.config({
    general = { layout = "scrolling" },
    scrolling = { column_width = 0.5, fullscreen_on_one_column = false },
    misc = { allow_session_lock_restore = true, key_press_enables_dpms = true, mouse_move_enables_dpms = true },
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

-- Оформление окон варианта B: скругление 10, тонкая светлая рамка, отступы 4/8. Тень мягкая
-- и почти равномерная со всех сторон (сдвиг вниз 3 px), у неактивного окна — вдвое слабее.
-- Размытие включено для полупрозрачных поверхностей оболочки (правило слоёв ниже); у окон
-- приложений фон непрозрачный, им размытие не мешает.
hl.config({
    general = {
        border_size = 1,
        gaps_in = 4,
        gaps_out = 8,
        col = { active_border = "rgba(ffffff29)", inactive_border = "rgba(ffffff14)" },
    },
    decoration = {
        rounding = 10,
        rounding_power = 2,
        shadow = {
            enabled = true,
            range = 18,
            render_power = 3,
            offset = "0 3",
            color = "rgba(0000004d)",
            color_inactive = "rgba(00000026)",
        },
        blur = { enabled = true, size = 8, passes = 3, noise = 0.02, vibrancy = 0.17 },
    },
})

-- Окна появляются из 96 % масштаба, пространства сдвигаются; кривая — та же, что у оболочки.
hl.curve("quietline", { type = "bezier", points = { { 0.2, 0.9 }, { 0.3, 1 } } })
hl.animation({ leaf = "windowsIn", enabled = true, speed = 2.5, bezier = "quietline", style = "popin 96%" })
hl.animation({ leaf = "workspaces", enabled = true, speed = 3, bezier = "quietline", style = "slide" })

-- Панель, всплывающие окна, док, индикатор и уведомления оболочки размываются под собой.
-- Размывается только плотная поверхность (непрозрачность от 0.4): тень вокруг всплывающих
-- окон прозрачнее и не размывается. Диалог с затемнением экрана (quietline-dialog) не
-- размывается: затемнение вместе с тенью плотнее порога и размылось бы прямоугольником.
-- Появление и скрытие анимирует сама оболочка. Шаблон namespace сравнивается со всей строкой.
hl.layer_rule({
    name = "quietline-surfaces",
    match = { namespace = "quietline-(bar|popup|dock|osd|notifications)" },
    blur = true,
    ignore_alpha = 0.4,
    no_anim = true,
})

-- В «Тайлах» у окон нет заголовков и теней в колонках: активное окно выделено рамкой
-- акцента 2 px. Правило динамическое: плавающее окно возвращает обычную рамку и тень.
hl.window_rule({
    name = "quietline-tiled-border",
    match = { float = false },
    border_size = 2,
    border_color = "rgba(0a84ffd9) rgba(ffffff14)",
    no_shadow = true,
})

-- Заголовки плавающих окон — плагин hyprbars (форк quietline-desktop/hyprland-plugins, ставится и собирается через
-- hyprpm). Плагин грузится при старте (`hyprpm reload`) и после загрузки сам перечитывает
-- конфигурацию; без него, например после обновления Hyprland до `hyprpm update`, этот блок
-- пропускается и окна остаются без заголовков. Кнопки справа налево: «закрыть», «развернуть»,
-- «свернуть» — одинаковые серые значки на прозрачной подложке; значки — кодовые точки Material
-- Symbols (close, crop_square, horizontal_rule; в Inter точки нет). Шрифт «Quietline Titlebar» — правило fontconfig
-- пакета (50-quietline-titlebar.conf): название окна — Inter, значки — Material Symbols
-- Rounded раньше запасных шрифтов, где те же точки заняты другими глифами.
-- Под указателем кнопка получает кружок — «закрыть» красный, остальные светло-серый — и белый
-- значок (`hover_bg_color`, `hover_fg_color`); цвет появляется и гаснет за 120 мс (`hover_fade`).
-- Крестик крупнее, квадрат мельче (`icon_size`), чтобы три значка выглядели соразмерно.
-- hyprbars без этих возможностей поля кнопок пропускает, `hover_fade` задаётся, только если
-- плагин его знает (`hl.get_config`), и кнопки остаются серыми без подсветки.
-- «Свернуть» уносит окно на скрытое пространство special:quietline-minimized, вернуть его
-- можно из дока. В колонках «Тайлов» заголовков нет.
if hl.plugin and hl.plugin.hyprbars then
    hl.config({
        plugin = {
            hyprbars = {
                bar_height = 32,
                bar_color = "rgb(2b2b30)",
                ["col.text"] = "rgba(ffffffd1)",
                bar_text_font = "Quietline Titlebar",
                bar_text_size = 13,
                bar_text_weight = "semibold",
                bar_text_align = "center",
                bar_buttons_alignment = "right",
                bar_padding = 8,
                bar_button_padding = 6,
                bar_part_of_window = true,
                bar_precedence_over_border = true,
                on_double_click = [[hyprctl dispatch 'hl.dsp.window.fullscreen({ mode = "maximized", action = "toggle" })']],
            },
        },
    })
    hl.plugin.hyprbars.add_button({
        bg_color = "rgba(00000000)",
        fg_color = "rgba(ffffffcc)",
        hover_bg_color = "rgb(e5484d)",
        hover_fg_color = "rgb(ffffff)",
        size = 26,
        icon_size = 19,
        icon = "\u{E5CD}",
        action = [[hyprctl dispatch 'hl.dsp.window.close()']],
    })
    hl.plugin.hyprbars.add_button({
        bg_color = "rgba(00000000)",
        fg_color = "rgba(ffffffcc)",
        hover_bg_color = "rgba(ffffff24)",
        hover_fg_color = "rgb(ffffff)",
        size = 26,
        icon_size = 14,
        icon = "\u{E3C6}",
        action = [[hyprctl dispatch 'hl.dsp.window.fullscreen({ mode = "maximized", action = "toggle" })']],
    })
    hl.plugin.hyprbars.add_button({
        bg_color = "rgba(00000000)",
        fg_color = "rgba(ffffffcc)",
        hover_bg_color = "rgba(ffffff24)",
        hover_fg_color = "rgb(ffffff)",
        size = 26,
        icon = "\u{F108}",
        action = [[hyprctl dispatch 'hl.dsp.window.move({ workspace = "special:quietline-minimized", follow = false })']],
    })
    if hl.get_config("plugin:hyprbars:hover_fade") ~= nil then
        hl.config({ plugin = { hyprbars = { hover_fade = 120 } } })
    end
    hl.window_rule({
        name = "quietline-tiled-no-bar",
        match = { float = false },
        ["hyprbars:no_bar"] = true,
    })
end

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
-- домашнего каталога для поиска строится при входе. Простоем и блокировкой перед сном
-- управляет hypridle: он работает и без оболочки.
hl.on("hyprland.start", function ()
    hl.exec_cmd("hyprpm reload -n")
    hl.exec_cmd("quietline-engine serve")
    hl.exec_cmd("qs -c quietline")
    hl.exec_cmd("hypridle -c /usr/share/quietline/hypridle/hypridle.conf")
    hl.exec_cmd("wl-paste --type text --watch quietline-shell clipboard store")
    hl.exec_cmd("wl-paste --type image --watch quietline-shell clipboard store")
    hl.exec_cmd("quietline-shell files --update")
end)

-- Привязки с описанием: `hyprctl binds -j` не показывает команду Lua-привязки, поэтому
-- памятка оболочки берёт действие из описания. `run` — команда, она же описание;
-- `act` — диспетчер или функция с описанием `quietline:<действие>`.
local function run(keys, command, opts)
    opts = opts or {}
    opts.description = command
    return hl.bind(keys, hl.dsp.exec_cmd(command), opts)
end
local function act(keys, action, name, opts)
    opts = opts or {}
    opts.description = "quietline:" .. name
    return hl.bind(keys, action, opts)
end

-- Терминал запускает сам Hyprland: работает без сервиса движка и без панели.
run("SUPER + Return", "ghostty")

-- Блокировка — отдельный процесс экрана блокировки, работает без панели; привязка
-- действует и на заблокированном экране, чтобы поднять упавший экран блокировки.
run("SUPER + L", "quietline-shell lock", { locked = true })

-- Закрыть активное окно; корректно выйти из приложения со всеми окнами; принудительно
-- завершить его процесс — только после подтверждения на панели.
act("SUPER + W", hl.dsp.window.close(), "close")
run("SUPER + Q", "quietline-shell app quit --notify")
run("SUPER + SHIFT + Q", "qs -c quietline ipc call quietline confirmKill")

-- История буфера: поиск по записям, выбранная возвращается в буфер.
run("SUPER + V", "qs -c quietline ipc call quietline clipboard")

-- Громкость (до 150 %), звук и микрофон, яркость встроенного экрана шагом 5 %: меняют сами
-- утилиты, поэтому клавиши работают и без оболочки и на заблокированном экране; громкость и
-- яркость повторяются при удержании. Индикатор громкости оболочка показывает сама по
-- изменению PipeWire, яркости — по вызову `osd brightness`.
run("XF86AudioRaiseVolume", "wpctl set-volume -l 1.5 @DEFAULT_AUDIO_SINK@ 5%+", { locked = true, repeating = true })
run("XF86AudioLowerVolume", "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-", { locked = true, repeating = true })
run("XF86AudioMute", "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle", { locked = true })
run("XF86AudioMicMute", "wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle", { locked = true })
run("XF86MonBrightnessUp", "brightnessctl -c backlight --min-value=1 set 5%+ && qs -c quietline ipc call quietline osd brightness", { locked = true, repeating = true })
run("XF86MonBrightnessDown", "brightnessctl -c backlight --min-value=1 set 5%- && qs -c quietline ipc call quietline osd brightness", { locked = true, repeating = true })

-- Снимок монитора с фокусом в файл и буфер; область экрана с разметкой в Satty.
run("Print", "quietline-shell screenshot output")
run("SUPER + SHIFT + S", "quietline-shell screenshot region")

-- Dolphin; памятка сочетаний — раздел окна «Настройки».
run("SUPER + E", "dolphin")
run("SUPER + F1", "qs -c quietline ipc call quietline settings shortcuts")

-- Фокус соседнего окна: в «Тайлах» влево/вправо — соседняя колонка, вверх/вниз — окно в колонке.
act("SUPER + Left", hl.dsp.focus({ direction = "l" }), "focus-left")
act("SUPER + Right", hl.dsp.focus({ direction = "r" }), "focus-right")
act("SUPER + Up", hl.dsp.focus({ direction = "u" }), "focus-up")
act("SUPER + Down", hl.dsp.focus({ direction = "d" }), "focus-down")

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
act("SUPER + SHIFT + Left", move_or_nudge("l", -NUDGE, 0), "move-left")
act("SUPER + SHIFT + Right", move_or_nudge("r", NUDGE, 0), "move-right")
act("SUPER + SHIFT + Up", move_or_nudge("u", 0, -NUDGE), "move-up")
act("SUPER + SHIFT + Down", move_or_nudge("d", 0, NUDGE), "move-down")

-- Фокус соседнего монитора.
act("SUPER + ALT + Left", hl.dsp.focus({ monitor = "l" }), "monitor-left")
act("SUPER + ALT + Right", hl.dsp.focus({ monitor = "r" }), "monitor-right")

-- Временно вынуть окно из колонки и вернуть обратно; движок не трогает такое окно до смены режима.
act("SUPER + ALT + Space", hl.dsp.window.float({ action = "toggle" }), "float")

-- Развернуть в рабочей области / настоящий полноэкранный режим.
act("SUPER + F", hl.dsp.window.fullscreen({ mode = "maximized" }), "maximize")
act("SUPER + SHIFT + F", hl.dsp.window.fullscreen({ mode = "fullscreen" }), "fullscreen")

-- Следующее окно текущего пространства, поверх остальных.
act("ALT + Tab", function ()
    hl.dispatch(hl.dsp.window.cycle_next())
    hl.dispatch(hl.dsp.window.bring_to_top())
end, "cycle")

-- Super + левая кнопка мыши двигает окно, правая — меняет размер.
act("SUPER + mouse:272", hl.dsp.window.drag(), "drag", { mouse = true })
act("SUPER + mouse:273", hl.dsp.window.resize(), "resize", { mouse = true })

-- Локальные пространства 1–10 монитора с фокусом; клавиша 0 — пространство 10.
run("SUPER + 1", "quietline-engine switch 1")
run("SUPER + 2", "quietline-engine switch 2")
run("SUPER + 3", "quietline-engine switch 3")
run("SUPER + 4", "quietline-engine switch 4")
run("SUPER + 5", "quietline-engine switch 5")
run("SUPER + 6", "quietline-engine switch 6")
run("SUPER + 7", "quietline-engine switch 7")
run("SUPER + 8", "quietline-engine switch 8")
run("SUPER + 9", "quietline-engine switch 9")
run("SUPER + 0", "quietline-engine switch 10")

-- Активное окно переезжает на локальное пространство того же монитора, фокус — за ним.
run("SUPER + SHIFT + 1", "quietline-engine move 1")
run("SUPER + SHIFT + 2", "quietline-engine move 2")
run("SUPER + SHIFT + 3", "quietline-engine move 3")
run("SUPER + SHIFT + 4", "quietline-engine move 4")
run("SUPER + SHIFT + 5", "quietline-engine move 5")
run("SUPER + SHIFT + 6", "quietline-engine move 6")
run("SUPER + SHIFT + 7", "quietline-engine move 7")
run("SUPER + SHIFT + 8", "quietline-engine move 8")
run("SUPER + SHIFT + 9", "quietline-engine move 9")
run("SUPER + SHIFT + 0", "quietline-engine move 10")

-- Режим текущего пространства: «Окна» ↔ «Тайлы».
run("SUPER + M", "quietline-engine toggle")

-- Поиск оболочки на мониторе с фокусом: приложения, файлы, действия, вычисления.
run("SUPER + Space", "qs -c quietline ipc call quietline launcher")

-- Центр уведомлений оболочки на мониторе с фокусом.
run("SUPER + N", "qs -c quietline ipc call quietline notifications")

-- Окно «Настройки» оболочки на последнем открытом разделе.
run("SUPER + I", "qs -c quietline ipc call quietline settings ''")
