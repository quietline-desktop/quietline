"""Тесты сетевого помощника `quietline-shell network`: состояние, профили, Wi-Fi и контрольные точки."""

import io
import json
import subprocess

import pytest

from quietline_shell import network
from quietline_shell.__main__ import main


class FakeSystem:
    """Записывает команды и отвечает по самому длинному совпавшему префиксу argv; при равенстве — по последнему."""

    def __init__(self):
        self.answers = []
        self.calls = []

    def add(self, prefix, stdout="", code=0, stderr=""):
        self.answers.append((list(prefix), stdout, code, stderr))

    def __call__(self, args, **kwargs):
        self.calls.append({"args": list(args), "input": kwargs.get("input"), "timeout": kwargs.get("timeout")})
        best = None
        for prefix, stdout, code, stderr in self.answers:
            if args[: len(prefix)] == prefix and (best is None or len(prefix) >= len(best[0])):
                best = (prefix, stdout, code, stderr)
        if best is None:
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(args, best[2], best[1], best[3])

    def commands(self):
        return [call["args"] for call in self.calls]


@pytest.fixture
def system(monkeypatch):
    fake = FakeSystem()
    monkeypatch.setattr(subprocess, "run", fake)
    return fake


@pytest.fixture
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path


DEVICES = "\n".join([
    "GENERAL.DEVICE:eth0", "GENERAL.TYPE:ethernet", "GENERAL.STATE:20 (unavailable)",
    "GENERAL.CONNECTION:--", "GENERAL.CON-UUID:--", "WIRED-PROPERTIES.CARRIER:off", "IP4.GATEWAY:--", "",
    "GENERAL.DEVICE:enx00e04c680001", "GENERAL.TYPE:ethernet", "GENERAL.STATE:100 (connected)",
    "GENERAL.CONNECTION:Site\\: office", "GENERAL.CON-UUID:1111-aaaa", "WIRED-PROPERTIES.CARRIER:on",
    "IP4.ADDRESS[1]:10.42.0.5/24", "IP4.GATEWAY:10.42.0.1", "IP6.ADDRESS[1]:fe80\\:\\:1/64", "",
    "GENERAL.DEVICE:wlan0", "GENERAL.TYPE:wifi", "GENERAL.STATE:70 (connecting (getting IP configuration))",
    "GENERAL.CONNECTION:Home", "GENERAL.CON-UUID:2222-bbbb", "IP4.GATEWAY:--", "",
    "GENERAL.DEVICE:lo", "GENERAL.TYPE:loopback", "GENERAL.STATE:100 (connected (externally))", "",
])
CONNECTIONS = ["nmcli", "-t", "--escape", "yes", "-f", "NAME,UUID,TYPE", "connection", "show"]


def answer_status(system, connections="", details=None):
    system.add(["nmcli", "-t", "--escape", "yes", "-f"], DEVICES)
    system.add(CONNECTIONS, connections)
    system.add(["nmcli", "-t", "-f", "WIFI", "radio"], "enabled\n")
    for uuid, text in (details or {}).items():
        system.add(["nmcli", "-t", "--escape", "yes", "-f", network.PROFILE_FIELDS, "connection", "show", "uuid", uuid], text)


def test_status_reports_cable_and_activation_state(system):
    answer_status(system)
    devices = {item["device"]: item for item in network.status()["devices"]}
    assert set(devices) == {"eth0", "enx00e04c680001", "wlan0"}
    assert (devices["eth0"]["cable"], devices["eth0"]["state"]) == (False, "unavailable")
    assert devices["eth0"]["addresses"] == [] and devices["eth0"]["profile"] == ""
    usb = devices["enx00e04c680001"]
    assert (usb["cable"], usb["state"], usb["type"]) == (True, "connected", "ethernet")
    assert usb["profile"] == "Site: office" and usb["uuid"] == "1111-aaaa"
    assert usb["addresses"] == ["10.42.0.5/24", "fe80::1/64"] and usb["gateway"] == "10.42.0.1"
    assert (devices["wlan0"]["cable"], devices["wlan0"]["state"]) == (None, "connecting")


