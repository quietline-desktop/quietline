"""Тексты экранов установщика на русском и английском.

Подстановки — `{имя}`; набор ключей и подстановок в обоих языках совпадает (проверяется тестом).
Журнал `install.log` и вывод `install.sh` до выбора языка тут не участвуют: они английские.
"""

TEXTS = {
    'ru': {
        # Общее
        'language.ru': 'Русский',
        'language.en': 'English',
        'hint.menu': 'Стрелки — выбор, Enter — дальше, Esc — назад, q — выход без изменений',
        'hint.confirm': 'Enter — продолжить, Esc — назад, q — выход без изменений',
        'hint.list': 'Стрелки — выбор, Пробел — отметить, Enter — раскрыть, r — рекомендуемый набор, Esc — назад, q — выход',
        'hint.any': 'Enter — продолжить',
        'hint.close': 'Enter — закрыть',

        # Проверки
        'checks.title': 'Проверка системы',
        'check.arch': 'Это Arch Linux',
        'check.not-root': 'Запуск не от root',
        'check.network': 'Есть сеть',
        'check.sudo': 'Есть sudo',
        'check.btrfs': 'Корень на Btrfs',
        'check.status.ok': 'ОК',
        'check.status.fail': 'НЕТ',
        'check.status.warn': 'ВНИМАНИЕ',
        'checks.failed': 'Исправьте то, что отмечено «НЕТ», и запустите ./install.sh снова. Ничего не изменено.',
        'checks.noBtrfs': (
            'Корень не на Btrfs: снимка не будет. Если установка сломается, откат пойдёт по журналу: '
            'пакеты, которые поставил установщик, будут удалены, а изменённые файлы конфигурации — '
            'возвращены из копий. Он менее полный, чем откат снимка.'
        ),
        'checks.noBtrfsConfirm': 'Продолжить без снимка?',

        # Язык системы
        'systemLanguage.title': 'Язык системы',
        'systemLanguage.prompt': 'На каком языке будет установленная система: меню, настройки, подписи приложений. Обе локали (русская и английская) создаются в любом случае.',

        # Программы
        'programs.title': 'Программы',
        'programs.base': 'Основа ставится всегда: Hyprland, Quickshell, Quietline, экран входа, звук, сеть, Bluetooth, шрифты, снимки экрана, буфер, Ghostty, fish.',
        'programs.recommended': 'Рекомендуемый набор — установить',
        'programs.next': 'Далее',
        'programs.installed': 'уже установлено',
        'sectionBrowsers': 'Браузеры',
        'sectionMessengers': 'Общение',
        'sectionFiles': 'Файлы',
        'sectionCode': 'Редактор кода',
        'sectionPasswords': 'Пароли',
        'sectionVpn': 'VPN',
        'sectionRemote': 'Удалённый доступ',
        'sectionDocuments': 'Документы',
        'sectionContainers': 'Контейнеры',
        'sectionDotnet': 'Разработка: .NET',
        'sectionNode': 'Разработка: Node.js',
        'sectionPython': 'Разработка: Python',
        'sectionDevTools': 'Разработка: инструменты',
        'advanced': 'Расширенные',

        # Сводка
        'summary.title': 'Сводка',
        'summary.install': 'Будет установлено:',
        'summary.manual': 'Ручные шаги:',
        'summary.question': 'Начать установку?',

        # Итог
        'final.title': 'Готово',
        'final.done': 'Установка завершена.',
        'final.manual': 'Осталось сделать вручную:',
        'final.checks': 'Проверка готовности:',
        'final.homeDirs': 'Папки в домашнем каталоге оставлены как были: {path}. Данные не переносились.',
        'final.reboot': 'Перезагрузиться сейчас, чтобы войти через экран входа Quietline?',
        'final.hint': 'Enter — перезагрузить, Esc — позже',

        # Продолжить или откатить
        'resume.title': 'Незавершённая установка',
        'resume.failed': 'Шаг «{step}» не завершился.',
        'resume.continue': 'Продолжить — с этого шага, готовое не повторяется',
        'resume.rollback': 'Откатить — вернуть систему как до запуска',
        'resume.quit': 'Выйти — ничего не менять',
        'rollback.confirm': 'Откатить сделанное установщиком?',
        'rollback.done': 'Откат выполнен.',

        # Ошибки
        'error.stepFailed': 'Шаг «{step}» не выполнен: {reason}',
        'error.next': 'Сделанное сохранено. Запустите ./install.sh снова, чтобы продолжить или откатить.',

        # Шаги
        'step.system-upgrade': 'Обновление системы',
        'step.repo-packages': 'Пакеты из репозитория Arch',
        'step.graphics': 'Драйвер видеокарты',
        'step.locales': 'Языки системы',
        'step.quietline-package': 'Пакет Quietline',
        'step.services': 'Службы',
        'step.hyprland-config': 'Конфигурация Hyprland',
        'step.fish': 'Настройка fish',
        'step.micro': 'Настройка micro',
        'step.quickshell-link': 'Подключение оболочки',
        'step.user-dirs': 'Домашние папки',
        'step.region': 'Регион',
        'step.pins': 'Закрепления дока',
        'step.greetd': 'Экран входа',
        'step.flatpak': 'Программы из Flathub',
        'step.fnm': 'Node.js через fnm',
        'step.uv': 'Версии Python через uv',
        'step.aur': 'Программы из AUR',
        'step.default-shell': 'fish по умолчанию',
        'step.docker-group': 'Группа docker',
        'step.docker-desktop': 'Docker Desktop (вручную)',
        'step.amneziavpn': 'AmneziaVPN (вручную)',
        'step.snapshot-prepare': 'Подготовка снимков',
        'step.snapshot': 'Снимок системы',
    },
    'en': {
        'language.ru': 'Русский',
        'language.en': 'English',
        'hint.menu': 'Arrows — choose, Enter — next, Esc — back, q — quit without changes',
        'hint.confirm': 'Enter — continue, Esc — back, q — quit without changes',
        'hint.list': 'Arrows — choose, Space — check, Enter — expand, r — recommended set, Esc — back, q — quit',
        'hint.any': 'Enter — continue',
        'hint.close': 'Enter — close',

        'checks.title': 'System check',
        'check.arch': 'This is Arch Linux',
        'check.not-root': 'Not running as root',
        'check.network': 'Network is available',
        'check.sudo': 'sudo is available',
        'check.btrfs': 'Root filesystem is Btrfs',
        'check.status.ok': 'OK',
        'check.status.fail': 'NO',
        'check.status.warn': 'WARNING',
        'checks.failed': 'Fix what is marked "NO" and run ./install.sh again. Nothing was changed.',
        'checks.noBtrfs': (
            'Root is not on Btrfs: there will be no snapshot. If the installation breaks, rollback follows the '
            'installer journal: packages the installer added are removed and changed configuration files are '
            'restored from copies. It is less complete than rolling back a snapshot.'
        ),
        'checks.noBtrfsConfirm': 'Continue without a snapshot?',

        'systemLanguage.title': 'System language',
        'systemLanguage.prompt': 'The language of the installed system: menus, settings, application labels. Both locales (Russian and English) are generated anyway.',

        'programs.title': 'Programs',
        'programs.base': 'The base is always installed: Hyprland, Quickshell, Quietline, login screen, audio, network, Bluetooth, fonts, screenshots, clipboard, Ghostty, fish.',
        'programs.recommended': 'Recommended set — install',
        'programs.next': 'Next',
        'programs.installed': 'already installed',
        'sectionBrowsers': 'Browsers',
        'sectionMessengers': 'Messengers',
        'sectionFiles': 'Files',
        'sectionCode': 'Code editor',
        'sectionPasswords': 'Passwords',
        'sectionVpn': 'VPN',
        'sectionRemote': 'Remote access',
        'sectionDocuments': 'Documents',
        'sectionContainers': 'Containers',
        'sectionDotnet': 'Development: .NET',
        'sectionNode': 'Development: Node.js',
        'sectionPython': 'Development: Python',
        'sectionDevTools': 'Development: tools',
        'advanced': 'Advanced',

        'summary.title': 'Summary',
        'summary.install': 'Will be installed:',
        'summary.manual': 'Manual steps:',
        'summary.question': 'Start the installation?',

        'final.title': 'Done',
        'final.done': 'Installation finished.',
        'final.manual': 'Still to do by hand:',
        'final.checks': 'Readiness check:',
        'final.homeDirs': 'Folders in your home directory were left as they are: {path}. No data was moved.',
        'final.reboot': 'Reboot now to sign in through the Quietline login screen?',
        'final.hint': 'Enter — reboot, Esc — later',

        'resume.title': 'Unfinished installation',
        'resume.failed': 'Step "{step}" did not finish.',
        'resume.continue': 'Continue — from this step, finished steps are not repeated',
        'resume.rollback': 'Roll back — return the system to how it was before',
        'resume.quit': 'Quit — change nothing',
        'rollback.confirm': 'Roll back what the installer did?',
        'rollback.done': 'Rollback finished.',

        'error.stepFailed': 'Step "{step}" failed: {reason}',
        'error.next': 'Progress is saved. Run ./install.sh again to continue or to roll back.',

        'step.system-upgrade': 'System upgrade',
        'step.repo-packages': 'Arch repository packages',
        'step.graphics': 'Graphics driver',
        'step.locales': 'System languages',
        'step.quietline-package': 'Quietline package',
        'step.services': 'Services',
        'step.hyprland-config': 'Hyprland configuration',
        'step.fish': 'fish setup',
        'step.micro': 'micro setup',
        'step.quickshell-link': 'Shell link',
        'step.user-dirs': 'Home folders',
        'step.region': 'Region',
        'step.pins': 'Dock pins',
        'step.greetd': 'Login screen',
        'step.flatpak': 'Flathub programs',
        'step.fnm': 'Node.js via fnm',
        'step.uv': 'Python versions via uv',
        'step.aur': 'AUR programs',
        'step.default-shell': 'fish as the default shell',
        'step.docker-group': 'docker group',
        'step.docker-desktop': 'Docker Desktop (manual)',
        'step.amneziavpn': 'AmneziaVPN (manual)',
        'step.snapshot-prepare': 'Snapshot preparation',
        'step.snapshot': 'System snapshot',
    },
}


def text(language: str, key: str, **values) -> str:
    """Текст по ключу на языке; нет в языке — английский; нет нигде — KeyError."""
    table = TEXTS.get(language, TEXTS['en'])
    template = table[key] if key in table else TEXTS['en'][key]
    return template.format(**values)
