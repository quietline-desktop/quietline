"""Тесты `quietline-shell`: закрепления, ограничение анимаций, сводка «О системе» и контракт JSON CLI."""

import json
import os
import subprocess

import pytest

from quietline_shell import config
from quietline_shell.__main__ import main
from quietline_shell.config import DEFAULT_PINS, load_pins, save_pins


def test_missing_config_has_the_five_approved_apps(tmp_path):
    assert load_pins(tmp_path / "pins.json") == [
        "org.kde.dolphin",
        "google-chrome",
        "code",
        "com.mitchellh.ghostty",
        "org.telegram.desktop",
    ]
    assert list(DEFAULT_PINS) == load_pins(tmp_path / "pins.json")


def test_pins_roundtrip_preserves_order_and_removes_duplicates(tmp_path):
    path = tmp_path / "quietline" / "pins.json"
    save_pins(path, ["code", "org.kde.dolphin", "code"])
    assert load_pins(path) == ["code", "org.kde.dolphin"]
    assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("pins", [["../bad"], ["a/b"], ["app;command"], ["a..b"], "code", [3], ["x"] * 101])
def test_invalid_desktop_ids_do_not_replace_good_config(tmp_path, pins):
    path = tmp_path / "pins.json"
    save_pins(path, ["code"])
    with pytest.raises(ValueError):
        save_pins(path, pins)
    assert load_pins(path) == ["code"]


def test_atomic_replace_failure_keeps_previous_pins(tmp_path, monkeypatch):
    path = tmp_path / "pins.json"
    save_pins(path, ["code"])

    def refuse(*args):
        raise OSError("read-only config")

    monkeypatch.setattr(os, "replace", refuse)
    with pytest.raises(OSError):
        save_pins(path, ["org.kde.dolphin"])
    monkeypatch.undo()
    assert load_pins(path) == ["code"]
    assert list(tmp_path.iterdir()) == [path]


def test_empty_pin_list_is_persisted_instead_of_reset_to_defaults(tmp_path):
    path = tmp_path / "pins.json"
    save_pins(path, [])
    assert load_pins(path) == []


@pytest.mark.parametrize(
    "content",
    ["{broken", '{"version": 2, "pinned": []}', '["code"]', '{"version": 1, "pinned": "code"}', '{"version": 1}'],
)
def test_corrupt_config_is_reported_without_overwriting_it(tmp_path, content):
    path = tmp_path / "pins.json"
    path.write_text(content)
    with pytest.raises(ValueError):
        load_pins(path)
    assert path.read_text() == content


@pytest.mark.parametrize("pinned", ['"code"', '["../etc"]'])
def test_invalid_pins_in_file_name_the_file(tmp_path, pinned):
    path = tmp_path / "pins.json"
    path.write_text('{"version": 1, "pinned": ' + pinned + "}")
    with pytest.raises(ValueError, match="invalid pins in .*pins.json") as caught:
        load_pins(path)
    assert str(path) in str(caught.value)
    assert str(caught.value).isascii()


def test_default_path_follows_xdg_config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config.default_pins_path() == tmp_path / "quietline" / "pins.json"


@pytest.mark.parametrize(("value", "expected"), [("1", True), ("yes", True), ("0", False), ("", False)])
def test_reduced_motion_override_wins_over_the_portal(monkeypatch, value, expected):
    monkeypatch.setenv("QUIETLINE_REDUCED_MOTION", value)

    def portal(*args, **kwargs):
        raise AssertionError("portal must not be asked")

    monkeypatch.setattr(subprocess, "run", portal)
    assert config.reduced_motion() is expected


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        (subprocess.CompletedProcess([], 0, "(<<uint32 1>>,)\n", ""), True),
        (subprocess.CompletedProcess([], 0, "(<<uint32 0>>,)\n", ""), False),
        (subprocess.CompletedProcess([], 1, "", "no portal"), False),
        (OSError("gdbus not found"), False),
    ],
)
def test_reduced_motion_reads_the_portal_and_defaults_to_animations(monkeypatch, reply, expected):
    monkeypatch.delenv("QUIETLINE_REDUCED_MOTION", raising=False)

    def portal(*args, **kwargs):
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(subprocess, "run", portal)
    assert config.reduced_motion() is expected


