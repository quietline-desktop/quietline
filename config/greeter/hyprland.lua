-- Hyprland экрана входа Quietline: его запускает `quietline-greeter` от пользователя greeter.
-- Внутри работает только Quickshell с `Greeter.qml`; когда он завершается, закрывается и
-- Hyprland. Если Quickshell завершился ошибкой, создаётся метка `QUIETLINE_GREETER_FAILED`, и
-- `quietline-greeter` открывает tuigreet. Ctrl+Alt+Backspace делает то же вручную.

hl.config({
    misc = {
        disable_hyprland_logo = true,
        disable_splash_rendering = true,
        disable_hyprland_guiutils_check = true,
    },
    ecosystem = { no_update_news = true, no_donation_nag = true },
    general = { border_size = 0 },
    -- Раскладки как у сеанса Quietline по умолчанию: us и ru, переключение левыми Alt+Shift.
    input = { kb_layout = "us,ru", kb_options = "grp:lalt_lshift_toggle" },
})

-- Все мониторы — в родном разрешении, масштаб выбирает Hyprland.
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })

local greeter = "/usr/share/quietline/greeter/run-ui"
local fail = 'touch "$QUIETLINE_GREETER_FAILED"'
local exit = [[hyprctl dispatch "hl.dsp.exit()"]]

hl.on("hyprland.start", function ()
    hl.exec_cmd(greeter)
end)

hl.bind("CTRL + ALT + BackSpace", hl.dsp.exec_cmd("sh -c '" .. fail .. "; " .. exit .. "'"),
    { description = "quietline-greeter:text-login" })
