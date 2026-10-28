"""Поиск файлов домашнего каталога по личной базе plocate.

База — `$XDG_CACHE_HOME/quietline/home.db`, строится `updatedb -l 0 -U ~ -o <база>`
(правила исключений — из `/etc/updatedb.conf`, скрытые каталоги верхнего уровня исключаются).
Поиск по имени файла без учёта регистра идёт по готовой базе; старая или отсутствующая база
перестраивается в фоне. Файлы внутри скрытых каталогов и скрытые файлы в ответ не попадают.
"""

import fcntl
import os
import subprocess
import sys
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


def _pruned(home: Path) -> list[str]:
    """Скрытые каталоги верхнего уровня домашнего каталога для `updatedb -e`.

    Список `-e` разделяется пробелами, поэтому каталоги с пробелом в имени в него не входят:
    их файлы отсекает фильтр скрытых путей при поиске.
    """
    try:
        return sorted(
            str(entry) for entry in home.iterdir()
            if entry.name.startswith(".") and " " not in entry.name and entry.is_dir() and not entry.is_symlink()
        )
    except OSError:
        return []


def update_index() -> dict[str, Any]:
    """Перестраивает базу домашнего каталога; второе обновление одновременно не запускается.

    Ответ — `{"indexedAt"}` (время построения) или `{"indexedAt", "running": true}`, если база
    уже строится.
    """
    path = database()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(path.with_name("home.db.lock"), "w") as guard:
        try:
            fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"indexedAt": int(path.stat().st_mtime) if path.exists() else None, "running": True}
        home = Path.home()
        temporary = path.with_name("home.db.new")
        command = ["updatedb", "-l", "0", "-U", str(home), "-o", str(temporary)]
        pruned = _pruned(home)
        if pruned:
            command += ["-e", " ".join(pruned)]
        result = _run(command, timeout=300)
        if result.returncode:
            temporary.unlink(missing_ok=True)
            raise RuntimeError(f"updatedb failed: {result.stderr.strip() or f'exit code {result.returncode}'}")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    return {"indexedAt": int(path.stat().st_mtime)}


def start_update() -> None:
    """Перестраивает базу отдельным процессом в фоне."""
    subprocess.Popen(
        [sys.executable, "-m", "quietline_shell", "files", "--update"], stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )


def _hidden(path: str, home: str) -> bool:
    relative = path[len(home):] if path.startswith(home) else path
    return any(part.startswith(".") for part in relative.split("/") if part)


def find_files(query: str, limit: int = 20) -> dict[str, Any]:
    """Пути, имя которых содержит `query`, по готовой базе.

    Базы ещё нет — пустой ответ с `"indexing": true` и построение в фоне; база старше
    `REFRESH_SECONDS` — поиск по ней и обновление в фоне.
    """
    needle = query.strip()
    if not needle or len(needle) > QUERY_LIMIT or "\0" in needle:
        raise ValueError(f"search query must be 1 to {QUERY_LIMIT} characters")
    if limit < 1 or limit > 500:
        raise ValueError("limit must be between 1 and 500")
    path = database()
    if not path.exists():
        start_update()
        return {"files": [], "indexedAt": None, "indexing": True}
    if time.time() - path.stat().st_mtime > REFRESH_SECONDS:
        start_update()
    result = _run(["plocate", "-d", str(path), "-i", "-b", "-l", str(limit * 5), "--", needle], timeout=10)
    if result.returncode not in (0, 1):
        raise RuntimeError(f"plocate failed: {result.stderr.strip() or f'exit code {result.returncode}'}")
    home = str(Path.home())
    found = [line for line in result.stdout.splitlines() if line and not _hidden(line, home)]
    return {"files": found[:limit], "indexedAt": int(path.stat().st_mtime)}