def test_new_static_profile_never_takes_default_route(system):
    system.add(["nmcli", "connection", "add"], "Connection 'Щит A' (3333-cccc) successfully added.\n")
    profile = network.save_profile({"name": "Щит A", "method": "manual", "address": "10.42.0.5/24", "gateway": None, "dns": []})
    assert system.commands()[-1] == [
        "nmcli", "connection", "add", "type", "ethernet", "con-name", "Щит A", "ifname", "*",
        "connection.autoconnect", "no", "ipv4.method", "manual", "ipv4.addresses", "10.42.0.5/24",
        "ipv4.never-default", "yes", "ipv6.method", "disabled",
    ]
    assert profile["uuid"] == "3333-cccc" and profile["neverDefault"] is True


def test_explicit_default_route_is_kept(system):
    system.add(["nmcli", "connection", "add"], "Connection 'B' (4444-dddd) successfully added.\n")
    network.save_profile({
        "name": "B", "method": "manual", "address": "10.42.0.5/24",
        "gateway": "10.42.0.1", "dns": ["10.42.0.1"], "neverDefault": False,
    })
    assert "ipv4.never-default no ipv4.gateway 10.42.0.1 ipv4.dns 10.42.0.1" in " ".join(system.commands()[-1])


@pytest.mark.parametrize(("changes", "field"), [
    ({"address": "10.0.0.300/24"}, "address"),
    ({"address": "10.0.0.5"}, "prefix"),
    ({"gateway": "10.0.0"}, "gateway"),
    ({"dns": ["x.y"]}, "dns"),
    ({"name": ""}, "name"),
    ({"name": "x" * 65}, "name"),
    ({"method": "static"}, "method"),
])
def test_profile_validation_rejects_bad_input(system, changes, field):
    data = {"name": "Щит", "method": "manual", "address": "10.42.0.5/24", "gateway": None, "dns": [], **changes}
    with pytest.raises(network.ProfileError) as error:
        network.save_profile(data)
    assert error.value.field == field and str(error.value).isascii()
    assert system.calls == []


def test_profile_names_with_colons_roundtrip(system):
    name = 'Site: "B" 2'
    system.add(["nmcli", "connection", "add"], f"Connection '{name}' (5555-eeee) successfully added.\n")
    network.save_profile({"name": name, "method": "manual", "address": "10.42.0.7/24", "gateway": None, "dns": []})
    assert system.commands()[-1][5:7] == ["con-name", name]
    answer_status(
        system,
        connections='Site\\: "B" 2:5555-eeee:802-3-ethernet\nHome:2222-bbbb:802-11-wireless\n',
        details={"5555-eeee": "ipv4.method:manual\nipv4.addresses:10.42.0.7/24\nipv4.gateway:--\nipv4.dns:\nipv4.never-default:yes\n"},
    )
    assert network.status()["profiles"] == [{
        "uuid": "5555-eeee", "name": name, "method": "manual", "address": "10.42.0.7/24",
        "gateway": None, "dns": [], "neverDefault": True, "lastUsed": None,
    }]


def test_wifi_password_never_in_argv(system):
    network.wifi_connect("Home", None, "s3cret")
    assert all("s3cret" not in arg for call in system.calls for arg in call["args"])
    up = system.calls[-1]
    assert up["args"][:7] == ["nmcli", "--wait", "45", "connection", "up", "id", "Home"]
    assert up["args"][-2:] == ["passwd-file", "/dev/stdin"]
    assert up["input"] == "802-11-wireless-security.psk:s3cret\n"


def run_cli(capsys, monkeypatch, stdin, *argv):
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    code = main(list(argv))
    output = capsys.readouterr().out
    assert output.count("\n") == 1
    return code, json.loads(output)


