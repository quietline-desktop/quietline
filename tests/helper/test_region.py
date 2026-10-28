"""Тесты настроек языка и региона: `region.json`, `locale.conf`, `keyboard.lua` и CLI `region`."""

import json
import re
import subprocess
from pathlib import Path

import pytest

from quietline_shell import config
from quietline_shell.__main__ import main
from quietline_shell.config import (
    NOTIFICATION_TEXTS, default_region, keyboard_lua, load_region, notification_text, save_region, validated_region,
)

RU_DEFAULT = {"language": "ru", "clock": "24h", "date": "dmy", "layouts": ["us", "ru"], "toggle": "grp:lalt_lshift_toggle"}
EN_DEFAULT = {"language": "en", "clock": "12h", "date": "mdy", "layouts": ["us", "ru"], "toggle": "grp:lalt_lshift_toggle"}


def run_cli(capsys, *argv):
    code = main(list(argv))
    return code, json.loads(capsys.readouterr().out)


@pytest.fixture(autouse=True)
def no_hyprland(monkeypatch):
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)


@pytest.mark.parametrize("lang, expected", [("ru_RU.UTF-8", RU_DEFAULT), ("de_DE.UTF-8", EN_DEFAULT), (None, EN_DEFAULT)])
def test_region_defaults_follow_lang(tmp_path, lang, expected):
    assert default_region(lang) == expected
    assert load_region(tmp_path / "region.json", lang) == expected


