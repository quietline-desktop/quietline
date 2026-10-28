"""Тесты `quietline-shell files`: личная база plocate, фоновое обновление, скрытые файлы."""

import os
import subprocess
import time

import pytest

from quietline_shell import search


class FakeLocate:
    def __init__(self, found=""):
        self.found = found
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append(list(args))
        if args[0] == "updatedb":
            open(args[args.index("-o") + 1], "w").close()
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(args, 0 if self.found else 1, self.found, "")


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".cache").mkdir(parents=True)
    (home / ".config").mkdir()
    (home / "Документы").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    found = "\n".join([f"{home}/Документы/отчёт.docx", f"{home}/work/.git/отчёт", f"{home}/work/.отчёт.swp", ""])
    fake = FakeLocate(found)
    monkeypatch.setattr(subprocess, "run", fake)
    started = []
    monkeypatch.setattr(search, "start_update", lambda: started.append(True))
    return home, tmp_path / "cache" / "quietline" / "home.db", fake, started


def test_update_builds_the_private_index_without_hidden_top_dirs(env):
    home, db, fake, _started = env
    assert search.update_index() == {"indexedAt": int(db.stat().st_mtime)}
    assert fake.calls[0] == [
        "updatedb", "-l", "0", "-U", str(home), "-o", str(db.with_name("home.db.new")),
        "-e", f"{home}/.cache {home}/.config",
    ]
    assert db.exists() and db.stat().st_mode & 0o777 == 0o600


def test_first_search_starts_indexing_in_the_background(env):
    _home, _db, fake, started = env
    assert search.find_files("отчёт") == {"files": [], "indexedAt": None, "indexing": True}
    assert started == [True] and fake.calls == []


def test_search_uses_the_index_and_hides_dotfiles(env):
    home, db, fake, started = env
    search.update_index()
    result = search.find_files("отчёт")
    assert fake.calls[-1] == ["plocate", "-d", str(db), "-i", "-b", "-l", "100", "--", "отчёт"]
    assert result["files"] == [f"{home}/Документы/отчёт.docx"] and started == []


def test_old_index_is_searched_and_refreshed_in_the_background(env):
    _home, db, fake, started = env
    search.update_index()
    old = time.time() - search.REFRESH_SECONDS - 10
    os.utime(db, (old, old))
    assert search.find_files("отчёт")["files"]
    assert started == [True]


def test_concurrent_update_is_skipped(env):
    _home, db, fake, _started = env
    import fcntl
    db.parent.mkdir(parents=True, exist_ok=True)
    with open(db.with_name("home.db.lock"), "w") as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        assert search.update_index() == {"indexedAt": None, "running": True}
    assert fake.calls == []


@pytest.mark.parametrize("query", ["", "   ", "x" * 201, "a\0b"])
def test_bad_queries_are_rejected(env, query):
    with pytest.raises(ValueError):
        search.find_files(query)
    assert env[2].calls == []


def test_option_like_query_is_passed_after_double_dash(env):
    search.update_index()
    search.find_files("--help")
    assert env[2].calls[-1][-2:] == ["--", "--help"]
