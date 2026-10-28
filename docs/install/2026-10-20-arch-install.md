# Установка Arch Linux рядом с Windows — Lenovo 83ES

Гайд для текущего ноутбука и его разметки. Сверено 20 октября 2026 с ISO `archlinux-2026.10.01` (archinstall 4.5, ядро 7.2); схема Btrfs с `/efi` добавлена 28 октября 2026 по документации и исходному коду archinstall и вживую ещё не проверялась. Разметка, Secure Boot и загрузочные записи прочитаны с этой машины из Kubuntu. Основание — раздел «Установка на текущем компьютере» спецификации.

## Что на диске сейчас

`/dev/nvme0n1`, Micron 1 ТБ, GPT, UEFI 64-bit, **Secure Boot выключен**.

| Раздел | Размер | Что это | Что делаем |
| --- | --- | --- | --- |
| `p1` | 100 МБ | EFI Windows (Windows Boot Manager) | не трогаем |
| `p2` | 16 МБ | Microsoft reserved | не трогаем |
| `p3` | 249 ГБ | NTFS, Windows `C:` (BitLocker не включён) | не трогаем |
| `p4` | 745 МБ | Windows Recovery | не трогаем |
| `p5` | 350 ГБ | NTFS, данные | не трогаем |
| `p6` | 1 ГБ | EFI Kubuntu, занято 8 МБ | EFI-раздел Arch в `/efi`, **без форматирования** |
| `p7` | 16 ГБ | swap | swap Arch, без форматирования |
| `p8` | 337 ГБ | ext4, Kubuntu `/` и `/home` | **форматируем** в Btrfs с подтомами — корень Arch |

Железо: Intel Core i5-12450H со встроенной графикой Intel UHD (Alder Lake), Wi-Fi Intel CNVi, 16 ГБ ОЗУ, батарея, подсветка `intel_backlight`. Проводного порта нет: Ethernet только через USB-адаптер.

Загрузочные записи UEFI: `ubuntu` (`p6`, первая), `Windows Boot Manager` (`p1`), USB-флешка Ventoy.

## 1. До установки — в Kubuntu

### 1.1. Сохранить всё, что живёт только на `p8`

Форматирование `p8` уничтожит весь `/home`. Резервную копию кладём **не на этот диск**: в облако или на отдельный носитель (флешка Ventoy подходит только как временная, её легко перезаписать).

**Срочно — нет удалённой копии:**

- **Репозиторий `quietline`** лежит на GitHub (`lunasy26/quietline`, приватный): проверь, что локальных незапушенных коммитов нет — `git -C ~/Work/Personal/quietline status -sb`.
- **MarkTicket**: ветка `feature/staff-quick-view` (24 коммита) не отправлена на сервер — `git push -u origin feature/staff-quick-view` либо сохрани её через `git bundle create`.

**SSH** (`~/.ssh`): закрытого ключа в файлах нет, он хранится в 1Password и отдаётся через его агент (`~/.1password/agent.sock`). Сохраняются `config`, `known_hosts`, `markticket-dev.pub`. Отдельно убедись, что есть доступ к аккаунту 1Password с другого устройства или Emergency Kit: без них ключ не вернуть.

```sh
mkdir -p ~/backup
tar -C ~ -czf - .ssh | gpg --symmetric --cipher-algo AES256 -o ~/backup/ssh.tar.gz.gpg
gpg -d ~/backup/ssh.tar.gz.gpg | tar -tzf -    # проверка: список файлов читается
```

**Контрольный список остального** (отметить каждое как «сохранено» или «не нужно»):

- [ ] `~/Documents` (284 МБ), `~/Downloads` (482 МБ), `~/Desktop`
- [ ] `~/Work/powerchainger` — это не git-репозиторий (папка `projects` и архив `.7z`)
- [ ] Конфигурации и токены AmneziaVPN, Remmina (RDP/VNC), Docker (`~/.docker`), если без них не восстановить доступ
- [ ] Сессия Telegram — можно просто войти заново
- [ ] Настройки VS Code (Settings Sync или `~/.config/Code/User`)
- [ ] Память Claude Code (`~/.claude/projects/…/memory`) и сессии Codex (`~/.codex`), если нужны
- [ ] `~/.local` (15 ГБ) и `~/.var` (Flatpak, 2,6 ГБ): в основном кэши и данные приложений; проверь, нет ли там чего-то уникального

