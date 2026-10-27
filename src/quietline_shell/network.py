"""NetworkManager для оболочки: состояние устройств, Ethernet-профили объекта, Wi-Fi и откат.

Каждая команда `nmcli` передаётся списком аргументов через `run_nmcli`, вызовы D-Bus
NetworkManager — через `run_gdbus`. Пароль Wi-Fi приходит только через stdin. Смена
активной конфигурации идёт за контрольной точкой NetworkManager: без `confirm` через
`ROLLBACK_SECONDS` NetworkManager сам возвращает прежнюю конфигурацию.

Недавние профили хранятся в `$XDG_CONFIG_HOME/quietline/network.json` вида
`{"version": 1, "recent": {uuid: unix_time}}`.

Подкоманды `quietline-shell network` и их ответы:

- `status` — `{devices, wifi: {enabled}, profiles, pendingCheckpoints: [path]}`;
- `wifi-scan` — `{networks: [{ssid, signal, security, active, known}]}`;
- `wifi-radio --on|--off` — `{wifi: {enabled}}`;
- `wifi-connect --ssid S [--device D]`, пароль одной строкой в stdin (пусто — открытая
  сеть) — `{connected: true}`;
- `profile-save`, JSON профиля в stdin — `{profile}`;
- `profile-delete --uuid U` — `{deleted: U}`;
- `apply --uuid U --device D`, `dhcp --device D` — `{checkpoint, timeout}`;
- `confirm --checkpoint P`, `rollback --checkpoint P` — `{checkpoint, result: "kept" | "reverted"}`.

Устройство — `{device, type: "ethernet" | "wifi", state: "connected" | "connecting" |
"disconnected" | "unavailable", cable: bool | null, profile, uuid, addresses, gateway}`.
Профиль — `{uuid, name, method: "manual" | "auto", address, gateway, dns, neverDefault,
lastUsed}`.
"""

import argparse
import ipaddress
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, TextIO

from quietline_shell.config import atomic_write_json

DEVICE_FIELDS = (
    "GENERAL.DEVICE,GENERAL.TYPE,GENERAL.STATE,GENERAL.CONNECTION,GENERAL.CON-UUID,"
    "WIRED-PROPERTIES.CARRIER,IP4.ADDRESS,IP4.GATEWAY,IP6.ADDRESS"
)
PROFILE_FIELDS = "ipv4.method,ipv4.addresses,ipv4.gateway,ipv4.dns,ipv4.never-default"
ETHERNET = "802-3-ethernet"
WIFI = "802-11-wireless"
ROLLBACK_SECONDS = 30
# Сколько `nmcli --wait` ждёт активации Ethernet и Wi-Fi.
ACTIVATION_WAIT = 20
WIFI_WAIT = 45
DHCP_PROFILE = "Quietline DHCP"
NM_PATH = "/org/freedesktop/NetworkManager"

_ADDED = re.compile(r"\(([0-9a-fA-F-]+)\) successfully added")
_OBJECT = re.compile(r"objectpath '([^']+)'")
_CHECKPOINT = re.compile(r"/org/freedesktop/NetworkManager/Checkpoint/\d+")
# Путь в ответе `gdbus`: пометку `objectpath` получает только первый элемент массива.
_CHECKPOINT_IN_REPLY = re.compile(r"'(/org/freedesktop/NetworkManager/Checkpoint/\d+)'")
# Результат `CheckpointRollback` по устройствам: `{'<путь>': uint32 0, '<путь>': 3}`, 0 — успех.
_ROLLBACK_RESULT = re.compile(r"'(/org/freedesktop/NetworkManager/Devices/\d+)':\s*(?:uint32\s+)?(\d+)")
_ROLLBACK_ERRORS = {1: "device not found", 2: "device is not managed", 3: "rollback failed"}
# Префикс сети профиля объекта: шире /8 подсеть увела бы через кабель часть интернета.
MIN_PREFIX = 8
_INTERFACE = re.compile(r"[A-Za-z0-9_.:-]{1,15}")
_UUID = re.compile(r"[0-9a-fA-F-]{1,64}")


