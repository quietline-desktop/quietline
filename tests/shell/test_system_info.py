"""Тесты сводки «О системе» `quietline-shell about`."""

import json
import subprocess

from quietline_shell import system_info
from quietline_shell.__main__ import main


def test_about_reads_os_release_and_versions(tmp_path, monkeypatch):
    (tmp_path / "os-release").write_text('NAME="Arch Linux"\nPRETTY_NAME="Arch Linux"\n')
    (tmp_path / "cpuinfo").write_text("processor\t: 0\nmodel name\t: 12th Gen Intel(R) Core(TM) i5-12450H\n")
    (tmp_path / "meminfo").write_text("MemTotal:       16099064 kB\n")
    monkeypatch.setattr(system_info.platform, "release", lambda: "7.2.7-arch1-1")
    monkeypatch.setattr(system_info.socket, "gethostname", lambda: "quietline")

    def run(args, **kwargs):
        if args[0] == "hyprctl":
            return subprocess.CompletedProcess(args, 0, json.dumps({"tag": "v0.55.1"}), "")
        return subprocess.CompletedProcess(args, 0, "quickshell 0.3.2\n", "")

    monkeypatch.setattr(subprocess, "run", run)
    info = system_info.about(tmp_path / "os-release", tmp_path / "cpuinfo", tmp_path / "meminfo")
    assert info == {
        "os": "Arch Linux", "kernel": "7.2.7-arch1-1", "hostname": "quietline",
        "cpu": "12th Gen Intel(R) Core(TM) i5-12450H", "memoryGb": 15.4,
        "hyprland": "v0.55.1", "quickshell": "quickshell 0.3.2",
    }


def test_missing_tools_are_reported_as_null(tmp_path, monkeypatch):
    def run(args, **kwargs):
        raise FileNotFoundError(args[0])

    monkeypatch.setattr(subprocess, "run", run)
    info = system_info.about(tmp_path / "none", tmp_path / "none", tmp_path / "none")
    assert info["hyprland"] is None and info["quickshell"] is None
    assert info["os"] is None and info["cpu"] is None and info["memoryGb"] is None


def test_cli_about_prints_one_json_line(capsys, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda args, **kwargs: subprocess.CompletedProcess(args, 1, "", ""))
    assert main(["about"]) == 0
    output = capsys.readouterr().out
    assert output.count("\n") == 1
    assert set(json.loads(output)) == {"os", "kernel", "hostname", "cpu", "memoryGb", "hyprland", "quickshell"}
