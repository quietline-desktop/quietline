#!/bin/sh
# Точка входа установщика Quietline: шрифт консоли с кириллицей, проверки и запуск пакета из клона.
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
os_release="${QUIETLINE_OS_RELEASE:-/etc/os-release}"

# В виртуальной консоли без шрифта с кириллицей русский текст превратится в квадраты.
if [ "${TERM:-}" = linux ]; then
    setfont cyr-sun16 2>/dev/null || true
fi

if [ "$(id -u)" -eq 0 ]; then
    echo "Run ./install.sh as your user, not as root: it asks for sudo when needed." >&2
    exit 1
fi

if ! grep -qx 'ID=arch' "$os_release" 2>/dev/null; then
    echo "Quietline installs on Arch Linux only." >&2
    exit 1
fi

if ! command -v python >/dev/null 2>&1 || ! command -v git >/dev/null 2>&1; then
    if ! sudo pacman -S --needed python git; then
        echo "Could not install python and git. Update the system first: sudo pacman -Syu" >&2
        exit 1
    fi
fi

if ! python -c 'import sys; sys.exit(sys.version_info < (3, 14))'; then
    echo "Quietline needs Python 3.14 or newer. Update the system: sudo pacman -Syu" >&2
    exit 1
fi

PYTHONPATH="$repo/src" exec python -m quietline_install --repo "$repo" "$@"
