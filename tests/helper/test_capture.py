"""Тесты `quietline-shell screenshot`: монитор с фокусом, порядок «файл → буфер → уведомление», ошибки по шагам."""

import json
import subprocess
from datetime import datetime

import pytest

from quietline_shell import capture
from quietline_shell.config import notification_text

NOW = datetime(2026, 10, 28, 9, 15, 30)
MONITORS = [{"name": "DP-1", "focused": False}, {"name": "eDP-1", "focused": True}]


class FakeTools:
    """grim, slurp, wl-copy, hyprctl, xdg-user-dir и notify-send; `fail` — имя программы, которая падает."""

    def __init__(self, pictures, fail=None, selection="10,20 300x200\n"):
        self.pictures = pictures
        self.fail = fail
        self.selection = selection
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append((list(args), kwargs.get("input")))
        name = args[0]
        if name == self.fail:
            return subprocess.CompletedProcess(args, 1, b"" if not kwargs.get("text") else "", b"boom" if not kwargs.get("text") else "boom")
        outputs = {
            "hyprctl": json.dumps(MONITORS), "xdg-user-dir": f"{self.pictures}\n", "slurp": self.selection,
            "grim": b"PNGDATA", "wl-copy": b"", "notify-send": b"",
        }
        return subprocess.CompletedProcess(args, 0, outputs.get(name, ""), "" if kwargs.get("text") else b"")

    def names(self):
        return [args[0] for args, _ in self.calls]

    def notices(self):
        return [args[3:] for args, _ in self.calls if args[0] == "notify-send"]


@pytest.fixture
def tools(tmp_path, monkeypatch):
    fake = FakeTools(tmp_path / "Изображения")
    monkeypatch.setattr(subprocess, "run", fake)
    return fake


def test_output_shot_saves_then_copies_then_notifies(tools, tmp_path):
    result = capture.capture_output(NOW)
    path = tmp_path / "Изображения" / "Screenshots" / "Screenshot_2026-10-28_09-15-30.png"
    assert result == {"path": str(path), "copied": True}
    assert path.read_bytes() == b"PNGDATA"
    grim = next(args for args, _ in tools.calls if args[0] == "grim")
    assert grim == ["grim", "-o", "eDP-1", "-"]
    assert tools.names()[-2:] == ["wl-copy", "notify-send"]
    assert next(data for args, data in tools.calls if args[0] == "wl-copy") == b"PNGDATA"
    assert tools.notices() == [[notification_text("screenshot_saved"), str(path)]]


def test_same_second_gets_a_free_name(tools, tmp_path):
    first = capture.capture_output(NOW)["path"]
    second = capture.capture_output(NOW)["path"]
    assert first != second and second.endswith("Screenshot_2026-10-28_09-15-30-2.png")


@pytest.mark.parametrize(("fail", "step", "text"), [
    ("grim", "capture", "Не удалось снять экран"),
    ("wl-copy", "copy", "Снимок сохранён, но не скопирован в буфер"),
])
def test_failed_step_is_named_and_success_is_not_claimed(tools, fail, step, text):
    tools.fail = fail
    with pytest.raises(capture.CaptureError) as error:
        capture.capture_output(NOW)
    assert error.value.step == step
    assert [notice[0] for notice in tools.notices()] == [text]


def test_unwritable_directory_is_a_save_error(tools, tmp_path):
    (tmp_path / "Изображения").write_text("not a directory")
    with pytest.raises(capture.CaptureError) as error:
        capture.capture_output(NOW)
    assert error.value.step == "save"
    assert "wl-copy" not in tools.names()


def test_no_focused_monitor_is_a_capture_error(tools, monkeypatch):
    tools_outputs = json.dumps([{"name": "DP-1", "focused": False}])
    original = tools.__call__

    def without_focus(args, **kwargs):
        if args[0] == "hyprctl":
            return subprocess.CompletedProcess(args, 0, tools_outputs, "")
        return original(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", without_focus)
    with pytest.raises(capture.CaptureError, match="no monitor has focus"):
        capture.capture_output(NOW)


def test_cancelled_region_does_nothing(tools, monkeypatch):
    tools.selection = ""
    started = []
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: started.append(args))
    assert capture.capture_region() == {"cancelled": True}
    assert started == [] and "grim" not in tools.names()


def test_region_opens_satty_with_the_capture(tools, tmp_path, monkeypatch):
    opened = []

    class Editor:
        def __init__(self, args, **kwargs):
            opened.append((args, kwargs))
            self.stdin = self
            self.data = b""

        def write(self, data):
            opened.append(data)

        def close(self):
            pass

    monkeypatch.setattr(subprocess, "Popen", Editor)
    assert capture.capture_region() == {"started": True}
    assert next(args for args, _ in tools.calls if args[0] == "grim") == ["grim", "-g", "10,20 300x200", "-"]
    args, kwargs = opened[0]
    directory = tmp_path / "Изображения" / "Screenshots"
    assert args == ["satty", "--filename", "-", "--output-filename", str(directory / "Screenshot_%Y-%m-%d_%H-%M-%S.png"),
                    "--copy-command", "wl-copy", "--early-exit", "all"]
    assert kwargs["start_new_session"] is True and opened[1] == b"PNGDATA"
    assert directory.is_dir()
