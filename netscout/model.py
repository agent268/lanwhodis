"""Core data model. No Qt or CLI imports: this module is reusable as a library."""
from __future__ import annotations

import re
import threading
import time
from urllib.parse import urlsplit, urlunsplit
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
    os_hint: str | None = None          # family: Windows, macOS, iOS, Linux, Roku OS ...
    os_detail: str | None = None        # e.g. Ubuntu, kernel 3.14, NT 10.0
    os_confidence: float = 0.0
    os_evidence: list[Evidence] = field(default_factory=list)
    open_ports: set[int] = field(default_factory=set)
    services: set[str] = field(default_factory=set)           # e.g. "_airplay._tcp", "upnp:MediaRenderer"
    facts: dict[str, str] = field(default_factory=dict)       # misc key/values for details view
    text: list[str] = field(default_factory=list)             # free-text blobs for keyword rules
    web_urls: dict[str, tuple[str, int]] = field(default_factory=dict)   # url -> (source, rank; lower wins)
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

    def add_web_url(self, url: str, source: str, rank: int) -> None:
        """Record a device-hosted admin page. Advertised URLs are untrusted input, so only the
        device's own IP or its own mDNS name is accepted (and rewritten to the IP); a spoofed or
        compromised device can't aim the 'open' action at some other site."""
        try:
            p = urlsplit(url.strip())
            port = p.port
        except ValueError:
            return
        own = {self.ip, (self.facts.get("mdns_host") or "").lower()}
        if p.scheme not in ("http", "https") or not p.hostname or p.hostname.lower() not in own:
            return
        clean = urlunsplit((p.scheme, self.ip + (f":{port}" if port else ""), p.path or "/", p.query, ""))
        if clean not in self.web_urls or rank < self.web_urls[clean][1]:
            self.web_urls[clean] = (source, rank)

    @property
    def web_url(self) -> str | None:
        """Best guess at the device's web UI: UPnP presentationURL > mDNS adminurl > mDNS http > probed port."""
        return min(self.web_urls, key=lambda u: (self.web_urls[u][1], u), default=None)

    @property
    def os_label(self) -> str:
        if not self.os_hint:
            return ""
        return f"{self.os_hint} ({self.os_detail})" if self.os_detail else self.os_hint

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
            "web_url": self.web_url,
            "web_urls": [{"url": u, "source": s}
                         for u, (s, r) in sorted(self.web_urls.items(), key=lambda kv: (kv[1][1], kv[0]))],
            "os": self.os_label,
            "os_family": self.os_hint,
            "os_detail": self.os_detail,
            "os_confidence": round(self.os_confidence, 2),
            "os_evidence": [vars(e) for e in sorted(self.os_evidence, key=lambda e: -e.weight)],
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
