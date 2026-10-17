"""Interfaces, default gateways and the OS neighbor (ARP) table."""
from __future__ import annotations

import ipaddress
import re
import sys

import psutil

from .. import oui
from .base import Iface, run_cmd

MAX_PREFIX_SPAN = 22   # never sweep anything bigger than a /22 (1022 hosts)

# Host-only / tunnel adapters are not "the LAN": scanning them just finds this machine's own bridge.
_VIRTUAL = re.compile(r"vethernet|wsl|hyper-v|docker|^veth|virbr|^br-|vmnet|vboxnet|tailscale|zerotier|"
                      r"^tun\d|^tap\d|loopback|^lo$|bluetooth", re.I)


def list_interfaces(include_virtual: bool = False) -> list[Iface]:
    out: list[Iface] = []
    stats = psutil.net_if_stats()
    for name, addrs in psutil.net_if_addrs().items():
        st = stats.get(name)
        if st is not None and not st.isup:
            continue
        if not include_virtual and _VIRTUAL.search(name):
            continue
        mac = next((a.address for a in addrs if a.family == psutil.AF_LINK), None)
        for a in addrs:
            if a.family.name != "AF_INET" or not a.netmask:
                continue
            ip = ipaddress.ip_address(a.address)
            if ip.is_loopback or ip.is_link_local:
                continue
            net = full = ipaddress.ip_network(f"{a.address}/{a.netmask}", strict=False)
            if net.prefixlen < MAX_PREFIX_SPAN:
                net = ipaddress.ip_network(f"{a.address}/24", strict=False)
            if net.prefixlen >= 31:
                continue
            out.append(Iface(name=name, ip=a.address, network=net, mac=oui.normalize_mac(mac or ""),
                             full_network=full if full != net else None))
    return out


def default_gateways() -> set[str]:
    gws: set[str] = set()
    if sys.platform == "win32":
        for line in run_cmd(["route", "print", "-4", "0.0.0.0"]).splitlines():
            m = re.match(r"\s*0\.0\.0\.0\s+0\.0\.0\.0\s+(\d+\.\d+\.\d+\.\d+)\s", line)
            if m:
                gws.add(m.group(1))
    else:
        for line in run_cmd(["ip", "-4", "route", "show", "default"]).splitlines():
            m = re.search(r"default via (\d+\.\d+\.\d+\.\d+)", line)
            if m:
                gws.add(m.group(1))
        if not gws:
            try:  # /proc/net/route stores the gateway as little-endian hex
                with open("/proc/net/route") as f:
                    next(f)
                    for line in f:
                        p = line.split()
                        if p[1] == "00000000":
                            gws.add(str(ipaddress.ip_address(int(p[2], 16).to_bytes(4, "little"))))
            except OSError:
                pass
    return gws


# Linux puts "dev eth0 lladdr" between IP and MAC, so the gap must allow digits.
_ARP_LINE = re.compile(r"(\d+\.\d+\.\d+\.\d+)\s.*?((?:[0-9a-fA-F]{2}[-:]){5}[0-9a-fA-F]{2})(?![0-9a-fA-F:-])")


def read_arp() -> dict[str, str]:
    """ip -> mac from the OS neighbor cache, excluding broadcast/multicast/empty entries."""
    text = run_cmd(["arp", "-a"] if sys.platform == "win32" else ["ip", "-4", "neigh"])
    if not text.strip() and sys.platform != "win32":
        try:
            text = open("/proc/net/arp").read()
        except OSError:
            text = ""
    table: dict[str, str] = {}
    for line in text.splitlines():
        m = _ARP_LINE.search(line)
        if not m:
            continue
        ip, mac = m.group(1), oui.normalize_mac(m.group(2))
        if not mac or mac in ("00:00:00:00:00:00", "ff:ff:ff:ff:ff:ff") or mac.startswith("01:00:5e"):
            continue
        if ipaddress.ip_address(ip).is_multicast or ip.endswith(".255"):
            continue
        table[ip] = mac
    return table