def test_nmcli_failure_is_reported_as_json(system, capsys, monkeypatch):
    system.add(["nmcli", "--wait", "45", "connection", "up"], code=10, stderr="Error: Connection activation failed\n")
    code, response = run_cli(capsys, monkeypatch, "", "network", "wifi-connect", "--ssid", "Open")
    assert code == 1 and set(response) == {"error"}
    assert "NetworkManager" in response["error"] and "Connection activation failed" in response["error"]


def test_cli_form_error_names_the_field(system, capsys, monkeypatch):
    profile = json.dumps({"name": "Щит", "method": "manual", "address": "10.42.0.5"})
    assert run_cli(capsys, monkeypatch, profile, "network", "profile-save") == (
        1, {"error": "address needs a network prefix, for example 10.42.0.5/24: '10.42.0.5'", "field": "prefix"},
    )
    assert run_cli(capsys, monkeypatch, "not json", "network", "profile-save")[1]["field"] == "profile"
    assert system.calls == []


def test_cli_status_prints_one_json_line(system, capsys, monkeypatch, config):
    answer_status(system)
    code, response = run_cli(capsys, monkeypatch, "", "network", "status")
    assert code == 0 and set(response) == {"devices", "wifi", "profiles", "pendingCheckpoints"}


GDBUS = [
    "gdbus", "call", "--system", "--dest", "org.freedesktop.NetworkManager",
    "--object-path", "/org/freedesktop/NetworkManager", "--method",
]
NM = "org.freedesktop.NetworkManager."
CHECKPOINT = "/org/freedesktop/NetworkManager/Checkpoint/3"
CREATE = [*GDBUS, NM + "CheckpointCreate", "['/org/freedesktop/NetworkManager/Devices/7']", "30", "0"]


def answer_checkpoint(system):
    system.add([*GDBUS, NM + "GetDeviceByIpIface"], "(objectpath '/org/freedesktop/NetworkManager/Devices/7',)\n")
    system.add([*GDBUS, NM + "CheckpointCreate"], f"(objectpath '{CHECKPOINT}',)\n")


def test_apply_creates_checkpoint_before_activation(system, config):
    answer_checkpoint(system)
    result = network.apply_profile("1111-aaaa", "enx00e04c")
    commands = system.commands()
    assert commands[0] == [*GDBUS, NM + "GetDeviceByIpIface", "enx00e04c"]
    assert commands[1] == CREATE
    assert commands[2] == ["nmcli", "--wait", "20", "connection", "up", "uuid", "1111-aaaa", "ifname", "enx00e04c"]
    assert result == {"checkpoint": CHECKPOINT, "timeout": 30}
    assert "1111-aaaa" in json.loads((config / "quietline" / "network.json").read_text())["recent"]


def test_failed_activation_rolls_back_immediately(system, config):
    answer_checkpoint(system)
    system.add(["nmcli", "--wait", "20", "connection", "up"], code=4, stderr="Error: IP configuration could not be reserved\n")
    with pytest.raises(RuntimeError, match="IP configuration could not be reserved"):
        network.apply_profile("1111-aaaa", "enx00e04c")
    assert system.commands()[-1] == [*GDBUS, NM + "CheckpointRollback", CHECKPOINT]
    assert not (config / "quietline" / "network.json").exists()


def test_apply_to_missing_device_fails_before_checkpoint(system, config):
    system.add([*GDBUS, NM + "GetDeviceByIpIface"], code=1,
               stderr="GDBus.Error:org.freedesktop.NetworkManager.UnknownDevice: No device found\n")
    with pytest.raises(RuntimeError, match="network adapter enx00e04c not found"):
        network.apply_profile("1111-aaaa", "enx00e04c")
    assert not any(NM + "CheckpointCreate" in command for command in system.commands())


@pytest.mark.parametrize(("uuid", "device"), [("1111-aaaa'", "eth0"), ("1111-aaaa", "eth0; rm"), ("", "eth0")])
def test_apply_rejects_bad_identifiers_without_calls(system, uuid, device):
    with pytest.raises(ValueError):
        network.apply_profile(uuid, device)
    assert system.calls == []


