"""Тесты `quietline-shell clipboard`: что не попадает в историю, где лежит база, восстановление и очистка."""

import json
import subprocess

import pytest

from quietline_shell import clipboard


class FakeClipboard:
    """cliphist, wl-copy и hyprctl activewindow; `active` — класс активного окна."""

    def __init__(self, active="code"):
        self.active = active
        self.calls = []
        self.listing = b"12\tsecond line\n11\t[[ binary data 14 KiB png 120x80 ]]\nbad\tline\n"

    def __call__(self, args, **kwargs):
        self.calls.append((list(args), kwargs.get("input")))
        if args[:3] == ["hyprctl", "activewindow", "-j"]:
            return subprocess.CompletedProcess(args, 0, json.dumps({"address": "0x1", "class": self.active, "pid": 5}), "")
        if args[0] == "cliphist" and args[3] == "list":
            return subprocess.CompletedProcess(args, 0, self.listing, b"")
        if args[0] == "cliphist" and args[3] == "decode":
            return subprocess.CompletedProcess(args, 0, b"PNGBYTES", b"")
        return subprocess.CompletedProcess(args, 0, b"", b"")

    def cliphist(self):
        return [(args[3:], data) for args, data in self.calls if args[0] == "cliphist"]


@pytest.fixture
def fake(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("CLIPBOARD_STATE", raising=False)
    tool = FakeClipboard()
    monkeypatch.setattr(subprocess, "run", tool)
    return tool


def test_entry_is_stored_in_the_runtime_database(fake, tmp_path):
    assert clipboard.store(b"hello") == {"stored": True}
    args, data = next((args, data) for args, data in fake.calls if args[0] == "cliphist")
    assert args == ["cliphist", "-db-path", str(tmp_path / "quietline" / "clipboard.db"), "store"] and data == b"hello"


@pytest.mark.parametrize(("setup", "reason"), [
    ("paused", "paused"),
    ("sensitive", "sensitive"),
    ("1password", "password-manager"),
])
def test_secrets_and_paused_recording_are_skipped(fake, monkeypatch, setup, reason):
    if setup == "paused":
        clipboard.set_paused(True)
    elif setup == "sensitive":
        monkeypatch.setenv("CLIPBOARD_STATE", "sensitive")
    else:
        fake.active = "1Password"
    assert clipboard.store(b"s3cret") == {"stored": False, "reason": reason}
    assert not any(args == ["store"] for args, _ in fake.cliphist())


@pytest.mark.parametrize("state", ["clear", "nil"])
def test_cleared_clipboard_is_not_stored(fake, monkeypatch, state):
    monkeypatch.setenv("CLIPBOARD_STATE", state)
    assert clipboard.store(b"") == {"stored": False, "reason": "empty"}
    assert fake.cliphist() == []


def test_resuming_records_again(fake):
    clipboard.set_paused(True)
    clipboard.set_paused(False)
    assert clipboard.store(b"x") == {"stored": True}


def test_list_marks_images_and_skips_broken_lines(fake):
    assert clipboard.entries() == {
        "entries": [
            {"id": "12", "kind": "text", "preview": "second line"},
            {"id": "11", "kind": "image", "preview": "[[ binary data 14 KiB png 120x80 ]]"},
        ],
        "paused": False,
    }


def test_restore_decodes_and_copies(fake):
    assert clipboard.restore("11") == {"ok": True}
    assert (["decode"], b"11\t\n") in fake.cliphist()
    assert fake.calls[-1] == (["wl-copy"], b"PNGBYTES")


def test_image_preview_is_a_private_temporary_file(fake, tmp_path):
    path = tmp_path / "quietline" / "clipboard-11.png"
    assert clipboard.image("11") == {"path": str(path)}
    assert path.read_bytes() == b"PNGBYTES" and path.stat().st_mode & 0o777 == 0o600


def test_wipe_and_delete_remove_previews(fake, tmp_path):
    clipboard.image("11")
    clipboard.delete("11")
    assert (["delete"], b"11\t\n") in fake.cliphist()
    assert not (tmp_path / "quietline" / "clipboard-11.png").exists()
    clipboard.image("12")
    assert clipboard.wipe() == {"ok": True}
    assert (["wipe"], None) in fake.cliphist()
    assert list((tmp_path / "quietline").glob("clipboard-*.png")) == []


@pytest.mark.parametrize("entry_id", ["", "1;rm", "../1", "12\t"])
def test_bad_ids_are_rejected(fake, entry_id):
    with pytest.raises(ValueError):
        clipboard.restore(entry_id)
    assert fake.calls == []


def test_missing_runtime_dir_is_an_error(monkeypatch):
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    with pytest.raises(RuntimeError, match="XDG_RUNTIME_DIR"):
        clipboard.store(b"x")
