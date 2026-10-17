"""Unprivileged OS / platform fingerprinting.

Signals: ICMP TTL, SSH/HTTP/UPnP/RTSP banner strings, Apple model identifiers, well-known port
signatures, hostnames and vendor. Like the type classifier, each signal votes {os_family: weight},
combined by noisy-OR. Passive TCP/IP-stack and DHCP fingerprinting need raw sockets and are
deliberately out of scope here. The rules are data: see rules.py and netscout/data/rules/os.toml.
"""
from __future__ import annotations

from . import rules
from .model import Device, Evidence

MIN_CONFIDENCE = .25     # below this a lone weak hint (e.g. a Microsoft OUI) isn't worth showing


def _blobs(d: Device) -> list[str]:
    out = list(d.text) + [x for x in (d.model, d.hostname) if x] + list(d.names.values())
    out += [v for k, v in d.facts.items() if k.endswith(("_server", "_banner", "_title")) or k == "ssdp_server"]
    return out


def _ttl_votes(ttl: int) -> dict[str, float]:
    table = rules.get().os_ttl
    initial = next((i for i in sorted(table) if ttl <= i), max(table, default=255))
    # initial values of 32/60 are rare; anything <=64 is treated as the common 64 bucket
    return table.get(initial, {})


def detect(d: Device) -> None:
    """Fill d.os_hint / d.os_detail / d.os_confidence / d.os_evidence."""
    rs = rules.get()
    votes: list[tuple[str, str | None, float, str, str]] = []   # family, detail, weight, source, why

    for blob in _blobs(d):
        for r in rs.os_text:
            m = r.rx.search(blob)
            if m:
                detail = m.expand(r.detail) if r.detail and "\\" in r.detail else r.detail
                votes.append((r.family, detail, r.weight, "text", blob[:70]))
    for p in d.open_ports:
        r = rs.os_ports.get(p)
        if r and r.weight > 0:
            votes.append((r.family, r.detail, r.weight, "port", f"tcp/{p}"))
    if "netbios:nbstat" in d.services:
        votes.append(("Windows", None, .35, "netbios", "NetBIOS node status"))
    if d.vendor:
        for r in rs.os_vendor:
            if r.rx.search(d.vendor):
                votes.append((r.family, r.detail, r.weight, "oui", d.vendor))
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
    if score[fam] < MIN_CONFIDENCE:
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
    table = rules.get().os_type_votes
    base = table.get((d.os_hint, d.os_detail)) or table.get((d.os_hint, None)) or {}
    if d.os_detail == "TTL guess":
        # TTL alone can't pick a specific type, but "Windows-like" still says computer far more
        # often than it says anything else, so let it nudge generic types at half strength.
        return {t: w * .5 for t, w in table.get((d.os_hint, None), {}).items()}
    return {t: w * d.os_confidence for t, w in base.items()}
