"""Тесты `quietline-shell files`: личная база plocate, обновление по возрасту, скрытые файлы."""

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
            path = args[args.index("-o") + 1]
            open(path, "w").close()
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(args, 0 if self.found else 1, self.found, "")


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    found = "\n".join([f"{home}/Документы/отчёт.docx", f"{home}/.config/app/отчёт.json", f"{home}/work/.отчёт.swp", ""])
    fake = FakeLocate(found)
    monkeypatch.setattr(subprocess, "run", fake)
    return home, tmp_path / "cache" / "quietline" / "home.db", fake


def test_first_search_builds_the_private_index(env):
    home, db, fake = env
    result = search.find_files("отчёт")
    assert fake.calls[0] == ["updatedb", "-l", "0", "-U", str(home), "-o", str(db)]
    assert fake.calls[1] == ["plocate", "-d", str(db), "-i", "-b", "-l", "100", "--", "отчёт"]
    assert result["files"] == [f"{home}/Документы/отчёт.docx"]
    assert db.stat().st_mode & 0o777 == 0o600


def test_fresh_index_is_reused_and_old_one_rebuilt(env):
    _home, db, fake = env
    search.find_files("отчёт")
    search.find_files("отчёт")
    assert [call[0] for call in fake.calls] == ["updatedb", "plocate", "plocate"]
    old = time.time() - search.REFRESH_SECONDS - 10
    os.utime(db, (old, old))
    search.find_files("отчёт")
    assert fake.calls[-2][0] == "updatedb"


def test_nothing_found_is_an_empty_list(env):
    _home, _db, fake = env
    fake.found = ""
    assert search.find_files("нет-такого")["files"] == []


@pytest.mark.parametrize("query", ["", "   ", "x" * 201, "a\0b"])
def test_bad_queries_are_rejected(env, query):
    with pytest.raises(ValueError):
        search.find_files(query)
    assert env[2].calls == []


def test_option_like_query_is_passed_after_double_dash(env):
    search.find_files("--help")
    assert env[2].calls[-1][-2:] == ["--", "--help"]