class ProfileError(ValueError):
    """Ошибка формы профиля; `field` — поле формы, по которому панель выбирает русский текст."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field


def run_nmcli(args: list[str], stdin: str | None = None, wait: int | None = None) -> str:
    """Выполняет `nmcli` с `LC_ALL=C`; с `wait` — `nmcli --wait`, таймаут на 5 с дольше.

    Ненулевой код — `RuntimeError` с текстом NetworkManager.
    """
    command = ["nmcli", "--wait", str(wait), *args] if wait else ["nmcli", *args]
    try:
        result = subprocess.run(
            command, input=stdin, capture_output=True, text=True, timeout=wait + 5 if wait else 10,
            check=False, env={**os.environ, "LC_ALL": "C"},
        )
    except FileNotFoundError as error:
        raise RuntimeError("NetworkManager (nmcli) is not installed") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("NetworkManager did not respond") from error
    if result.returncode:
        detail = (result.stderr or result.stdout).strip() or f"exit code {result.returncode}"
        raise RuntimeError(f"NetworkManager failed: {detail}")
    return result.stdout


def run_gdbus(method: str, *args: str, interface: str = "org.freedesktop.NetworkManager") -> str:
    """Вызывает метод объекта `/org/freedesktop/NetworkManager` на системной шине."""
    command = [
        "gdbus", "call", "--system", "--dest", "org.freedesktop.NetworkManager",
        "--object-path", NM_PATH, "--method", f"{interface}.{method}", *args,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    except FileNotFoundError as error:
        raise RuntimeError("gdbus is not installed: NetworkManager checkpoints are unavailable") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("NetworkManager did not respond") from error
    if result.returncode:
        raise RuntimeError(f"NetworkManager failed: {result.stderr.strip()}")
    return result.stdout


def split_terse(line: str) -> list[str]:
    """Делит строку `nmcli -t --escape yes` по неэкранированным `:`; `\\:` и `\\\\` раскрываются."""
    fields: list[str] = []
    current: list[str] = []
    escaped = False
    for char in line:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(char)
    fields.append("".join(current))
    return fields


def _key_value(line: str) -> tuple[str, str]:
    key, _, value = line.partition(":")
    return key, "".join(split_terse(value)) if "\\" in value else value


def _empty(value: str) -> str:
    return "" if value == "--" else value


def _state(value: str) -> str:
    """Код `GENERAL.STATE` NetworkManager → `connected`, `connecting`, `disconnected`, `unavailable`."""
    code = int(value.split(" ", 1)[0]) if value[:1].isdigit() else 0
    if code == 100:
        return "connected"
    if 40 <= code < 100:
        return "connecting"
    if code == 30:
        return "disconnected"
    return "unavailable"


def devices() -> list[dict[str, Any]]:
    """Ethernet- и Wi-Fi-устройства; `cable` — `None` у устройств без кабеля."""
    result: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in run_nmcli(["-t", "--escape", "yes", "-f", DEVICE_FIELDS, "device", "show"]).splitlines():
        if not line:
            continue
        key, value = _key_value(line)
        if key == "GENERAL.DEVICE":
            current = {
                "device": value, "type": "", "state": "unavailable", "cable": None,
                "profile": "", "uuid": "", "addresses": [], "gateway": None,
            }
            result.append(current)
        elif current is None:
            continue
        elif key == "GENERAL.TYPE":
            current["type"] = value
        elif key == "GENERAL.STATE":
            current["state"] = _state(value)
        elif key == "GENERAL.CONNECTION":
            current["profile"] = _empty(value)
        elif key == "GENERAL.CON-UUID":
            current["uuid"] = _empty(value)
        elif key == "WIRED-PROPERTIES.CARRIER":
            current["cable"] = value == "on"
        elif key.startswith(("IP4.ADDRESS[", "IP6.ADDRESS[")) and _empty(value):
            current["addresses"].append(value)
        elif key == "IP4.GATEWAY":
            current["gateway"] = _empty(value) or None
    return [item for item in result if item["type"] in ("ethernet", "wifi")]


def _connections() -> list[tuple[str, str, str]]:
    """Сохранённые соединения: имя, UUID, тип."""
    rows: list[tuple[str, str, str]] = []
    for line in run_nmcli(["-t", "--escape", "yes", "-f", "NAME,UUID,TYPE", "connection", "show"]).splitlines():
        fields = split_terse(line)
        if len(fields) == 3:
            rows.append((fields[0], fields[1], fields[2]))
    return rows


def recent_path() -> Path:
    directory = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(directory) / "quietline" / "network.json"


def recent() -> dict[str, int]:
    """Время последнего применения профилей; повреждённый или отсутствующий файл — пусто."""
    try:
        data = json.loads(recent_path().read_text(encoding="utf-8"))
        return {key: int(value) for key, value in data.get("recent", {}).items()}
    except (OSError, ValueError, AttributeError, TypeError):
        return {}


def mark_used(uuid: str) -> None:
    used = recent()
    used[uuid] = int(time.time())
    atomic_write_json(recent_path(), {"version": 1, "recent": used})


def _profile(name: str, uuid: str, used: dict[str, int]) -> dict[str, Any]:
    output = run_nmcli(["-t", "--escape", "yes", "-f", PROFILE_FIELDS, "connection", "show", "uuid", uuid])
    values = dict(_key_value(line) for line in output.splitlines() if line)
    addresses = _empty(values.get("ipv4.addresses", ""))
    return {
        "uuid": uuid,
        "name": name,
        "method": "manual" if values.get("ipv4.method") == "manual" else "auto",
        "address": addresses.split(",")[0] if addresses else None,
        "gateway": _empty(values.get("ipv4.gateway", "")) or None,
        "dns": [item for item in _empty(values.get("ipv4.dns", "")).split(",") if item],
        "neverDefault": values.get("ipv4.never-default") == "yes",
        "lastUsed": used.get(uuid),
    }


def wifi_enabled() -> bool:
    return run_nmcli(["-t", "-f", "WIFI", "radio"]).strip() == "enabled"


def pending_checkpoints() -> list[str]:
    """Незавершённые контрольные точки, в том числе созданные до перезапуска оболочки."""
    try:
        output = run_gdbus("Get", "org.freedesktop.NetworkManager", "Checkpoints",
                           interface="org.freedesktop.DBus.Properties")
    except RuntimeError:
        return []
    return _CHECKPOINT_IN_REPLY.findall(output)


def status() -> dict[str, Any]:
    used = recent()
    profiles = [
        _profile(name, uuid, used) for name, uuid, kind in _connections() if kind == ETHERNET and name != DHCP_PROFILE
    ]
    return {
        "devices": devices(),
        "wifi": {"enabled": wifi_enabled()},
        "profiles": profiles,
        "pendingCheckpoints": pending_checkpoints(),
    }


def _checkpoint_path(path: str) -> str:
    if not _CHECKPOINT.fullmatch(path or ""):
        raise ValueError(f"invalid checkpoint: {path!r}")
    return path


def _uuid(uuid: object) -> str:
    if not isinstance(uuid, str) or not _UUID.fullmatch(uuid):
        raise ValueError(f"invalid profile UUID: {uuid!r}")
    return uuid


def _activate(uuid: str, device: str) -> dict[str, Any]:
    """Включает профиль на адаптере за контрольной точкой, которая откатывается сама.

    Неудачная активация откатывается сразу. После удачной таймер отката запускается
    заново, чтобы у пользователя были полные `ROLLBACK_SECONDS` на проверку.
    """
    if not _INTERFACE.fullmatch(device or ""):
        raise ValueError(f"invalid network adapter name: {device!r}")
    try:
        device_path = _OBJECT.findall(run_gdbus("GetDeviceByIpIface", device))[0]
    except (RuntimeError, IndexError) as error:
        raise RuntimeError(f"network adapter {device} not found") from error
    created = _CHECKPOINT_IN_REPLY.findall(run_gdbus("CheckpointCreate", f"['{device_path}']", str(ROLLBACK_SECONDS), "0"))
    if not created:
        raise RuntimeError("NetworkManager did not return a checkpoint")
    checkpoint = created[0]
    try:
        run_nmcli(["connection", "up", "uuid", uuid, "ifname", device], wait=ACTIVATION_WAIT)
    except RuntimeError as error:
        try:
            _rollback(checkpoint)
        except RuntimeError as rollback_error:
            raise RuntimeError(f"{error}; {rollback_error}") from error
        raise
    run_gdbus("CheckpointAdjustRollbackTimeout", checkpoint, str(ROLLBACK_SECONDS))
    mark_used(uuid)
    return {"checkpoint": checkpoint, "timeout": ROLLBACK_SECONDS}


def apply_profile(uuid: str, device: str) -> dict[str, Any]:
    return _activate(_uuid(uuid), device)


def apply_dhcp(device: str) -> dict[str, Any]:
    """Включает DHCP на адаптере через профиль `DHCP_PROFILE`; профиль создаётся один раз."""
    uuid = next((uuid for name, uuid, kind in _connections() if name == DHCP_PROFILE and kind == ETHERNET), None)
    if uuid is None:
        output = run_nmcli([
            "connection", "add", "type", "ethernet", "con-name", DHCP_PROFILE, "ifname", "*",
            "connection.autoconnect", "no", "ipv4.method", "auto",
        ])
        match = _ADDED.search(output)
        if not match:
            raise RuntimeError("cannot create the DHCP profile")
        uuid = match.group(1)
    return _activate(uuid, device)


def confirm(checkpoint: str) -> dict[str, str]:
    run_gdbus("CheckpointDestroy", _checkpoint_path(checkpoint))
    return {"checkpoint": checkpoint, "result": "kept"}


def _rollback(checkpoint: str) -> None:
    """Откатывает контрольную точку; ненулевой результат любого устройства — `RuntimeError`."""
    output = run_gdbus("CheckpointRollback", checkpoint)
    failed = [
        f"{path}: {_ROLLBACK_ERRORS.get(int(code), f'result {code}')}"
        for path, code in _ROLLBACK_RESULT.findall(output) if int(code)
    ]
    if failed:
        raise RuntimeError("NetworkManager rollback failed for " + ", ".join(failed))


def rollback(checkpoint: str) -> dict[str, str]:
    _rollback(_checkpoint_path(checkpoint))
    return {"checkpoint": checkpoint, "result": "reverted"}


def validate_profile(data: object) -> dict[str, Any]:
    """Нормализованный профиль; ошибка формы — `ProfileError` с полем формы.

    Без явного `neverDefault: false` профиль не становится маршрутом в интернет.
    """
    if not isinstance(data, dict):
        raise ProfileError("profile", "profile must be a JSON object")
    name = str(data.get("name") or "").strip()
    if not name or len(name) > 64 or any(ord(char) < 32 for char in name):
        raise ProfileError("name", "profile name must be 1 to 64 printable characters")
    method = data.get("method", "manual")
    if method not in ("manual", "auto"):
        raise ProfileError("method", f"unknown address method: {method!r}")
    address = gateway = None
    if method == "manual":
        address = str(data.get("address") or "").strip()
        if "/" not in address:
            raise ProfileError("prefix", f"address needs a network prefix, for example 10.42.0.5/24: {address!r}")
        try:
            interface = ipaddress.IPv4Interface(address)
        except ValueError as error:
            raise ProfileError("address", f"invalid IPv4 address: {address!r}") from error
        network = interface.network
        if network.prefixlen < MIN_PREFIX:
            raise ProfileError("prefix", f"network prefix must be /{MIN_PREFIX} to /32: {address!r}")
        if network.prefixlen < 31 and interface.ip in (network.network_address, network.broadcast_address):
            raise ProfileError("address", f"address is the network or broadcast address of {network}: {address!r}")
        address = str(interface)
        if data.get("gateway"):
            try:
                gateway = str(ipaddress.IPv4Address(str(data["gateway"]).strip()))
            except ValueError as error:
                raise ProfileError("gateway", f"invalid gateway address: {data['gateway']!r}") from error
    servers = data.get("dns") or []
    if not isinstance(servers, list):
        raise ProfileError("dns", f"DNS servers must be a list of addresses: {servers!r}")
    dns: list[str] = []
    for item in servers:
        try:
            if not isinstance(item, str):
                raise ValueError(item)
            dns.append(str(ipaddress.ip_address(item.strip())))
        except ValueError as error:
            raise ProfileError("dns", f"invalid DNS server address: {item!r}") from error
    uuid = data.get("uuid")
    if uuid is not None:
        try:
            _uuid(uuid)
        except ValueError as error:
            raise ProfileError("profile", str(error)) from error
    return {
        "uuid": uuid, "name": name, "method": method, "address": address, "gateway": gateway,
        "dns": dns, "neverDefault": data.get("neverDefault", True) is not False,
    }


def save_profile(data: object) -> dict[str, Any]:
    """Создаёт или изменяет Ethernet-профиль объекта: без автоподключения, IPv6 выключен."""
    profile = validate_profile(data)
    existing = profile["uuid"] is not None
    settings = ["connection.autoconnect", "no", "ipv4.method", profile["method"]]
    if profile["method"] == "manual":
        settings += ["ipv4.addresses", profile["address"]]
    elif existing:
        settings += ["ipv4.addresses", ""]
    settings += ["ipv4.never-default", "yes" if profile["neverDefault"] else "no"]
    if profile["gateway"]:
        settings += ["ipv4.gateway", profile["gateway"]]
    elif existing:
        settings += ["ipv4.gateway", ""]
    if profile["dns"]:
        settings += ["ipv4.dns", ",".join(profile["dns"])]
    elif existing:
        settings += ["ipv4.dns", ""]
    settings += ["ipv6.method", "disabled"]
    if existing:
        run_nmcli(["connection", "modify", "uuid", profile["uuid"], "connection.id", profile["name"], *settings])
    else:
        output = run_nmcli(["connection", "add", "type", "ethernet", "con-name", profile["name"], "ifname", "*", *settings])
        match = _ADDED.search(output)
        profile["uuid"] = match.group(1) if match else None
    profile["lastUsed"] = recent().get(profile["uuid"])
    return profile


def delete_profile(uuid: str) -> dict[str, str]:
    run_nmcli(["connection", "delete", "uuid", _uuid(uuid)])
    return {"deleted": uuid}


def set_wifi(enabled: bool) -> dict[str, Any]:
    run_nmcli(["radio", "wifi", "on" if enabled else "off"])
    return {"wifi": {"enabled": wifi_enabled()}}


def wifi_scan() -> list[dict[str, Any]]:
    """Сети по одной на SSID: активная, иначе с самым сильным сигналом; активная — первой."""
    known = {name for name, _uuid, kind in _connections() if kind == WIFI}
    best: dict[str, dict[str, Any]] = {}
    output = run_nmcli(["-t", "--escape", "yes", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "auto"])
    for line in output.splitlines():
        fields = split_terse(line)
        if len(fields) != 4 or not fields[1]:
            continue
        network = {
            "ssid": fields[1], "signal": int(fields[2] or 0), "security": _empty(fields[3]),
            "active": fields[0] == "*", "known": fields[1] in known,
        }
        previous = best.get(network["ssid"])
        if previous is None or network["active"] or (not previous["active"] and network["signal"] > previous["signal"]):
            best[network["ssid"]] = network
    return sorted(best.values(), key=lambda item: (not item["active"], -item["signal"]))


def wifi_connect(ssid: str, device: str | None, password: str) -> dict[str, bool]:
    """Подключает Wi-Fi; пароль идёт в `nmcli` только через stdin (`passwd-file /dev/stdin`).

    Профиль, созданный этой попыткой, удаляется при неудаче: иначе сеть с неверным
    паролем считалась бы известной и больше не спрашивала пароль.
    """
    if not ssid or len(ssid.encode()) > 32 or any(ord(char) < 32 for char in ssid):
        raise ValueError(f"invalid Wi-Fi network name: {ssid!r}")
    created = not any(name == ssid and kind == WIFI for name, _uuid, kind in _connections())
    if created:
        command = ["connection", "add", "type", "wifi", "con-name", ssid, "ssid", ssid, "ifname", device or "*"]
        if password:
            command += ["wifi-sec.key-mgmt", "wpa-psk"]
        run_nmcli(command)
    command = ["connection", "up", "id", ssid]
    if device:
        command += ["ifname", device]
    try:
        if password:
            run_nmcli([*command, "passwd-file", "/dev/stdin"], wait=WIFI_WAIT,
                      stdin=f"802-11-wireless-security.psk:{password}\n")
        else:
            run_nmcli(command, wait=WIFI_WAIT)
    except RuntimeError:
        if created:
            try:
                run_nmcli(["connection", "delete", "id", ssid])
            except RuntimeError:
                pass
        raise
    return {"connected": True}


def add_parser(commands: argparse._SubParsersAction) -> None:
    """Подкоманды `quietline-shell network …`."""
    parser = commands.add_parser("network", help="manage NetworkManager devices, site profiles and Wi-Fi")
    actions = parser.add_subparsers(dest="action", required=True, metavar="ACTION")
    actions.add_parser("status", help="print devices, Wi-Fi, profiles and pending checkpoints")
    actions.add_parser("wifi-scan", help="print visible Wi-Fi networks")
    radio = actions.add_parser("wifi-radio", help="turn Wi-Fi on or off")
    switch = radio.add_mutually_exclusive_group(required=True)
    switch.add_argument("--on", dest="enabled", action="store_true")
    switch.add_argument("--off", dest="enabled", action="store_false")
    connect = actions.add_parser("wifi-connect", help="connect to Wi-Fi; the password is read from stdin")
    connect.add_argument("--ssid", required=True)
    connect.add_argument("--device")
    actions.add_parser("profile-save", help="create or update a site profile read from stdin as JSON")
    delete = actions.add_parser("profile-delete", help="delete a site profile")
    delete.add_argument("--uuid", required=True)
    apply = actions.add_parser("apply", help="apply a profile to an adapter behind a checkpoint")
    apply.add_argument("--uuid", required=True)
    apply.add_argument("--device", required=True)
    dhcp = actions.add_parser("dhcp", help="switch an adapter to DHCP behind a checkpoint")
    dhcp.add_argument("--device", required=True)
    for name, text in (("confirm", "keep the configuration of a checkpoint"),
                       ("rollback", "restore the configuration saved by a checkpoint")):
        actions.add_parser(name, help=text).add_argument("--checkpoint", required=True)


def run(args: argparse.Namespace, stdin: TextIO) -> dict[str, Any]:
    """Выполняет подкоманду `network`; ответ — словарь для одной строки JSON."""
    match args.action:
        case "status":
            return status()
        case "wifi-scan":
            return {"networks": wifi_scan()}
        case "wifi-radio":
            return set_wifi(args.enabled)
        case "wifi-connect":
            return wifi_connect(args.ssid, args.device, stdin.readline().rstrip("\n"))
        case "profile-save":
            try:
                data = json.loads(stdin.read())
            except ValueError as error:
                raise ProfileError("profile", "profile must be valid JSON") from error
            return {"profile": save_profile(data)}
        case "profile-delete":
            return delete_profile(args.uuid)
        case "apply":
            return apply_profile(args.uuid, args.device)
        case "dhcp":
            return apply_dhcp(args.device)
        case "confirm":
            return confirm(args.checkpoint)
        case _:
            return rollback(args.checkpoint)