def test_region_roundtrip_and_partial_update(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("LANG", "ru_RU.UTF-8")
    path = tmp_path / "quietline" / "region.json"
    code, response = run_cli(capsys, "region", "--path", str(path))
    assert (code, response) == (0, RU_DEFAULT)
    code, response = run_cli(capsys, "region", "--path", str(path), "--set", '{"clock": "12h"}')
    assert code == 0
    assert response == {**RU_DEFAULT, "clock": "12h", "applied": False}
    code, response = run_cli(capsys, "region", "--path", str(path))
    assert response == {**RU_DEFAULT, "clock": "12h"}
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved == {"version": 1, **RU_DEFAULT, "clock": "12h"}
    assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("update", [
    {"language": "de"},
    {"clock": "25h"},
    {"layouts": ["us"]},
    {"layouts": ["us", "us"]},
    {"toggle": "grp:win_space_toggle"},
    {"extra": 1},
])
def test_invalid_region_values_are_rejected(tmp_path, capsys, update):
    path = tmp_path / "quietline" / "region.json"
    code, response = run_cli(capsys, "region", "--path", str(path), "--set", json.dumps(update))
    assert code == 1
    assert "error" in response
    with pytest.raises(ValueError):
        validated_region(update, default_region("ru"))
    assert not path.exists()
    assert not (tmp_path / "locale.conf").exists()
    assert not (tmp_path / "quietline" / "keyboard.lua").exists()


def test_corrupt_region_is_reported_without_overwriting(tmp_path, capsys):
    path = tmp_path / "quietline" / "region.json"
    path.parent.mkdir()
    path.write_text("{broken", encoding="utf-8")
    code, response = run_cli(capsys, "region", "--path", str(path))
    assert code == 1 and "error" in response
    code, response = run_cli(capsys, "region", "--path", str(path), "--set", '{"clock": "24h"}')
    assert code == 1 and str(path) in response["error"]
    assert path.read_text(encoding="utf-8") == "{broken"
    assert not (tmp_path / "locale.conf").exists()


def test_foreign_region_format_is_an_error(tmp_path):
    path = tmp_path / "region.json"
    path.write_text(json.dumps({"version": 2}), encoding="utf-8")
    with pytest.raises(ValueError, match=str(path)):
        load_region(path)


def test_locale_conf_keeps_other_variables(tmp_path):
    (tmp_path / "locale.conf").write_text("LC_TIME=en_GB.UTF-8\nLANG=en_US.UTF-8\n", encoding="utf-8")
    path = tmp_path / "quietline" / "region.json"
    save_region(path, {**EN_DEFAULT, "language": "ru"}, tmp_path)
    assert (tmp_path / "locale.conf").read_text(encoding="utf-8") == "LC_TIME=en_GB.UTF-8\nLANG=ru_RU.UTF-8\n"


def test_locale_conf_is_created_and_lang_appended(tmp_path):
    path = tmp_path / "quietline" / "region.json"
    save_region(path, EN_DEFAULT, tmp_path)
    assert (tmp_path / "locale.conf").read_text(encoding="utf-8") == "LANG=en_US.UTF-8\n"
    (tmp_path / "locale.conf").write_text("LC_TIME=en_GB.UTF-8", encoding="utf-8")
    save_region(path, RU_DEFAULT, tmp_path)
    assert (tmp_path / "locale.conf").read_text(encoding="utf-8") == "LC_TIME=en_GB.UTF-8\nLANG=ru_RU.UTF-8\n"


def test_every_lang_line_is_replaced(tmp_path):
    (tmp_path / "locale.conf").write_text("LANG=en_US.UTF-8\nLC_TIME=en_GB.UTF-8\nLANG=de_DE.UTF-8\n", encoding="utf-8")
    save_region(tmp_path / "quietline" / "region.json", {**EN_DEFAULT, "language": "ru"}, tmp_path)
    assert (tmp_path / "locale.conf").read_text(encoding="utf-8") == "LANG=ru_RU.UTF-8\nLC_TIME=en_GB.UTF-8\nLANG=ru_RU.UTF-8\n"


def test_clock_change_does_not_rewrite_locale_conf(tmp_path):
    path = tmp_path / "quietline" / "region.json"
    save_region(path, EN_DEFAULT, tmp_path)
    inode = (tmp_path / "locale.conf").stat().st_ino
    save_region(path, {**EN_DEFAULT, "clock": "24h"}, tmp_path)
    assert (tmp_path / "locale.conf").stat().st_ino == inode


def test_matching_lang_keeps_file_bytes(tmp_path):
    (tmp_path / "locale.conf").write_text("# user\nLANG=ru_RU.UTF-8", encoding="utf-8")
    save_region(tmp_path / "quietline" / "region.json", RU_DEFAULT, tmp_path)
    assert (tmp_path / "locale.conf").read_text(encoding="utf-8") == "# user\nLANG=ru_RU.UTF-8"


def test_locale_write_failure_keeps_region_json(tmp_path, monkeypatch):
    path = tmp_path / "quietline" / "region.json"
    save_region(path, EN_DEFAULT, tmp_path)
    before = path.read_text(encoding="utf-8")
    original = config._atomic_write_text

    def failing(target, text):
        if target.name == "locale.conf":
            raise OSError("disk full")
        original(target, text)

    monkeypatch.setattr(config, "_atomic_write_text", failing)
    with pytest.raises(OSError):
        save_region(path, {**EN_DEFAULT, "language": "ru"}, tmp_path)
    assert path.read_text(encoding="utf-8") == before


def test_keyboard_lua_follows_order_and_toggle(tmp_path, capsys):
    region = {**RU_DEFAULT, "layouts": ["ru", "us"], "toggle": "grp:caps_toggle"}
    assert keyboard_lua(region) == 'return { kb_layout = "ru,us", kb_options = "grp:caps_toggle" }\n'
    path = tmp_path / "quietline" / "region.json"
    code, _ = run_cli(capsys, "region", "--path", str(path), "--set", json.dumps(
        {"layouts": ["ru", "us"], "toggle": "grp:caps_toggle"}))
    assert code == 0
    assert (tmp_path / "quietline" / "keyboard.lua").read_text(encoding="utf-8") == keyboard_lua(
        {**EN_DEFAULT, "layouts": ["ru", "us"], "toggle": "grp:caps_toggle"})


def test_keyboard_apply_failure_still_saves(tmp_path, capsys, monkeypatch):
    path = tmp_path / "quietline" / "region.json"
    code, response = run_cli(capsys, "region", "--path", str(path), "--set", '{"language": "ru"}')
    assert (code, response["applied"]) == (0, False)
    assert path.exists() and (tmp_path / "locale.conf").exists() and (tmp_path / "quietline" / "keyboard.lua").exists()

    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "test")
    calls = []

    def failing(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 1, "", "")

    monkeypatch.setattr(config.subprocess, "run", failing)
    code, response = run_cli(capsys, "region", "--path", str(path), "--set", '{"clock": "24h"}')
    assert (code, response["applied"]) == (0, False)
    assert json.loads(path.read_text(encoding="utf-8"))["clock"] == "24h"
    assert calls and calls[0][:2] == ["hyprctl", "eval"]


