# Обновление Quietline и приложений

Каждый источник обновляется своим способом. Предварительные версии автоматически не ставятся. Подсказка по всем способам — `./install.sh update`.

| Что | Как |
| --- | --- |
| Пакеты Arch, включая Hyprland и Quickshell | `sudo pacman -Syu` |
| Quietline | `git pull` в клоне, затем `./install.sh`: шаг «Пакет Quietline» пересобирает пакет при каждом новом коммите (версия — `<версия>.r<число коммитов>.g<хеш>`) |
| Программы из AUR (Chrome, VS Code, 1Password, Slack, WeChat) | `./install.sh update` — показывает обновлённые инструкции сборки и собирает только после подтверждения |
| Программы из Flathub (Brave, ONLYOFFICE) | `flatpak update --user` |
| Версии Node.js | `fnm install <версия>`, `fnm default <версия>` |
| Версии Python | `uv python install <версия>` |
| Docker Desktop | новый пакет со страницы Docker для Arch: `sudo pacman -U ./docker-desktop-x86_64.pkg.tar.zst` |
| AmneziaVPN | новый стабильный `.run` со страницы выпусков AmneziaVPN |

Повторный `./install.sh` открывает каталог: установленное отмечено и неактивно, можно добавить новые программы. Удалять программы установщик не умеет — это делается обычными средствами (`pacman -Rns`, `flatpak uninstall --user`).

## Перед обновлением Hyprland

Quietline управляет окнами через Lua-команды Hyprland и встроенную раскладку `scrolling`; нативного модуля с привязкой к ABI нет. Перед `pacman -Syu`, который обновляет Hyprland, прочитай заметки к выпуску. После обновления пройди [smoke-window-engine.md](../../scripts/smoke-window-engine.md): локальные пространства, «Окна ↔ Тайлы», ширина и порядок колонок, диалоги, отключение монитора. Если что-то сломалось, верни прошлую версию из кэша: `sudo pacman -U /var/cache/pacman/pkg/hyprland-<версия>-x86_64.pkg.tar.zst`.
