"""Поиск файлов домашнего каталога по личной базе plocate.

База — `$XDG_CACHE_HOME/quietline/home.db`, строится `updatedb -l 0 -U ~ -o <база>`
(правила исключений — из `/etc/updatedb.conf`). Поиск по имени файла без учёта регистра;
база старше `REFRESH_SECONDS` перед поиском перестраивается. Файлы внутри скрытых каталогов
и скрытые файлы в ответ не попадают.
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Any

REFRESH_SECONDS = 3600
QUERY_LIMIT = 200


def database() -> Path:
    directory = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(directory) / "quietline" / "home.db"


def _run(args: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError as error:
        raise RuntimeError(f"{args[0]} is not installed (package plocate)") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"{args[0]} did not respond") from error


def update_index() -> dict[str, int]:
    """Перестраивает базу домашнего каталога; ответ — время построения."""
    path = database()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    result = _run(["updatedb", "-l", "0", "-U", str(Path.home()), "-o", str(path)], timeout=300)
    if result.returncode:
        raise RuntimeError(f"updatedb failed: {result.stderr.strip() or f'exit code {result.returncode}'}")
    os.chmod(path, 0o600)
    return {"indexedAt": int(path.stat().st_mtime)}


def _hidden(path: str, home: str) -> bool:
    relative = path[len(home):] if path.startswith(home) else path
    return any(part.startswith(".") for part in relative.split("/") if part)


def find_files(query: str, limit: int = 20) -> dict[str, Any]:
    """Пути, имя которых содержит `query`; база при необходимости обновляется."""
    needle = query.strip()
    if not needle or len(needle) > QUERY_LIMIT or "\0" in needle:
        raise ValueError(f"search query must be 1 to {QUERY_LIMIT} characters")
    if limit < 1 or limit > 500:
        raise ValueError("limit must be between 1 and 500")
    path = database()
    if not path.exists() or time.time() - path.stat().st_mtime > REFRESH_SECONDS:
        update_index()
    result = _run(["plocate", "-d", str(path), "-i", "-b", "-l", str(limit * 5), "--", needle], timeout=10)
    if result.returncode not in (0, 1):
        raise RuntimeError(f"plocate failed: {result.stderr.strip() or f'exit code {result.returncode}'}")
    home = str(Path.home())
    found = [line for line in result.stdout.splitlines() if line and not _hidden(line, home)]
    return {"files": found[:limit], "indexedAt": int(path.stat().st_mtime)}