def test_keyboard_apply_success_and_missing_hyprctl(monkeypatch):
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "test")
    calls = []

    def succeeding(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(config.subprocess, "run", succeeding)
    assert config.apply_keyboard({**RU_DEFAULT, "layouts": ["ru", "us"]}) is True
    args, kwargs = calls[0]
    assert args == ["hyprctl", "eval", 'hl.config({ input = { kb_layout = "ru,us", kb_options = "grp:lalt_lshift_toggle" } })']
    assert kwargs.get("timeout")

    def missing(args, **kwargs):
        raise FileNotFoundError("hyprctl")

    monkeypatch.setattr(config.subprocess, "run", missing)
    assert config.apply_keyboard(RU_DEFAULT) is False

    def slow(args, **kwargs):
        raise subprocess.TimeoutExpired(args, 3)

    monkeypatch.setattr(config.subprocess, "run", slow)
    assert config.apply_keyboard(RU_DEFAULT) is False


def test_notification_text_follows_region_language(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("LANG", "ru_RU.UTF-8")
    assert notification_text("screenshot_saved") == "Снимок экрана сохранён и скопирован"
    save_region(tmp_path / "quietline" / "region.json", {**RU_DEFAULT, "language": "en"}, tmp_path)
    assert notification_text("screenshot_saved") == "Screenshot saved and copied"
    assert notification_text("app_in_background", app="Code") == "“Code” keeps running in the background"


def test_notification_text_falls_back_to_lang(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("LANG", "ru_RU.UTF-8")
    assert notification_text("lock_failed") == "Не удалось заблокировать сеанс"
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    assert notification_text("lock_failed") == "Could not lock the session"
    (tmp_path / "quietline").mkdir()
    (tmp_path / "quietline" / "region.json").write_text("{broken")
    assert notification_text("lock_failed") == "Could not lock the session"
    monkeypatch.setenv("LANG", "ru_RU.UTF-8")
    assert notification_text("lock_failed") == "Не удалось заблокировать сеанс"


def test_notification_texts_have_both_languages():
    assert set(NOTIFICATION_TEXTS) == {"ru", "en"}
    assert NOTIFICATION_TEXTS["ru"].keys() == NOTIFICATION_TEXTS["en"].keys()
    for key, text in NOTIFICATION_TEXTS["ru"].items():
        assert re.findall(r"\{(\w+)\}", text) == re.findall(r"\{(\w+)\}", NOTIFICATION_TEXTS["en"][key]), key


ROOT = Path(__file__).resolve().parents[2]


def test_lua_config_reads_keyboard_file_with_defaults():
    text = (ROOT / "config/hyprland/quietline.lua").read_text(encoding="utf-8")
    assert "quietline/keyboard.lua" in text
    assert "pcall(dofile" in text
    assert '"us,ru"' in text
    assert '"grp:lalt_lshift_toggle"' in text
    assert "kb_layout" in text and "kb_options" in text
    line = keyboard_lua({**RU_DEFAULT, "layouts": ["ru", "us"], "toggle": "grp:caps_toggle"})
    assert line == 'return { kb_layout = "ru,us", kb_options = "grp:caps_toggle" }\n'
    assert line.count("\n") == 1


def test_fish_locale_keeps_terminal_messages_english():
    text = (ROOT / "config/fish/quietline-locale.fish").read_text(encoding="utf-8")
    assert "set -gx LC_MESSAGES en_US.UTF-8" in text
    assert "set -e LANGUAGE" in text
    assert not re.search(r"\bLANG\b(?!UAGE)", re.sub(r"#.*", "", text))
