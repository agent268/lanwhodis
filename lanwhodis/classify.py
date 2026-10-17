"""Weighted-evidence device classifier.

Every signal (OUI vendor, mDNS/UPnP/WS-Discovery services, open ports, names, banners) casts votes
{device_type: weight}. Votes for the same type combine with noisy-OR, so many weak hints add up but
never exceed certainty. Generic types ("iot", "computer") only win when no specific type has
reasonable support. The rules themselves are data: see rules.py and lanwhodis/data/rules/*.toml.
"""
from __future__ import annotations

import re

from . import devtypes, osdetect, recog, rules
from .model import Device, Evidence

# Device types that can plausibly run Windows (PCs, servers, Windows handhelds like ROG Ally, signage
# players). Everything else - cameras, doorbells, TVs, plugs, printers, routers ... - does not.
WINDOWS_PLAUSIBLE = {"computer", "laptop", "server", "handheld_console", "media_server", "signage",
                     "nas", "unknown"}

SPECIFIC_THRESHOLD = 0.45   # a non-generic type at/above this beats any generic type
UNKNOWN_BELOW = 0.20

Votes = dict[str, float]

# "Windows 11 / Server 2025 (build 26100)": the same build number ships as a client and a server OS
_AMBIGUOUS_WINDOWS = re.compile(r"^(?P<client>.+?) / (?P<server>Server .+?) \(build (?P<build>\d+)\)$")


def _vote(ev: list[Evidence], source: str, votes: Votes, detail: str) -> None:
    for t, w in votes.items():
        ev.append(Evidence(source, t, w, detail))


def gather(d: Device) -> list[Evidence]:
    rs = rules.get()
    ev: list[Evidence] = []

    if d.vendor:
        v = d.vendor.lower()
        for rx, votes in rs.vendor:
            if rx.search(v):
                _vote(ev, "oui", votes, d.vendor)

    sv = d.facts.get("snmp_vendor")      # IANA enterprise behind the SNMP sysObjectID
    if sv:
        for rx, votes in rs.vendor:
            if rx.search(sv.lower()):
                _vote(ev, "snmp", votes, sv)

    for key in d.services:
        votes = rs.services.get(key.lower())
        if votes:
            _vote(ev, key.split(":", 1)[0], votes, key)

    for p in d.open_ports:
        votes = rs.ports.get(p)
        if votes:
            _vote(ev, "port", votes, f"tcp/{p}")

    names = [n for n in ([d.hostname] + list(d.names.values())) if n]
    for n in names:
        nl = n.lower()
        for rx, votes in rs.names:
            if rx.search(nl):
                _vote(ev, "name", votes, n)

    blobs = ([d.model] if d.model else []) + d.text
    for b in blobs:
        bl = b.lower()
        for rx, votes in rs.text:
            if rx.search(bl):
                _vote(ev, "text", votes, b[:80])

    for m in d.recog:       # Rapid7 Recog banner fingerprints (filled in by recog.annotate)
        for key, which in (("hw.device", "hw"), ("os.device", "os")):
            votes = rs.recog_devices.get(m.params.get(key, ""))
            if votes:
                c = recog.certainty(m, which)
                _vote(ev, "recog", {t: w * c for t, w in votes.items()}, f"{m.db}: {m.description}"[:80])
        hw_vendor = m.params.get("hw.vendor")
        if hw_vendor:
            for rx, votes in rs.vendor:
                if rx.search(hw_vendor.lower()):
                    _vote(ev, "recog", votes, f"{m.db}: {hw_vendor}"[:80])

    osdetect.detect(d)
    if d.os_hint:
        _vote(ev, "os", osdetect.type_votes(d), d.os_label)
    if d.is_gateway:
        _vote(ev, "gateway", {"router": .9, "gateway": .3}, "default gateway")
    if d.random_mac:
        _vote(ev, "mac", {"phone": .25, "laptop": .1, "tablet": .1}, "randomized MAC")
    return ev


def classify(d: Device) -> Device:
    d.auto_type = None          # a fresh verdict; LabelStore.apply records it and overlays user corrections
    d.evidence = gather(d)
    scores: dict[str, float] = {}
    for e in d.evidence:
        scores[e.device_type] = 1 - (1 - scores.get(e.device_type, 0.0)) * (1 - e.weight)

    specific = {t: s for t, s in scores.items() if not devtypes.is_generic(t)}
    best_specific = max(specific, key=specific.get, default=None)
    if best_specific and specific[best_specific] >= SPECIFIC_THRESHOLD - 1e-9:   # noisy-OR float slack
        d.device_type, d.confidence = best_specific, min(specific[best_specific], .99)
    elif scores:
        # generic types are penalised slightly so a weak specific guess can still edge them out
        pick = max(scores, key=lambda t: scores[t] * (0.85 if devtypes.is_generic(t) else 1.0))
        d.device_type, d.confidence = pick, min(scores[pick], .99)
    else:
        d.device_type, d.confidence = "unknown", 0.0

    if d.confidence < UNKNOWN_BELOW:
        d.device_type = "unknown"
    # A TTL-only "Windows" guess is the same hint embedded stacks give; once the type is settled by
    # stronger evidence, drop it if that type doesn't realistically run Windows (doorbell, TV, ...).
    if (d.os_hint == "Windows" and d.os_detail == "TTL guess"
            and d.device_type not in WINDOWS_PLAUSIBLE):
        d.os_hint = d.os_detail = None
        d.os_confidence = 0.0
    if d.os_hint == "Windows" and d.os_detail:      # client/server builds share numbers: type decides
        m = _AMBIGUOUS_WINDOWS.match(d.os_detail)
        if m:
            name = f"Windows {m['server']}" if d.device_type == "server" else m["client"]
            d.os_detail = f"{name} (build {m['build']})"
    if d.os_hint == "iOS" and d.device_type == "tablet":
        d.os_hint = "iPadOS"        # iOS and iPadOS share every network signal; the device type decides
    return d