Скопировать `~/backup` на внешний носитель или в облако и проверить, что копия открывается **с другого устройства**.

### 1.2. Windows

1. В Windows отключи быстрый запуск и гибернацию — тогда NTFS-разделы (`p3`, `p5`) будут безопасно монтироваться из Linux. В командной строке от администратора:
   ```bat
   powercfg /h off
   ```
2. BitLocker на `C:` сейчас не включён. Если включишь, заранее сохрани ключ восстановления: смена загрузчика может его запросить.

### 1.3. Флешка

Ventoy уже стоит на `sda`. Скачай `archlinux-2026.10.01-x86_64.iso` с [archlinux.org/download](https://archlinux.org/download/), проверь контрольную сумму и скопируй образ на раздел Ventoy:

```sh
sha256sum archlinux-2026.10.01-x86_64.iso   # сравнить со значением на странице загрузки
```

## 2. Загрузка установщика

1. Выключи ноутбук, включи его и нажми **F12** (меню загрузки Lenovo). Выбери флешку и в Ventoy — образ Arch. Если образ не стартует, в Ventoy выбери режим GRUB2.
2. Подключи Wi-Fi:
   ```sh
   iwctl station wlan0 connect "Имя сети"
   ping -c 3 archlinux.org
   timedatectl          # время синхронизировано: «System clock synchronized: yes»
   ```

## 3. Подготовка разделов вручную

В archinstall выбирается режим **Pre-mount** («уже смонтированная конфигурация»): установщик не трогает диск и берёт то, что смонтируем сами. Так форматирование делается одной явной командой и только для `p8`.

Схема: корень `p8` — **Btrfs** с подтомами, EFI-раздел `p6` монтируется в **`/efi`**, а `/boot` с ядром и initramfs — обычный каталог внутри подтома `@`. Тогда снимок корня, который делает установщик Quietline, содержит и ядро: откат не оставит новое ядро со старыми модулями.

| Подтом | Куда монтируется | Зачем |
| --- | --- | --- |
| `@` | `/` | система вместе с `/boot`; его снимает установщик |
| `@home` | `/home` | данные пользователя, в снимок корня не входят |
| `@log` | `/var/log` | журналы переживают откат |
| `@pkg` | `/var/cache/pacman/pkg` | скачанные пакеты переживают откат |
| `@snapshots` | **не монтируется** | сюда установщик кладёт снимки `quietline-pre-<время>` |

1. Сверить устройство и номера разделов — сравнить с таблицей выше:
   ```sh
   lsblk -o NAME,SIZE,FSTYPE,PARTTYPENAME /dev/nvme0n1
   ```
   Должно быть: `p6` 1G vfat EFI System, `p7` 16G swap, `p8` ~337G ext4 (ещё Kubuntu). **Если что-то не совпадает — остановись.**
2. Отформатировать **только** `p8` в Btrfs и создать подтома:
   ```sh
   mkfs.btrfs -L arch /dev/nvme0n1p8
   mount /dev/nvme0n1p8 /mnt
   btrfs subvolume create /mnt/@
   btrfs subvolume create /mnt/@home
   btrfs subvolume create /mnt/@log
   btrfs subvolume create /mnt/@pkg
   btrfs subvolume create /mnt/@snapshots
   umount /mnt
   ```
3. Смонтировать подтома и EFI-раздел:
   ```sh
   o=noatime,compress=zstd
   mount -o $o,subvol=@ /dev/nvme0n1p8 /mnt/archinstall --mkdir
   mount -o $o,subvol=@home /dev/nvme0n1p8 /mnt/archinstall/home --mkdir
   mount -o $o,subvol=@log /dev/nvme0n1p8 /mnt/archinstall/var/log --mkdir
   mount -o $o,subvol=@pkg /dev/nvme0n1p8 /mnt/archinstall/var/cache/pacman/pkg --mkdir
   mount /dev/nvme0n1p6 /mnt/archinstall/efi --mkdir     # без форматирования
   swapon /dev/nvme0n1p7
   ls /mnt/archinstall/efi/EFI                             # видно ubuntu — раздел верный и не затёрт
   ```

`/mnt/archinstall/boot` не монтируется: это каталог внутри `@`, туда попадут ядро и initramfs. На `p6` останется только EFI-файл GRUB рядом с `EFI/ubuntu`. Windows хранит свой загрузчик на `p1` и не затрагивается.

## 4. archinstall

```sh
archinstall
```

Названия пунктов могут немного отличаться — ориентируйся на смысл:

| Пункт | Значение |
| --- | --- |
| Язык archinstall | English или Русский — как удобнее |
| Locales | раскладка консоли `us`, язык `ru_RU.UTF-8`, кодировка UTF-8 (`en_US.UTF-8` включит установщик Quietline) |
| Mirrors | регион Belarus и соседние (Poland, Germany, Lithuania) |
| Disk configuration | **Pre-mount**, каталог `/mnt/archinstall` |
| Disk encryption | нет: шифрование корня в этом плане не предусмотрено |
| Swap | **выключить** zram: используется раздел `p7`, он уже подключён и попадёт в `fstab` |
| Bootloader | **No bootloader** — GRUB ставим вручную в разделе 5 |
| Unified kernel images | нет |
| Hostname | например `quietline` |
| Root password / User | пользователь `kiryl` с правами sudo (wheel); пароль root по желанию |
| Profile | **Minimal**: Hyprland и оболочку ставит Quietline, не archinstall |
| Audio | **PipeWire** |
| Bluetooth | включить |
| Power management | `power-profiles-daemon` (на нём основан раздел «Питание») |
| Kernels | `linux` |
| Network configuration | **NetworkManager** |
| Additional packages | `git openssh btrfs-progs nano` |
| Timezone | `Europe/Minsk` |
| Automatic time sync (NTP) | включить |

Загрузчик archinstall не ставим намеренно: с EFI-разделом в `/efi` он, судя по исходному коду archinstall, положил бы файлы GRUB на общий EFI-раздел и по умолчанию записал бы `EFI/BOOT/BOOTX64.EFI` (режим `--removable`), затерев запасной загрузчик, общий с Windows и Kubuntu. Это поведение не проверено вживую — ручная установка в разделе 5 его обходит.

Перед **Install** открой сводку и проверь: диск — pre-mount `/mnt/archinstall`, загрузчик — нет, профиль Minimal. Микрокод `intel-ucode` archinstall добавит сам.

## 5. До перезагрузки: GRUB и Windows в меню

В конце archinstall предложит войти в установленную систему (chroot) — соглашайся. Если пропустил: `arch-chroot /mnt/archinstall`.

```sh
pacman -S --needed grub efibootmgr os-prober btrfs-progs

# GRUB в /efi, без --removable: запасной загрузчик EFI/BOOT не трогаем
grub-install --target=x86_64-efi --efi-directory=/efi --bootloader-id=Arch

# Windows в меню GRUB
sed -i 's/^#\?GRUB_DISABLE_OS_PROBER=.*/GRUB_DISABLE_OS_PROBER=false/' /etc/default/grub
grep -q '^GRUB_DISABLE_OS_PROBER' /etc/default/grub || echo 'GRUB_DISABLE_OS_PROBER=false' >> /etc/default/grub
sed -i 's/^GRUB_TIMEOUT=.*/GRUB_TIMEOUT=5/' /etc/default/grub
grub-mkconfig -o /boot/grub/grub.cfg     # в выводе — «Found Windows Boot Manager on /dev/nvme0n1p1»

cat /etc/fstab        # ожидаемое — ниже
efibootmgr            # появилась запись Arch, она первая в BootOrder
exit
```

Ожидаемый `/etc/fstab` (UUID и `subvolid` у тебя свои):

```
UUID=…  /                      btrfs  rw,noatime,compress=zstd,subvolid=256,subvol=/@          0 0
UUID=…  /home                  btrfs  rw,noatime,compress=zstd,subvolid=257,subvol=/@home      0 0
UUID=…  /var/log               btrfs  rw,noatime,compress=zstd,subvolid=258,subvol=/@log       0 0
UUID=…  /var/cache/pacman/pkg  btrfs  rw,noatime,compress=zstd,subvolid=259,subvol=/@pkg       0 0
UUID=…  /efi                   vfat   rw,relatime,…                                            0 2
UUID=…  none                   swap   defaults                                                 0 0
```

Строки `/boot` и `@snapshots` быть не должно. Вторую локаль (`en_US.UTF-8`) и снимки настроит установщик Quietline.

Затем `umount -R /mnt/archinstall`, `swapoff -a`, `reboot`, вынуть флешку.

## 6. Проверка загрузки

- [ ] Ноутбук стартует в меню GRUB, загружается Arch, пользователь `kiryl` входит в TTY.
- [ ] Из меню GRUB загружается Windows; после возвращения в Arch время не сбито.
- [ ] Через **F12** напрямую выбирается Windows Boot Manager.
- [ ] `nmcli device wifi connect "Имя сети" --ask` подключает Wi-Fi; `swapon --show` показывает `p7`.
- [ ] `findmnt -t btrfs` показывает `/`, `/home`, `/var/log`, `/var/cache/pacman/pkg` с подтомами `@…`; `findmnt /boot` пуст (ядро внутри `@`).

Только после всех пяти пунктов можно убрать остатки Ubuntu:

```sh
sudo efibootmgr                        # найти номер записи ubuntu (сейчас Boot0002)
sudo efibootmgr -b 0002 -B             # удалить только её — сверь номер!
sudo rm -r /efi/EFI/ubuntu
```

## 7. После установки

1. Восстановить SSH и проверить права:
   ```sh
   gpg -d ssh.tar.gz.gpg | tar -C ~ -xzf -
   chmod 700 ~/.ssh && chmod 600 ~/.ssh/config ~/.ssh/known_hosts ~/.ssh/markticket-dev.pub
   ```
   Подключение `ssh markticket-dev` заработает после установки 1Password и включения его SSH-агента.
2. Получить Quietline из приватного репозитория (для `git` через HTTPS сначала `gh auth login` и `gh auth setup-git`, либо вход по SSH после 1Password):
   ```sh
   git clone https://github.com/lunasy26/quietline.git ~/Work/Personal/quietline
   cd ~/Work/Personal/quietline
   ```
3. Запустить установщик — от своего пользователя, не через sudo; пароль sudo он спросит сам:
   ```sh
   ./install.sh
   ```
   Установщик спрашивает язык установщика и язык системы, проверяет систему, показывает каталог программ («Рекомендуемый набор» или свой выбор) и сводку. После согласия он делает снимок корня `@` в `@snapshots` и ставит выбранное; PKGBUILD пакетов AUR показываются до сборки, Docker Desktop и AmneziaVPN — ручные шаги. Если шаг упал, повторный `./install.sh` предложит «Продолжить» (готовое не повторяется) или «Откатить» (вернуть систему к снимку). Журнал — `~/.local/state/quietline/install.log`, проверка готовности — `./install.sh check`.
4. Перезагрузиться: вход через greetd, сеанс Hyprland. Дальше — [smoke-installer.md](../../scripts/smoke-installer.md), [smoke-quickshell.md](../../scripts/smoke-quickshell.md) и [smoke-system-panels.md](../../scripts/smoke-system-panels.md).

## Если что-то пошло не так

- **Не загружается GRUB, грузится сразу Windows.** Через F12 загрузи флешку и смонтируй систему: `mount -o subvol=@ /dev/nvme0n1p8 /mnt`, `mount -o subvol=@home /dev/nvme0n1p8 /mnt/home`, `mount /dev/nvme0n1p6 /mnt/efi`. Затем `arch-chroot /mnt`, `grub-install --target=x86_64-efi --efi-directory=/efi --bootloader-id=Arch` и `grub-mkconfig -o /boot/grub/grub.cfg`.
- **После установки Quietline система не загружается.** В меню GRUB выбери подменю снимков и загрузи `quietline-pre-<время>`: это система до установки, изменения в ней пропадут после перезагрузки. Из неё или из своей системы выполни `./install.sh rollback` — он вернёт `@` к снимку.
- **В меню GRUB нет Windows.** Проверь `GRUB_DISABLE_OS_PROBER=false`, что `os-prober` установлен, и повтори `grub-mkconfig`. Пока это не исправлено, Windows доступна через F12.
- **Windows не видит свои файлы или NTFS монтируется только для чтения.** Значит, быстрый запуск не отключён: загрузись в Windows и выполни `powercfg /h off`.

Источники: [Archinstall 4.5](https://9to5linux.com/arch-linux-iso-release-for-october-2026-ships-with-the-archinstall-4-5-installer), [ISO октября 2026](https://linuxiac.com/arch-linux-october-2026-iso-is-out-with-linux-kernel-7-2-7-systemd-262/), [документация archinstall](https://archinstall.archlinux.page/installing/guided.html).
