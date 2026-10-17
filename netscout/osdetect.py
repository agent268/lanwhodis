"""Unprivileged OS / platform fingerprinting.

Signals: ICMP TTL, SSH/HTTP/UPnP/RTSP banner strings, Apple model identifiers, well-known port
signatures, hostnames and vendor. Like the type classifier, each signal votes {os_family: weight},
combined by noisy-OR. Passive TCP/IP-stack and DHCP fingerprinting need raw sockets and are
deliberately out of scope here.
"""
from __future__ import annotations

import re

from .model import Device, Evidence

MIN_CONFIDENCE = .25

Rule = tuple[str, str, str | None, float]   # regex, family, detail ("\\1" = first group), weight

# Matched against lowercase blobs: banners, UPnP SERVER, model strings, names, HTTP titles.
_TEXT: list[Rule] = [
    (r"^local-os: windows", "Windows", None, .99),
    (r"^local-os: darwin", "macOS", None, .99),
    (r"^local-os: linux \| (.+)", "Linux", r"\1", .99),
    (r"^local-os: linux \|.*steamos", "Linux", "SteamOS", .995),
    (r"^local-os: linux", "Linux", None, .99),
    (r"openssh_for_windows", "Windows", None, .95),
    (r"openssh[\w.]* ubuntu", "Linux", "Ubuntu", .9),
    (r"openssh[\w.]* debian|openssh[\w.]* \+deb", "Linux", "Debian", .9),
    (r"raspbian|raspios|raspberry pi os", "Linux", "Raspberry Pi OS", .9),
    (r"openssh[\w.]* freebsd|freebsd", "FreeBSD", None, .85),
    (r"openssh[\w.]* openbsd", "OpenBSD", None, .85),
    (r"dropbear", "Linux", "embedded (Dropbear)", .5),
    (r"openssh[_ ]([\d.]+)", "Linux", None, .25),          # OpenSSH default: Unix-like, weakly Linux
    (r"microsoft-windows/(\d+\.\d+)", "Windows", r"NT \1", .95),
    (r"microsoft-(httpapi|iis)|\bwin(32|64)\b", "Windows", None, .8),
    (r"\bwindows\b", "Windows", None, .4),
    (r"linux/(\d+\.\d+(?:\.\d+)?)", "Linux", r"kernel \1", .8),
    (r"\blinux\b|\bubuntu\b|\bdebian\b|\bfedora\b", "Linux", None, .6),
    (r"uhttpd|openwrt", "OpenWrt", None, .9),
    (r"lighttpd|boa/|goahead|mini_httpd|thttpd|micro_httpd|mbedthis|rompager", "Linux", "embedded", .45),
    (r"darwin|mac ?os ?x|macos", "macOS", None, .85),
    (r"macbook|macmini|imac|macpro|macstudio", "macOS", None, .9),
    (r"iphone\d+,\d+", "iOS", None, .97),
    (r"ipad\d+,\d+", "iPadOS", None, .97),
    (r"appletv\d", "tvOS", None, .97),
    (r"audioaccessory", "audioOS", "HomePod", .95),
    (r"\bandroid ?tv|google tv", "Android", "TV", .85),
    (r"fire ?tv|\baft[a-z]", "Fire OS", None, .85),
    (r"\bandroid\b", "Android", None, .7),
    (r"\broku\b", "Roku OS", None, .92),
    (r"webos|lgwebostv", "webOS", None, .92),
    (r"tizen", "Tizen", None, .92),
    (r"steam ?deck|steamos", "Linux", "SteamOS", .85),
    (r"xbox", "Xbox OS", None, .85),
    (r"playstation|\bps[345]\b", "PlayStation OS", None, .8),
    (r"routeros|mikrotik", "RouterOS", None, .92),
    (r"edgeos|edgerouter", "EdgeOS", None, .9),
    (r"esxi|vmware esx", "ESXi", None, .92),
    (r"diskstation|synology|dsm", "DSM", None, .8),
    (r"truenas|freenas", "FreeBSD", "TrueNAS", .7),
    (r"pfsense|opnsense", "FreeBSD", "firewall distro", .85),
    (r"home assistant|hassio", "Linux", "Home Assistant OS", .7),
    (r"esphome|tasmota|wled|esp32|esp8266", "Embedded", "ESP firmware", .85),
]

