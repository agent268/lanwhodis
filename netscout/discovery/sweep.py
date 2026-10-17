"""Host discovery: wake the ARP cache with NetBIOS node-status queries, then read it.

Sending any packet to an on-link IP forces the OS to ARP for it, and every live host
answers ARP regardless of its firewall. The NBSTAT query doubles as a name lookup for
Windows/Samba machines. No raw sockets or elevation needed.
"""
from __future__ import annotations

import platform
import socket
import struct
import sys
import time

from .base import ScanContext
from .net import read_arp

# NBSTAT request for the wildcard name "*": header + 34-byte encoded name + type NBSTAT(0x21) class IN
_NAME_ENC = b"\x20" + b"CK" + b"A" * 30 + b"\x00"   # first-level encoding of "*" (34 bytes)
_NBSTAT = b"\x13\x37\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00" + _NAME_ENC + b"\x00\x21\x00\x01"


def _parse_nbstat(data: bytes) -> tuple[dict[str, str], str | None]:
    """Return ({'workstation': NAME, 'workgroup': NAME, 'server': NAME}, mac)."""
    names: dict[str, str] = {}
    if len(data) < 57:
        return names, None
    count = data[56]
    off = 57
    for _ in range(count):
        if off + 18 > len(data):
            break
        raw = data[off:off + 15].decode("ascii", "replace").strip()
        suffix = data[off + 15]
        flags = struct.unpack(">H", data[off + 16:off + 18])[0]
        group = bool(flags & 0x8000)
        if suffix == 0x00 and not group:
            names.setdefault("workstation", raw)
        elif suffix == 0x00 and group:
            names.setdefault("workgroup", raw)
        elif suffix == 0x20 and not group:
            names.setdefault("server", raw)
        off += 18
    mac = None
    if off + 6 <= len(data):
        mac = ":".join(f"{b:02x}" for b in data[off:off + 6])
        if mac == "00:00:00:00:00:00":
            mac = None
    return names, mac


def local_os_text() -> str:
    """Exact OS of this machine, in the form osdetect's 'local-os:' rules expect."""
    system = platform.system().lower()
    pretty = ""
    if system == "linux":
        try:
            with open("/etc/os-release") as f:
                kv = dict(l.rstrip().split("=", 1) for l in f if "=" in l)
            pretty = kv.get("PRETTY_NAME", "").strip('"')
            if "microsoft" in platform.release().lower():
                pretty += " (WSL)"
        except OSError:
            pass
    return f"local-os: {system} | {pretty}"


def run(ctx: ScanContext) -> None:
    for iface in ctx.ifaces:
        if ctx.stop.is_set():
            return
        hosts = iface.hosts()
        ctx.log(f"sweep {iface.network}: probing {len(hosts)} addresses")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind((iface.ip, 0))
            sock.settimeout(0.05)
            for i, h in enumerate(hosts):
                if ctx.stop.is_set():
                    return
                try:
                    sock.sendto(_NBSTAT, (h, 137))
                except OSError:
                    pass
                if i % 32 == 0:
                    ctx.progress("sweep", i / max(len(hosts), 1) * 0.6)
                    time.sleep(0.005)
            deadline = time.time() + 2.0
            while time.time() < deadline and not ctx.stop.is_set():
                try:
                    data, (ip, _) = sock.recvfrom(1024)
                except socket.timeout:
                    continue
                except OSError:   # Windows reports ICMP port-unreachable as a connection reset
                    continue
                names, mac = _parse_nbstat(data)
                d = ctx.table.get(ip, mac)
                if names:
                    d.facts["netbios"] = ", ".join(f"{k}={v}" for k, v in names.items())
                    if "workstation" in names:
                        d.names.setdefault("netbios", names["workstation"])
                    d.services.add("netbios:nbstat")
                    d.text.append("windows")  # NBSTAT responders are overwhelmingly Windows/Samba
                    ctx.table.touch(d)
        finally:
            sock.close()

    time.sleep(0.5)
    arp = read_arp()
    for ip, mac in arp.items():
        if ctx.in_scope(ip) and ip not in {i.ip for i in ctx.ifaces}:
            d = ctx.table.get(ip, mac)
            if ip in ctx.gateways:
                d.is_gateway = True
            ctx.table.touch(d)
    # our own interfaces are devices on the network too
    for iface in ctx.ifaces:
        d = ctx.table.get(iface.ip, iface.mac)
        d.names.setdefault("local", socket.gethostname())
        d.facts["note"] = "this machine"
        d.text.append(local_os_text())
        d.services.add("local:self")
    ctx.progress("sweep", 1.0)
