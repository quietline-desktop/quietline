-- Quietline: движок пространств и окон, его клавиши и оболочка Quickshell для Hyprland ≥ 0.55.
-- Подключается из ~/.config/hypr/hyprland.lua строкой require("quietline").
--
-- Внимание: стандартный пример конфигурации Hyprland привязывает SUPER + M к выходу
-- из Hyprland и сам привязывает SUPER + 1…0 и SUPER + SHIFT + 1…0 к пространствам.
-- Эти строки примера удаляются из hyprland.lua до подключения этого файла: иначе
-- SUPER + M закрывает сеанс, а цифровые клавиши конфликтуют с клавишами движка.

-- Все пространства в раскладке scrolling: режим «Окна» держит обычные окна плавающими,
-- режим «Тайлы» возвращает их в колонки. Новая колонка занимает половину рабочей области;
-- единственная колонка не растягивается на весь экран.
hl.config({
    general = { layout = "scrolling" },
    scrolling = { column_width = 0.5, fullscreen_on_one_column = false },
})

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
hl.on("hyprland.start", function ()
    hl.exec_cmd("quietline-engine serve")
    hl.exec_cmd("qs -c quietline")
end)

-- Терминал запускает сам Hyprland: работает без сервиса движка и без панели.
hl.bind("SUPER + Return", hl.dsp.exec_cmd("ghostty"))

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

-- Меню приложений оболочки на мониторе с фокусом, поле поиска в фокусе.
hl.bind("SUPER + Space", hl.dsp.exec_cmd("qs -c quietline ipc call quietline launcher"))

-- Окно «Настройки» оболочки на последнем открытом разделе.
hl.bind("SUPER + I", hl.dsp.exec_cmd("qs -c quietline ipc call quietline settings ''"))