_PORT: dict[int, tuple[str, str | None, float]] = {
    3389: ("Windows", None, .5), 135: ("Windows", None, .5), 5985: ("Windows", None, .4),
    62078: ("iOS", None, .9), 5555: ("Android", None, .5), 548: ("macOS", None, .4),
    8060: ("Roku OS", None, .9), 8291: ("RouterOS", None, .3), 5353: ("Linux", None, 0.0),
}

_VENDOR: list[tuple[str, str, str | None, float]] = [
    (r"raspberry pi", "Linux", "Raspberry Pi OS", .5),
    (r"valve corp", "Linux", "SteamOS", .35),
    (r"espressif", "Embedded", "ESP firmware", .5),
    (r"microsoft", "Windows", None, .15),
    (r"\broku\b", "Roku OS", None, .8),
    (r"mikrotik|routerboard", "RouterOS", None, .8),
    (r"synology", "DSM", None, .6),
    (r"vmware", "ESXi", None, .2),
]

# TTL is a weak, family-level hint: it only separates Windows / Unix-like / network gear.
_TTL_VOTES = {
    64: {"Linux": .2, "macOS": .15, "iOS": .15, "Android": .15, "FreeBSD": .1},
    128: {"Windows": .5},
    255: {"Embedded": .2, "FreeBSD": .1},
}

# What each OS implies about the device type (scaled by OS confidence in classify.py).
OS_TYPE_VOTES: dict[tuple[str, str | None], dict[str, float]] = {
    ("Windows", None): {"computer": .4, "laptop": .05},
    ("macOS", None): {"computer": .45, "laptop": .2},
    ("iOS", None): {"phone": .6, "tablet": .2},
    ("iPadOS", None): {"tablet": .9},
    ("tvOS", None): {"streaming": .9},
    ("audioOS", None): {"speaker": .9},
    ("Android", None): {"phone": .4, "tablet": .12, "tv": .1},
    ("Android", "TV"): {"tv": .6, "streaming": .3},
    ("Fire OS", None): {"streaming": .5, "tv": .3, "tablet": .15},
    ("Roku OS", None): {"streaming": .9},
    ("webOS", None): {"tv": .9},
    ("Tizen", None): {"tv": .85},
    ("Xbox OS", None): {"game_console": .9},
    ("PlayStation OS", None): {"game_console": .9},
    ("Linux", "SteamOS"): {"handheld_console": .5, "computer": .2},
    ("Linux", "Raspberry Pi OS"): {"raspberry_pi": .6},
    ("Linux", "Ubuntu"): {"server": .2, "computer": .15},
    ("Linux", "Debian"): {"server": .25, "computer": .1},
    ("Linux", "Home Assistant OS"): {"hub": .6, "server": .2},
    ("Linux", "embedded"): {"iot": .25, "router": .1},
    ("Linux", "embedded (Dropbear)"): {"router": .3, "iot": .2},
    ("Linux", None): {"server": .1},
    ("OpenWrt", None): {"router": .8, "access_point": .2},
    ("RouterOS", None): {"router": .9},
    ("EdgeOS", None): {"router": .9},
    ("ESXi", None): {"server": .9},
    ("DSM", None): {"nas": .9},
    ("FreeBSD", None): {"server": .2, "router": .15},
    ("FreeBSD", "firewall distro"): {"router": .8},
    ("FreeBSD", "TrueNAS"): {"nas": .8},
    ("Embedded", "ESP firmware"): {"iot": .6},
    ("Embedded", None): {"iot": .2},
}

