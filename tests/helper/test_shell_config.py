"""Тесты `quietline-shell`: закрепления, ограничение анимаций, сводка «О системе», масштаб мониторов и контракт JSON CLI."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from quietline_shell import config
from quietline_shell.__main__ import main
from quietline_shell.config import DEFAULT_PINS, display_lua, load_appearance, load_display, load_pins, save_pins, updated_display


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


# Масштаб мониторов: `display.json`, `display.lua` и CLI `display`.

BUILTIN = "desc:BOE 0x0B76"


def run_display(capsys, *argv):
    code = main(["display", *argv])
    return code, json.loads(capsys.readouterr().out)


@pytest.fixture
def no_hyprland(monkeypatch):
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)


def test_missing_file_means_no_monitors(tmp_path, capsys, no_hyprland):
    assert load_display(tmp_path / "display.json") == {}
    assert run_display(capsys, "--path", str(tmp_path / "display.json")) == (
        0, {"monitors": {}, "scales": {}, "outputs": []})


def test_set_and_reset_fields_write_json_and_lua(tmp_path, capsys, no_hyprland):
    path = tmp_path / "quietline" / "display.json"
    code, response = run_display(capsys, "--path", str(path), "--set", json.dumps({"output": BUILTIN, "scale": 1.25}))
    assert (code, response) == (0, {"monitors": {BUILTIN: {"scale": 1.25}}, "scales": {BUILTIN: 1.25},
                                     "outputs": [], "applied": False})
    assert json.loads(path.read_text(encoding="utf-8")) == {"version": 2, "monitors": {BUILTIN: {"scale": 1.25}}}
    assert path.with_name("display.lua").read_text(encoding="utf-8") == 'return {\n    ["desc:BOE 0x0B76"] = { scale = 1.25 },\n}\n'

    change = {"output": "DP-2", "mode": "2560x1440@74.96", "position": "auto-right", "transform": 1, "vrr": 2}
    run_display(capsys, "--path", str(path), "--set", json.dumps(change))
    code, response = run_display(capsys, "--path", str(path), "--set", json.dumps({"output": BUILTIN, "scale": "auto"}))
    assert (code, response["monitors"], response["scales"]) == (0, {"DP-2": {
        "mode": "2560x1440@74.96", "position": "auto-right", "transform": 1, "vrr": 2}}, {})
    assert path.with_name("display.lua").read_text(encoding="utf-8") == (
        'return {\n    ["DP-2"] = { mode = "2560x1440@74.96", position = "auto-right", transform = 1, vrr = 2 },\n}\n')

    run_display(capsys, "--path", str(path), "--set", json.dumps(
        {"output": "DP-2", "mode": "auto", "position": "auto", "transform": 0}))
    assert load_display(path) == {"DP-2": {"vrr": 2}}


def test_version_one_file_is_read_as_scales_and_upgraded(tmp_path, capsys, no_hyprland):
    path = tmp_path / "display.json"
    path.write_text(json.dumps({"version": 1, "scales": {BUILTIN: 1.25}}), encoding="utf-8")
    assert load_display(path) == {BUILTIN: {"scale": 1.25}}
    run_display(capsys, "--path", str(path), "--set", json.dumps({"output": "DP-1", "vrr": 0}))
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "version": 2, "monitors": {BUILTIN: {"scale": 1.25}, "DP-1": {"vrr": 0}}}


@pytest.mark.parametrize("change", [
    {"output": BUILTIN, "scale": 0.25},
    {"output": BUILTIN, "scale": 5},
    {"output": BUILTIN, "scale": True},
    {"output": BUILTIN, "scale": "1.25"},
    {"output": 'desc:Evil" }) os.exit() --', "scale": 1},
    {"output": "desc:back\\slash", "scale": 1},
    {"output": "DP 1", "scale": 1},
    {"output": BUILTIN},
    {"output": BUILTIN, "mode": "preferred"},
    {"output": BUILTIN, "mode": '2560x1440@60" })'},
    {"output": BUILTIN, "position": "0x0"},
    {"output": BUILTIN, "transform": 4},
    {"output": BUILTIN, "transform": True},
    {"output": BUILTIN, "vrr": 3},
    {"output": BUILTIN, "mirror": "DP-1"},
    [BUILTIN, 1],
])
def test_invalid_changes_are_rejected_without_writing(tmp_path, capsys, change, no_hyprland):
    path = tmp_path / "display.json"
    code, response = run_display(capsys, "--path", str(path), "--set", json.dumps(change))
    assert code == 1 and "error" in response
    assert not path.exists() and not path.with_name("display.lua").exists()


def test_corrupt_file_is_reported_without_overwriting(tmp_path, capsys, no_hyprland):
    path = tmp_path / "display.json"
    path.write_text('{"version": 1, "scales": {"DP-1": 9}}', encoding="utf-8")
    code, response = run_display(capsys, "--path", str(path), "--set", json.dumps({"output": "DP-1", "scale": 1}))
    assert code == 1 and str(path) in response["error"]
    assert json.loads(path.read_text(encoding="utf-8"))["scales"] == {"DP-1": 9}


def test_display_lua_is_sorted_and_empty_without_monitors():
    assert display_lua({}) == "return {\n}\n"
    assert display_lua({"eDP-1": {"scale": 1.5}, "DP-1": {"vrr": 1, "mode": "1920x1080@60.0"}}) == (
        'return {\n    ["DP-1"] = { mode = "1920x1080@60.0", vrr = 1 },\n    ["eDP-1"] = { scale = 1.5 },\n}\n')


def test_updated_display_keeps_other_monitors():
    assert updated_display({"output": "DP-1", "scale": "auto"}, {"DP-1": {"scale": 2.0}, "eDP-1": {"scale": 1.25}}) == (
        "DP-1", {"eDP-1": {"scale": 1.25}})


def test_monitor_rule_fills_defaults():
    assert config.monitor_rule(BUILTIN, {}) == (
        'hl.monitor({ output = "desc:BOE 0x0B76", mode = "preferred", position = "auto", scale = "auto" })')
    assert config.monitor_rule("DP-1", {"mode": "2560x1440@74.96", "scale": 1.0, "transform": 3, "vrr": 0}) == (
        'hl.monitor({ output = "DP-1", mode = "2560x1440@74.96", position = "auto", scale = 1.0, transform = 3, vrr = 0 })')


def test_apply_runs_monitor_rule_in_hyprland(monkeypatch):
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "test")
    calls = []

    def succeeding(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, "ok", "")

    monkeypatch.setattr(config.subprocess, "run", succeeding)
    assert config.apply_display(BUILTIN, {"scale": 1.25}) is True
    assert config.apply_display(BUILTIN, {}) is True
    assert [args for args, _ in calls] == [
        ["hyprctl", "eval", 'hl.monitor({ output = "desc:BOE 0x0B76", mode = "preferred", position = "auto", scale = 1.25 })'],
        ["hyprctl", "eval", 'hl.monitor({ output = "desc:BOE 0x0B76", mode = "preferred", position = "auto", scale = "auto" })'],
    ]
    assert all(kwargs.get("timeout") for _, kwargs in calls)

    def missing(args, **kwargs):
        raise FileNotFoundError("hyprctl")

    monkeypatch.setattr(config.subprocess, "run", missing)
    assert config.apply_display(BUILTIN, {"scale": 1.25}) is False


def test_apply_failure_still_saves(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "test")
    monkeypatch.setattr(config.subprocess, "run", lambda args, **kwargs: subprocess.CompletedProcess(args, 1, "", ""))
    path = tmp_path / "display.json"
    code, response = run_display(capsys, "--path", str(path), "--set", json.dumps({"output": "eDP-1", "scale": 1.5}))
    assert (code, response["applied"], response["outputs"]) == (0, False, [])
    assert load_display(path) == {"eDP-1": {"scale": 1.5}}


def test_outputs_come_from_hyprctl_monitors(monkeypatch):
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "test")
    monitors = [{
        "name": "HDMI-A-1", "description": "LG Electronics LG HDR QHD 309NTLE8V592", "width": 2560, "height": 1440,
        "refreshRate": 59.951, "scale": 1.0, "transform": 0, "vrr": False, "x": 1536, "y": 0,
        "availableModes": ["2560x1440@59.95Hz", "2560x1440@74.96Hz", "1920x1080@60.00Hz", "1920x1080@60.00Hz", "junk"],
    }, {"name": "DP-9", "description": 'Bad "quote"', "availableModes": []}, "junk"]
    monkeypatch.setattr(config.subprocess, "run",
                        lambda args, **kwargs: subprocess.CompletedProcess(args, 0, json.dumps(monitors), ""))
    outputs = config.display_outputs()
    assert [item["output"] for item in outputs] == ["desc:LG Electronics LG HDR QHD 309NTLE8V592", "DP-9"]
    assert outputs[0]["modes"] == [{"width": 2560, "height": 1440, "refresh": 59.95},
                                   {"width": 2560, "height": 1440, "refresh": 74.96},
                                   {"width": 1920, "height": 1080, "refresh": 60.0}]
    assert (outputs[0]["refreshRate"], outputs[0]["x"], outputs[0]["vrr"]) == (59.951, 1536, False)
    monkeypatch.setattr(config.subprocess, "run", lambda args, **kwargs: subprocess.CompletedProcess(args, 1, "", ""))
    assert config.display_outputs() == []


# Мышь, тачпад и повтор клавиш: `input.json`, `input.lua` и CLI `input`.

def run_input(capsys, *argv):
    code = main(["input", *argv])
    return code, json.loads(capsys.readouterr().out)


def test_input_defaults_are_hyprland_defaults(tmp_path, capsys, no_hyprland):
    code, response = run_input(capsys, "--path", str(tmp_path / "input.json"))
    assert code == 0
    assert response == {**config.INPUT_DEFAULTS, "touchpad": False}
    assert (response["repeatDelay"], response["repeatRate"], response["tapToClick"]) == (600, 25, True)


def test_input_set_writes_json_and_lua(tmp_path, capsys, no_hyprland):
    path = tmp_path / "quietline" / "input.json"
    change = {"pointerSpeed": -0.3000001, "acceleration": False, "touchpadNaturalScroll": True, "repeatRate": 40}
    code, response = run_input(capsys, "--path", str(path), "--set", json.dumps(change))
    assert code == 0 and response["applied"] is False
    assert (response["pointerSpeed"], response["acceleration"], response["repeatRate"]) == (-0.3, False, 40)
    assert json.loads(path.read_text(encoding="utf-8"))["touchpadNaturalScroll"] is True
    lua = path.with_name("input.lua").read_text(encoding="utf-8")
    assert lua.startswith('return { sensitivity = -0.3, accel_profile = "flat", natural_scroll = false,')
    assert "repeat_rate = 40" in lua and "touchpad = { tap_to_click = true, natural_scroll = true," in lua
    assert run_input(capsys, "--path", str(path))[1]["pointerSpeed"] == -0.3


@pytest.mark.parametrize("change", [
    {}, {"pointerSpeed": 2}, {"pointerSpeed": True}, {"scrollSpeed": 0.1}, {"repeatDelay": 100},
    {"repeatRate": 25.5}, {"repeatRate": True}, {"tapToClick": 1}, {"sensitivity": 0}, ["pointerSpeed"],
])
def test_invalid_input_changes_are_rejected(tmp_path, capsys, change, no_hyprland):
    path = tmp_path / "input.json"
    code, response = run_input(capsys, "--path", str(path), "--set", json.dumps(change))
    assert code == 1 and "error" in response
    assert not path.exists() and not path.with_name("input.lua").exists()


def test_input_applies_in_hyprland_and_finds_touchpad(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "test")
    calls = []

    def fake(args, **kwargs):
        calls.append(args)
        out = json.dumps({"mice": [{"name": "logitech-wireless-mouse"}, {"name": "syna2ba6:00-06cb:cefe-touchpad"}]})
        return subprocess.CompletedProcess(args, 0, out if args[1] == "devices" else "ok", "")

    monkeypatch.setattr(config.subprocess, "run", fake)
    code, response = run_input(capsys, "--path", str(tmp_path / "input.json"), "--set", '{"numlock": true}')
    assert (code, response["applied"], response["touchpad"]) == (0, True, True)
    evals = [args[2] for args in calls if args[1] == "eval"]
    assert evals == ["hl.config({ input = " + config.input_table({**config.INPUT_DEFAULTS, "numlock": True}) + " })"]


# Сроки простоя: `idle.json`, `hypridle.conf` и CLI `idle settings`.

def run_idle(capsys, *argv):
    code = main(["idle", "settings", *argv])
    return code, json.loads(capsys.readouterr().out)


def _timeouts(text):
    return [int(line.split("=")[1]) for line in text.splitlines() if line.strip().startswith("timeout")]


def _general(text):
    return text[text.index("general {"):text.index("}", text.index("general {")) + 1]


def test_default_idle_conf_matches_the_packaged_file():
    packaged = (Path(__file__).parents[2] / "config" / "hypridle" / "hypridle.conf").read_text(encoding="utf-8")
    generated = config.hypridle_conf(config.IDLE_DEFAULTS)
    assert _timeouts(generated) == _timeouts(packaged) == [300, 330, 900]
    assert _general(generated) == _general(packaged)


def test_idle_settings_write_conf_without_never_listeners(tmp_path, capsys, no_hyprland):
    path = tmp_path / "quietline" / "idle.json"
    assert run_idle(capsys, "--path", str(path)) == (0, {"lock": 5, "screenOff": 5, "suspend": 15})
    code, response = run_idle(capsys, "--path", str(path), "--set", json.dumps({"lock": 0, "screenOff": 10, "suspend": 0}))
    assert (code, response) == (0, {"lock": 0, "screenOff": 10, "suspend": 0, "applied": False})
    conf = path.with_name("hypridle.conf").read_text(encoding="utf-8")
    assert _timeouts(conf) == [600] and "lock-session\n}" not in conf and "idle suspend" not in conf
    assert json.loads(path.read_text(encoding="utf-8")) == {"version": 1, "lock": 0, "screenOff": 10, "suspend": 0}


@pytest.mark.parametrize("change", [{}, {"lock": 3}, {"suspend": 5}, {"screenOff": True}, {"sleep": 10}, [5]])
def test_invalid_idle_changes_are_rejected(tmp_path, capsys, change, no_hyprland):
    path = tmp_path / "idle.json"
    code, response = run_idle(capsys, "--path", str(path), "--set", json.dumps(change))
    assert code == 1 and "error" in response
    assert not path.exists() and not path.with_name("hypridle.conf").exists()


def test_idle_settings_restart_hypridle(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "test")
    runs, started = [], []
    monkeypatch.setattr(config.subprocess, "run", lambda args, **kwargs: runs.append(args) or subprocess.CompletedProcess(args, 0, "", ""))
    monkeypatch.setattr(config.subprocess, "Popen", lambda args, **kwargs: started.append((args, kwargs)))
    path = tmp_path / "idle.json"
    code, response = run_idle(capsys, "--path", str(path), "--set", '{"lock": 10}')
    assert (code, response["applied"]) == (0, True)
    assert runs == [["pkill", "-x", "hypridle"]]
    assert started[0][0] == ["hypridle", "-c", str(tmp_path / "hypridle.conf")] and started[0][1]["start_new_session"]


# Оформление: `appearance.json`, `appearance.lua` и CLI `appearance`.

def run_appearance(capsys, *argv):
    code = main(["appearance", *argv])
    return code, json.loads(capsys.readouterr().out)


@pytest.fixture
def commands(monkeypatch):
    """Подменяет `subprocess.run`: команды записываются, код выхода — из `codes` по имени программы."""
    calls = []
    codes = {}

    def run(args, **kwargs):
        calls.append(args)
        assert kwargs.get("timeout")
        return subprocess.CompletedProcess(args, codes.get(args[0], 0), "", "")

    monkeypatch.setattr(config.subprocess, "run", run)
    return calls, codes


def test_missing_appearance_file_means_dark_theme_and_dark_pointer(tmp_path, capsys, no_hyprland):
    expected = {"theme": "dark", "cursor": "dark", "cursorSize": 24, "batteryPercent": "off"}
    assert load_appearance(tmp_path / "appearance.json") == expected
    assert run_appearance(capsys, "--path", str(tmp_path / "appearance.json")) == (0, expected)


def test_partial_set_writes_json_and_lua_and_applies_in_hyprland(tmp_path, capsys, monkeypatch, commands):
    calls, _ = commands
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "test")
    path = tmp_path / "quietline" / "appearance.json"
    code, response = run_appearance(capsys, "--path", str(path), "--set", json.dumps({"theme": "light"}))
    assert (code, response) == (0, {"theme": "light", "cursor": "dark", "cursorSize": 24, "batteryPercent": "off", "applied": True})
    assert json.loads(path.read_text(encoding="utf-8")) == {"version": 1, "theme": "light", "cursor": "dark", "cursorSize": 24, "batteryPercent": "off"}
    assert path.with_name("appearance.lua").read_text(encoding="utf-8") == (
        'return { theme = "light", cursor = "dark", cursor_size = 24 }\n')
    assert calls == [
        ["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", "prefer-light"],
        ["gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", "Adwaita"],
        ["hyprctl", "reload", "config-only"],
        ["hyprctl", "setcursor", "capitaine-cursors", "24"],
    ]

    calls.clear()
    code, response = run_appearance(capsys, "--path", str(path), "--set", json.dumps({"cursor": "light", "cursorSize": 48}))
    assert response == {"theme": "light", "cursor": "light", "cursorSize": 48, "batteryPercent": "off", "applied": True}
    assert calls[-1] == ["hyprctl", "setcursor", "capitaine-cursors-light", "48"]


def test_dark_theme_sets_dark_application_scheme(commands, no_hyprland):
    calls, _ = commands
    assert config.apply_appearance({"theme": "dark", "cursor": "dark", "cursorSize": 36}) is False
    assert calls == [
        ["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", "prefer-dark"],
        ["gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", "Adwaita-dark"],
    ]


def test_failed_step_still_saves_and_runs_the_other_steps(tmp_path, capsys, monkeypatch, commands):
    calls, codes = commands
    codes["gsettings"] = 1
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "test")
    path = tmp_path / "appearance.json"
    code, response = run_appearance(capsys, "--path", str(path), "--set", json.dumps({"theme": "light"}))
    assert (code, response["applied"]) == (0, False)
    assert load_appearance(path)["theme"] == "light"
    assert [args[0] for args in calls] == ["gsettings", "gsettings", "hyprctl", "hyprctl"]


def test_missing_programs_mean_not_applied(monkeypatch):
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "test")

    def missing(args, **kwargs):
        raise FileNotFoundError(args[0])

    monkeypatch.setattr(config.subprocess, "run", missing)
    assert config.apply_appearance({"theme": "light", "cursor": "dark", "cursorSize": 24}) is False


@pytest.mark.parametrize("change", [
    {"theme": "sepia"},
    {"cursor": "white"},
    {"cursorSize": 30},
    {"cursorSize": True},
    {"cursorSize": "24"},
    {"batteryPercent": True},
    {"batteryPercent": "under"},
    {"theme": 'light", os.exit() --'},
    {"accent": "red"},
    {},
    ["light"],
])
def test_invalid_appearance_changes_are_rejected_without_writing(tmp_path, capsys, change, commands, no_hyprland):
    calls, _ = commands
    path = tmp_path / "appearance.json"
    code, response = run_appearance(capsys, "--path", str(path), "--set", json.dumps(change))
    assert code == 1 and "error" in response
    assert not path.exists() and not path.with_name("appearance.lua").exists()
    assert calls == []


def test_corrupt_appearance_file_is_reported_without_overwriting(tmp_path, capsys, no_hyprland):
    path = tmp_path / "appearance.json"
    path.write_text('{"version": 1, "theme": "neon"}', encoding="utf-8")
    code, response = run_appearance(capsys, "--path", str(path), "--set", json.dumps({"theme": "light"}))
    assert code == 1 and str(path) in response["error"]
    assert json.loads(path.read_text(encoding="utf-8"))["theme"] == "neon"


def test_appearance_file_without_some_fields_keeps_defaults(tmp_path):
    path = tmp_path / "appearance.json"
    path.write_text('{"version": 1, "theme": "light"}', encoding="utf-8")
    assert load_appearance(path) == {"theme": "light", "cursor": "dark", "cursorSize": 24, "batteryPercent": "off"}


def test_default_appearance_path_follows_xdg_config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config.default_appearance_path() == tmp_path / "quietline" / "appearance.json"


def test_battery_percent_flag_is_saved_without_touching_lua_fields(tmp_path, capsys, commands, no_hyprland):
    path = tmp_path / "appearance.json"
    code, response = run_appearance(capsys, "--path", str(path), "--set", json.dumps({"batteryPercent": "inside"}))
    assert (code, response["batteryPercent"]) == (0, "inside")
    assert load_appearance(path)["batteryPercent"] == "inside"
    assert path.with_name("appearance.lua").read_text(encoding="utf-8") == (
        'return { theme = "dark", cursor = "dark", cursor_size = 24 }\n')