def test_dhcp_creates_its_profile_once(system, config):
    answer_checkpoint(system)
    system.add(["nmcli", "connection", "add"], "Connection 'Quietline DHCP' (6666-ffff) successfully added.\n")
    system.add(CONNECTIONS, "")
    network.apply_dhcp("eth0")
    adds = [command for command in system.commands() if command[:3] == ["nmcli", "connection", "add"]]
    assert adds == [[
        "nmcli", "connection", "add", "type", "ethernet", "con-name", "Quietline DHCP", "ifname", "*",
        "connection.autoconnect", "no", "ipv4.method", "auto",
    ]]
    system.add(CONNECTIONS, "Quietline DHCP:6666-ffff:802-3-ethernet\n")
    network.apply_dhcp("eth0")
    assert len([command for command in system.commands() if command[:3] == ["nmcli", "connection", "add"]]) == 1
    assert system.commands().count(CREATE) == 2
    assert ["nmcli", "--wait", "20", "connection", "up", "uuid", "6666-ffff", "ifname", "eth0"] in system.commands()


def test_confirm_and_rollback_call_destroy_and_rollback(system):
    assert network.confirm(CHECKPOINT) == {"checkpoint": CHECKPOINT, "result": "kept"}
    assert system.commands()[-1] == [*GDBUS, NM + "CheckpointDestroy", CHECKPOINT]
    assert network.rollback(CHECKPOINT) == {"checkpoint": CHECKPOINT, "result": "reverted"}
    assert system.commands()[-1] == [*GDBUS, NM + "CheckpointRollback", CHECKPOINT]
    calls = len(system.calls)
    with pytest.raises(ValueError):
        network.confirm(f"{CHECKPOINT}' ; rm")
    assert len(system.calls) == calls


def test_status_lists_pending_checkpoint(system):
    answer_status(system)
    system.add([*GDBUS, "org.freedesktop.DBus.Properties.Get"], f"(<[objectpath '{CHECKPOINT}']>,)\n")
    assert network.status()["pendingCheckpoints"] == [CHECKPOINT]


def test_activation_waits_longer_than_the_default_timeout(system, config):
    network.wifi_connect("Home", None, "s3cret")
    assert system.calls[-1]["args"][1:3] == ["--wait", "45"] and system.calls[-1]["timeout"] == 50
    answer_checkpoint(system)
    network.apply_profile("1111-aaaa", "enx00e04c")
    up = next(call for call in system.calls if call["args"][3:5] == ["connection", "up"] and "1111-aaaa" in call["args"])
    assert up["args"][1:3] == ["--wait", "20"] and up["timeout"] == 25


def test_successful_apply_gives_the_user_a_full_rollback_window(system, config):
    answer_checkpoint(system)
    network.apply_profile("1111-aaaa", "enx00e04c")
    assert system.commands()[-1] == [*GDBUS, NM + "CheckpointAdjustRollbackTimeout", CHECKPOINT, "30"]


def test_failed_first_wifi_connection_removes_the_new_profile(system):
    system.add(["nmcli", "--wait", "45", "connection", "up"], code=4, stderr="Error: Secrets were required, but not provided\n")
    with pytest.raises(RuntimeError, match="Secrets were required"):
        network.wifi_connect("Home", None, "wrong")
    assert system.commands()[-1] == ["nmcli", "connection", "delete", "id", "Home"]


def test_failed_known_wifi_keeps_its_profile(system):
    system.add(CONNECTIONS, "Home:2222-bbbb:802-11-wireless\n")
    system.add(["nmcli", "--wait", "45", "connection", "up"], code=4, stderr="Error: Secrets were required, but not provided\n")
    with pytest.raises(RuntimeError):
        network.wifi_connect("Home", None, "wrong")
    assert not any(command[1:3] == ["connection", "delete"] for command in system.commands())


def test_missing_nmcli_is_reported(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError("nmcli")

    monkeypatch.setattr(subprocess, "run", missing)
    with pytest.raises(RuntimeError, match="nmcli"):
        network.devices()
