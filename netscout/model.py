"""Core data model. No Qt or CLI imports: this module is reusable as a library."""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from . import devtypes, oui


# Human-assigned names beat protocol-derived ones; opaque ids (UUIDs, hex serials) are last resort.
_NAME_PRIORITY = ("friendly", "cast", "roku", "upnp", "local", "netbios", "dns", "mdns")
_OPAQUE = re.compile(r"^(?:[0-9a-f]{8}-[0-9a-f]{4}-|[0-9a-f]{12}$|fuchsia-)", re.I)


@dataclass
class Evidence:
    source: str        # oui, mdns, ssdp, wsd, netbios, port, http, hostname, gateway ...
    device_type: str   # key in devtypes.TYPES
    weight: float      # 0..1 confidence contributed by this one signal
    detail: str


@dataclass
class Device:
    ip: str
    mac: str | None = None
    vendor: str | None = None
    hostname: str | None = None
    names: dict[str, str] = field(default_factory=dict)       # source -> name
    model: str | None = None
    os_hint: str | None = None
    open_ports: set[int] = field(default_factory=set)
    services: set[str] = field(default_factory=set)           # e.g. "_airplay._tcp", "upnp:MediaRenderer"
    facts: dict[str, str] = field(default_factory=dict)       # misc key/values for details view
    text: list[str] = field(default_factory=list)             # free-text blobs for keyword rules
    is_gateway: bool = False
    random_mac: bool = False
    device_type: str = "unknown"
    confidence: float = 0.0
    evidence: list[Evidence] = field(default_factory=list)
    first_seen: float = field(default_factory=time.time)

    @property
    def display_name(self) -> str:
        candidates = [self.names.get(k) for k in _NAME_PRIORITY] + [self.hostname] + list(self.names.values())
        readable = [n for n in candidates if n and not _OPAQUE.match(n)]
        return (readable[0] if readable else None) or self.model or self.vendor or self.hostname or self.ip

    @property
    def type_label(self) -> str:
        return devtypes.label(self.device_type)

    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "mac": self.mac,
            "name": self.display_name,
            "hostname": self.hostname,
            "vendor": self.vendor,
            "model": self.model,
            "type": self.device_type,
            "type_label": self.type_label,
            "category": devtypes.category(self.device_type),
            "confidence": round(self.confidence, 2),
            "os_hint": self.os_hint,
            "is_gateway": self.is_gateway,
            "random_mac": self.random_mac,
            "open_ports": sorted(self.open_ports),
            "services": sorted(self.services),
            "names": dict(self.names),
            "facts": dict(self.facts),
            "evidence": [vars(e) for e in sorted(self.evidence, key=lambda e: -e.weight)],
        }


class DeviceTable:
    """Thread-safe collection of devices keyed by IP, shared by all discovery modules."""

    def __init__(self, on_update: Callable[[Device], None] | None = None):
        self._devices: dict[str, Device] = {}
        self._lock = threading.RLock()
        self._on_update = on_update

    def get(self, ip: str, mac: str | None = None) -> Device:
        with self._lock:
            d = self._devices.get(ip)
            if d is None:
                d = self._devices[ip] = Device(ip=ip)
            if mac and not d.mac:
                n = oui.normalize_mac(mac)
                if n:
                    d.mac = n
                    d.vendor = oui.lookup(n)
                    d.random_mac = oui.is_locally_administered(n)
            return d

    def has(self, ip: str) -> bool:
        with self._lock:
            return ip in self._devices

    def touch(self, device: Device) -> None:
        """Signal that a device changed (for live GUI updates)."""
        if self._on_update:
            self._on_update(device)

    def all(self) -> list[Device]:
        with self._lock:
            return sorted(self._devices.values(), key=lambda d: _ip_key(d.ip))


def _ip_key(ip: str) -> tuple:
    try:
        return tuple(int(p) for p in ip.split("."))
    except ValueError:
        return (999, ip)
