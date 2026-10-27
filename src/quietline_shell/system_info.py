"""Сводка для страницы «О системе» окна «Настройки»; недоступное значение — `None`."""

import json
import platform
import re
import socket
import subprocess
from pathlib import Path
from typing import Any


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _run(args: list[str]) -> str | None:
    """stdout команды с кодом 0; иначе, без программы или по таймауту — `None`."""
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=3, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


def _hyprland() -> str | None:
    output = _run(["hyprctl", "version", "-j"])
    try:
        return json.loads(output).get("tag") if output else None
    except (ValueError, AttributeError):
        return None


def about(
    os_release: Path = Path("/etc/os-release"),
    cpuinfo: Path = Path("/proc/cpuinfo"),
    meminfo: Path = Path("/proc/meminfo"),
) -> dict[str, Any]:
    """`{os, kernel, hostname, cpu, memoryGb, hyprland, quickshell}`."""
    name = re.search(r'^PRETTY_NAME="?([^"\n]*)"?', _read(os_release), re.M)
    cpu = re.search(r"^model name\s*:\s*(.+)$", _read(cpuinfo), re.M)
    memory = re.search(r"^MemTotal:\s+(\d+) kB", _read(meminfo), re.M)
    quickshell = _run(["qs", "--version"])
    return {
        "os": name.group(1) if name else None,
        "kernel": platform.release(),
        "hostname": socket.gethostname(),
        "cpu": cpu.group(1).strip() if cpu else None,
        "memoryGb": round(int(memory.group(1)) / 1048576, 1) if memory else None,
        "hyprland": _hyprland(),
        "quickshell": quickshell.strip().splitlines()[0] if quickshell and quickshell.strip() else None,
    }