_TEXT_C = [(re.compile(p, re.I), fam, det, w) for p, fam, det, w in _TEXT]
_VENDOR_C = [(re.compile(p, re.I), fam, det, w) for p, fam, det, w in _VENDOR]


def _blobs(d: Device) -> list[str]:
    out = list(d.text) + [x for x in (d.model, d.hostname) if x] + list(d.names.values())
    out += [v for k, v in d.facts.items() if k.endswith(("_server", "_banner", "_title")) or k == "ssdp_server"]
    return out


def _ttl_votes(ttl: int) -> dict[str, float]:
    initial = next((i for i in (64, 128, 255) if ttl <= i), 255)
    # initial values of 32/60 are rare; anything <=64 is treated as the common 64 bucket
    return _TTL_VOTES[initial]


def detect(d: Device) -> None:
    """Fill d.os_hint / d.os_detail / d.os_confidence / d.os_evidence."""
    votes: list[tuple[str, str | None, float, str, str]] = []   # family, detail, weight, source, why

    for blob in _blobs(d):
        for rx, fam, det, w in _TEXT_C:
            m = rx.search(blob)
            if m:
                detail = m.expand(det) if det and "\\" in det else det
                votes.append((fam, detail, w, "text", blob[:70]))
    for p in d.open_ports:
        if p in _PORT and _PORT[p][2] > 0:
            fam, det, w = _PORT[p]
            votes.append((fam, det, w, "port", f"tcp/{p}"))
    if "netbios:nbstat" in d.services:
        votes.append(("Windows", None, .35, "netbios", "NetBIOS node status"))
    if d.vendor:
        for rx, fam, det, w in _VENDOR_C:
            if rx.search(d.vendor):
                votes.append((fam, det, w, "oui", d.vendor))
    ttl = d.facts.get("ttl")
    if ttl and ttl.isdigit():
        for fam, w in _ttl_votes(int(ttl)).items():
            votes.append((fam, None, w, "ttl", f"TTL {ttl}"))

    d.os_evidence = [Evidence(src, fam, w, why if not det else f"{why} → {det}")
                     for fam, det, w, src, why in votes]
    if not votes:
        d.os_hint = d.os_detail = None
        d.os_confidence = 0.0
        return

    score: dict[str, float] = {}
    for fam, _, w, _, _ in votes:
        score[fam] = 1 - (1 - score.get(fam, 0.0)) * (1 - w)
    fam = max(score, key=score.get)
    if score[fam] < MIN_CONFIDENCE:     # a lone weak hint (e.g. a Microsoft OUI) isn't worth showing
        d.os_hint = d.os_detail = None
        d.os_confidence = 0.0
        return
    # most confident detail among the winning family's votes (e.g. "Ubuntu" over "embedded")
    details = [(w, det) for f, det, w, _, _ in votes if f == fam and det]
    d.os_hint = fam
    d.os_detail = max(details)[1] if details else None
    d.os_confidence = min(score[fam], .99)
    if all(src == "ttl" for f, _, _, src, _ in votes if f == fam):
        d.os_detail, d.os_confidence = "TTL guess", min(d.os_confidence, .29)   # too weak to steer the type


def type_votes(d: Device) -> dict[str, float]:
    """Device-type votes implied by the detected OS, scaled by how sure we are of it."""
    if not d.os_hint:
        return {}
    base = OS_TYPE_VOTES.get((d.os_hint, d.os_detail)) or OS_TYPE_VOTES.get((d.os_hint, None)) or {}
    if d.os_detail == "TTL guess":
        # TTL alone can't pick a specific type, but "Windows-like" still says computer far more
        # often than it says anything else, so let it nudge generic types at half strength.
        base = OS_TYPE_VOTES.get((d.os_hint, None), {})
        return {t: w * .5 for t, w in base.items()}
    return {t: w * d.os_confidence for t, w in base.items()}
