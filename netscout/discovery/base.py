"""Shared context and helpers for discovery modules."""
from __future__ import annotations

import ipaddress
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from typing import Callable

from ..model import DeviceTable


@dataclass
class Iface:
    name: str
    ip: str
    network: ipaddress.IPv4Network
    mac: str | None = None

    @property
    def label(self) -> str:
        return f"{self.name} — {self.ip} ({self.network})"

    def hosts(self) -> list[str]:
        return [str(h) for h in self.network.hosts() if str(h) != self.ip]


@dataclass
class ScanContext:
    table: DeviceTable
    ifaces: list[Iface]
    gateways: set[str] = field(default_factory=set)
    stop: threading.Event = field(default_factory=threading.Event)
    log: Callable[[str], None] = lambda msg: None
    progress: Callable[[str, float], None] = lambda stage, frac: None
    timeout: float = 4.0        # listening window for multicast protocols (seconds)
    port_scan: bool = True

    def in_scope(self, ip: str) -> bool:
        try:
            a = ipaddress.ip_address(ip)
        except ValueError:
            return False
        return any(a in i.network for i in self.ifaces)


def run_cmd(args: list[str], timeout: float = 8.0) -> str:
    """Run a helper command without flashing a console window on Windows."""
    kw: dict = {}
    if sys.platform == "win32":
        kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                           errors="replace", **kw)
        return r.stdout
    except (OSError, subprocess.SubprocessError):
        return ""
