#!/usr/bin/env python3
"""Проверяет, что все пакеты репозитория из installer/catalog.toml есть в базах pacman.

Запуск на чистом Arch с одним python (базы синхронизированы, например `pacman -Syu`):
`python scripts/check-catalog.py`. Скрипт самостоятелен: читает TOML сам и не импортирует
`quietline_install`. Проверяются пакеты основы, варианты с источником `repo` и `repo_packages`
всех вариантов — `pacman -Si` для каждого. Flathub и AUR не проверяются (нет сети в CI).
Пропуски печатаются строкой `missing: …`, код выхода 1; иначе `all packages found`.
"""

import subprocess
import sys
import tomllib
from pathlib import Path

CATALOG = Path(__file__).resolve().parent.parent / 'installer' / 'catalog.toml'


def repo_packages(catalog: dict) -> list[str]:
    """Пакеты репозитория Arch из каталога без повторов, в порядке появления."""
    packages = list(catalog['core']['packages'])
    for section in catalog.get('section', []):
        for item in section.get('item', []):
            packages.extend(item.get('repo_packages', []))
            if item['source'] == 'repo':
                packages.extend(item.get('packages', []))
    return list(dict.fromkeys(packages))


def main() -> int:
    with open(CATALOG, 'rb') as file:
        packages = repo_packages(tomllib.load(file))
    missing = [
        package for package in packages
        if subprocess.run(['pacman', '-Si', package], capture_output=True).returncode != 0
    ]
    if missing:
        print('missing: ' + ' '.join(missing))
        return 1
    print('all packages found')
    return 0


if __name__ == '__main__':
    sys.exit(main())
