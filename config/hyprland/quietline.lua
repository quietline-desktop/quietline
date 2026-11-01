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

-- Оформление окон варианта B: скругление 10, тонкая светлая рамка, мягкая тень, отступы 4/8.
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
            range = 24,
            render_power = 3,
            offset = "0 8",
            color = "rgba(00000073)",
            color_inactive = "rgba(00000059)",
        },
        blur = { enabled = true, size = 8, passes = 3, noise = 0.02, vibrancy = 0.17 },
    },
})

-- Окна появляются из 96 % масштаба, пространства сдвигаются; кривая — та же, что у оболочки.
hl.curve("quietline", { type = "bezier", points = { { 0.2, 0.9 }, { 0.3, 1 } } })
hl.animation({ leaf = "windowsIn", enabled = true, speed = 2.5, bezier = "quietline", style = "popin 96%" })
hl.animation({ leaf = "workspaces", enabled = true, speed = 3, bezier = "quietline", style = "slide" })

-- Поверхности оболочки (namespace quietline-*) размываются под собой. Размывается только
-- плотная поверхность (непрозрачность от 0.4): тень вокруг всплывающих окон прозрачнее и не
-- размывается. Появление и скрытие анимирует сама оболочка. Шаблон namespace сравнивается
-- со всей строкой.
hl.layer_rule({
    name = "quietline-surfaces",
    match = { namespace = "quietline-.*" },
    blur = true,
    ignore_alpha = 0.4,
    no_anim = true,
})

-- В «Тайлах» у окон нет заголовков и теней в колонках: активное окно выделено рамкой
-- акцента 2 px. Правило динамическое: плавающее окно возвращает обычную рамку.
hl.window_rule({
    name = "quietline-tiled-border",
    match = { float = false },
    border_size = 2,
    border_color = "rgba(0a84ffd9) rgba(ffffff14)",
})

-- Заголовки плавающих окон — плагин hyprbars (hyprland-plugins, ставится и собирается через
-- hyprpm). Плагин грузится при старте (`hyprpm reload`) и после загрузки сам перечитывает
-- конфигурацию; без него, например после обновления Hyprland до `hyprpm update`, этот блок
-- пропускается и окна остаются без заголовков. Кнопки справа налево: «закрыть» на красном
-- кружке, «развернуть», «свернуть» на прозрачной подложке; значки — символы «×», «□», «−»
-- из Inter (символы личной области Unicode hyprbars берёт из Nerd Font, а там другие глифы).
-- У неактивного окна подложка всех кнопок почти прозрачна, красный кружок пропадает.
-- «Свернуть» уносит окно на скрытое пространство special:quietline-minimized, вернуть его
-- можно из дока. В колонках «Тайлов» заголовков нет.
if hl.plugin and hl.plugin.hyprbars then
    hl.config({
        plugin = {
            hyprbars = {
                bar_height = 32,
                bar_color = "rgb(2b2b30)",
                ["col.text"] = "rgba(ffffffd1)",
                bar_text_font = "Inter",
                bar_text_size = 12,
                bar_text_weight = "semibold",
                bar_text_align = "center",
                bar_buttons_alignment = "right",
                bar_padding = 8,
                bar_button_padding = 6,
                bar_part_of_window = true,
                bar_precedence_over_border = true,
                inactive_button_color = "rgba(ffffff01)",
                on_double_click = [[hyprctl dispatch 'hl.dsp.window.fullscreen({ mode = "maximized", action = "toggle" })']],
            },
        },
    })
    hl.plugin.hyprbars.add_button({
        bg_color = "rgb(e5484d)",
        fg_color = "rgb(ffffff)",
        size = 20,
        icon = "\u{00D7}",
        action = [[hyprctl dispatch 'hl.dsp.window.close()']],
    })
    hl.plugin.hyprbars.add_button({
        bg_color = "rgba(00000000)",
        fg_color = "rgba(ffffffcc)",
        size = 22,
        icon = "\u{25A1}",
        action = [[hyprctl dispatch 'hl.dsp.window.fullscreen({ mode = "maximized", action = "toggle" })']],
    })
    hl.plugin.hyprbars.add_button({
        bg_color = "rgba(00000000)",
        fg_color = "rgba(ffffffcc)",
        size = 22,
        icon = "\u{2212}",
        action = [[hyprctl dispatch 'hl.dsp.window.move({ workspace = "special:quietline-minimized", follow = false })']],
    })
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

-- Громкость (до 150 %), звук и микрофон, яркость встроенного экрана шагом 5 %: меняют сами
-- утилиты, поэтому клавиши работают и без оболочки и на заблокированном экране; громкость и
-- яркость повторяются при удержании. Индикатор громкости оболочка показывает сама по
-- изменению PipeWire, яркости — по вызову `osd brightness`.
hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd("wpctl set-volume -l 1.5 @DEFAULT_AUDIO_SINK@ 5%+"), { locked = true, repeating = true })
hl.bind("XF86AudioLowerVolume", hl.dsp.exec_cmd("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"), { locked = true, repeating = true })
hl.bind("XF86AudioMute", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"), { locked = true })
hl.bind("XF86AudioMicMute", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"), { locked = true })
hl.bind("XF86MonBrightnessUp", hl.dsp.exec_cmd("brightnessctl -c backlight --min-value=1 set 5%+ && qs -c quietline ipc call quietline osd brightness"), { locked = true, repeating = true })
hl.bind("XF86MonBrightnessDown", hl.dsp.exec_cmd("brightnessctl -c backlight --min-value=1 set 5%- && qs -c quietline ipc call quietline osd brightness"), { locked = true, repeating = true })

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

-- Центр уведомлений оболочки на мониторе с фокусом.
hl.bind("SUPER + N", hl.dsp.exec_cmd("qs -c quietline ipc call quietline notifications"))

-- Окно «Настройки» оболочки на последнем открытом разделе.
hl.bind("SUPER + I", hl.dsp.exec_cmd("qs -c quietline ipc call quietline settings ''"))
