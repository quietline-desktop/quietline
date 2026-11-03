# Обновление Quietline и приложений

Каждый источник обновляется своим способом. Предварительные версии автоматически не ставятся. Подсказка по всем способам — `./install.sh update`.

| Что | Как |
| --- | --- |
| Пакеты Arch, включая Hyprland и Quickshell | `sudo pacman -Syu` |
| Quietline | `git pull` в клоне, затем `./install.sh update`: пересобирает пакет `quietline`, если он собран не из текущего коммита клона (версия — `<версия>.r<число коммитов>.g<хеш>`); то же делает шаг «Пакет Quietline» полного `./install.sh` |
| Пакеты Arch и все программы из AUR, в том числе поставленные вами | `yay` — обновляет всё сразу, перед сборкой пакета AUR показывает изменения его инструкций |
| Программы из AUR каталога (Chrome, VS Code, 1Password, Slack, Docker Desktop, yay) | тот же `./install.sh update` — показывает обновлённые инструкции сборки и собирает только после подтверждения |
| Программы из Flathub (Brave, ONLYOFFICE) | `flatpak update --user` |
| Версии Node.js | `fnm install <версия>`, `fnm default <версия>` |
| Версии Python | `uv python install <версия>` |
| AmneziaVPN | новый стабильный `.run` со страницы выпусков AmneziaVPN |

После обновления пакета `quietline` Hyprland и оболочка продолжают работать со старыми файлами: Hyprland не следит за `/usr/share/quietline/hyprland/quietline.lua`, подключённым через `dofile`. Новая конфигурация (клавиши, заголовки окон, тени) применяется командой `hyprctl reload`, оболочка — перезапуском `pkill -fx 'qs -c quietline'; hyprctl dispatch 'hl.dsp.exec_cmd("qs -c quietline")'` (не `pkill -x qs`: экран блокировки — тоже процесс `qs`, и заблокированный сеанс остался бы без него). Надёжнее всего выйти из сеанса и войти снова: тогда же подхватываются новые правила fontconfig.

Повторный `./install.sh` открывает каталог: установленное отмечено и неактивно, можно добавить новые программы. Удалять программы установщик не умеет — это делается обычными средствами (`pacman -Rns`, `flatpak uninstall --user`).

## Форк hyprland-plugins

Заголовки окон собираются из форка [quietline-desktop/hyprland-plugins](https://github.com/quietline-desktop/hyprland-plugins): это `main` апстрима hyprwm и поверх него коммиты Quietline (цвета кнопок под указателем, плавный переход, центровка значков). Когда hyprwm подстраивает плагины под новый Hyprland, форк надо догнать, иначе после обновления Hyprland `hyprpm update` не соберёт hyprbars и окна останутся без заголовков (остальное работает). В клоне форка (`origin` — форк, `upstream` — hyprwm):

```sh
git fetch upstream
git rebase upstream/main          # конфликт — чаще всего в hyprbars/barDeco.cpp
make -C hyprbars all              # проверка сборки; заголовки Hyprland — PKG_CONFIG_PATH=/var/cache/hyprpm/$USER/headersRoot/share/pkgconfig
git push --force-with-lease origin main
hyprpm update
```

Если форк уже догнан, а Hyprland в Arch ещё старый, hyprpm берёт закреплённую в `hyprpm.toml` версию апстрима: кнопки серые без подсветки до обновления Hyprland.

## Перед обновлением Hyprland

Quietline управляет окнами через Lua-команды Hyprland и встроенную раскладку `scrolling`; нативного модуля с привязкой к ABI нет. Перед `pacman -Syu` или `yay`, которые обновляют Hyprland, прочитай заметки к выпуску. После обновления пройди [smoke-window-engine.md](../../scripts/smoke-window-engine.md): локальные пространства, «Окна ↔ Тайлы», ширина и порядок колонок, диалоги, отключение монитора. Если что-то сломалось, верни прошлую версию из кэша: `sudo pacman -U /var/cache/pacman/pkg/hyprland-<версия>-x86_64.pkg.tar.zst`.