def run_cli(capsys, *argv):
    code = main(list(argv))
    output = capsys.readouterr().out
    assert output.count("\n") == 1
    return code, json.loads(output)


def test_cli_pins_prints_saves_and_reports_errors_as_json(tmp_path, capsys):
    path = str(tmp_path / "pins.json")
    assert run_cli(capsys, "pins", "--path", path) == (0, {"pinned": list(DEFAULT_PINS)})
    assert run_cli(capsys, "pins", "--path", path, "--set", '["code", "google-chrome"]') == (
        0,
        {"pinned": ["code", "google-chrome"]},
    )
    code, response = run_cli(capsys, "pins", "--path", path, "--set", '["../etc"]')
    assert code == 1
    assert set(response) == {"error"}
    assert response["error"].isascii()
    code, response = run_cli(capsys, "pins", "--path", path, "--set", "not json")
    assert code == 1 and set(response) == {"error"}
    assert run_cli(capsys, "pins", "--path", path) == (0, {"pinned": ["code", "google-chrome"]})


def test_cli_motion_prints_the_shell_field(capsys, monkeypatch):
    monkeypatch.setenv("QUIETLINE_REDUCED_MOTION", "1")
    assert run_cli(capsys, "motion") == (0, {"reducedMotion": True})


def test_about_reads_os_release_and_versions(tmp_path, monkeypatch):
    (tmp_path / "os-release").write_text('NAME="Arch Linux"\nPRETTY_NAME="Arch Linux"\n')
    (tmp_path / "cpuinfo").write_text("processor\t: 0\nmodel name\t: 12th Gen Intel(R) Core(TM) i5-12450H\n")
    (tmp_path / "meminfo").write_text("MemTotal:       16099064 kB\n")
    monkeypatch.setattr(config.platform, "release", lambda: "7.2.7-arch1-1")
    monkeypatch.setattr(config.socket, "gethostname", lambda: "quietline")

    def run(args, **kwargs):
        if args[0] == "hyprctl":
            return subprocess.CompletedProcess(args, 0, json.dumps({"tag": "v0.55.1"}), "")
        return subprocess.CompletedProcess(args, 0, "Quickshell 0.3.2 (revision , distributed by Arch Linux)\n", "")

    monkeypatch.setattr(subprocess, "run", run)
    info = config.about(tmp_path / "os-release", tmp_path / "cpuinfo", tmp_path / "meminfo")
    assert info == {
        "os": "Arch Linux", "kernel": "7.2.7-arch1-1", "hostname": "quietline",
        "cpu": "12th Gen Intel(R) Core(TM) i5-12450H", "memoryGb": 15.4,
        "hyprland": "0.55.1", "quickshell": "0.3.2",
    }


def test_missing_tools_are_reported_as_null(tmp_path, monkeypatch):
    def run(args, **kwargs):
        raise FileNotFoundError(args[0])

    monkeypatch.setattr(subprocess, "run", run)
    info = config.about(tmp_path / "none", tmp_path / "none", tmp_path / "none")
    assert info["hyprland"] is None and info["quickshell"] is None
    assert info["os"] is None and info["cpu"] is None and info["memoryGb"] is None


def test_cli_about_prints_one_json_line(capsys, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda args, **kwargs: subprocess.CompletedProcess(args, 1, "", ""))
    assert main(["about"]) == 0
    output = capsys.readouterr().out
    assert output.count("\n") == 1
    assert set(json.loads(output)) == {"os", "kernel", "hostname", "cpu", "memoryGb", "hyprland", "quickshell"}
