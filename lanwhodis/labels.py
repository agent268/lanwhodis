"""User corrections ("this is a camera called Porch Cam"), remembered across scans.

Stored as JSON in the user data dir, keyed by MAC address (stable across rescans; devices with no MAC
fall back to ``ip:<addr>``). A correction overrides the detected type/name, and keeps the scanner's own
verdict next to it plus a snapshot of the evidence it saw, so wrong guesses stay visible and can be
turned into rules (see suggest_rules).
"""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import threading
import time
from pathlib import Path

from . import devtypes, oui, paths
from .model import Device, Evidence

log = logging.getLogger("lanwhodis.labels")
_KEEP = object()          # "leave this field unchanged" (None means "clear it")


def key_for(d: Device) -> str:
    return d.mac or f"ip:{d.ip}"


def normalize_key(text: str, arp: dict[str, str] | None = None) -> str:
    """MAC in any notation, 'ip:1.2.3.4', or a bare IPv4 address (resolved through `arp`) -> store key."""
    t = text.strip()
    mac = oui.normalize_mac(t)
    if mac:
        return mac
    if t.lower().startswith("ip:"):
        return "ip:" + t[3:].strip()
    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", t):
        if arp and t in arp:
            return arp[t]
        raise ValueError(f"{t}: not in this machine's ARP table yet - run a scan first, or use the MAC address")
    raise ValueError(f"{text!r} is not a MAC address or IPv4 address")


def snapshot(d: Device) -> dict:
    """What the scanner saw when the user corrected it (for tuning rules later)."""
    return {"type": d.auto_type or d.device_type, "confidence": round(d.auto_confidence or d.confidence, 2),
            "vendor": d.vendor, "model": d.model, "os": d.os_label, "hostname": d.hostname,
            "services": sorted(d.services)[:40], "ports": sorted(d.open_ports)}


class LabelStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else paths.data_dir() / "labels.json"
        self._lock = threading.RLock()
        self._data: dict[str, dict] = self._load()

    # ---- persistence ---------------------------------------------------------------------
    def _load(self) -> dict[str, dict]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as e:
            self._quarantine(e)
            return {}
        if not isinstance(raw, dict) or not isinstance(raw.get("devices"), dict):
            self._quarantine(ValueError("unexpected structure"))
            return {}
        return {k: v for k, v in raw["devices"].items() if isinstance(v, dict)}

    def _quarantine(self, err: Exception) -> None:
        bad = self.path.with_suffix(f".bad-{int(time.time())}")
        try:
            self.path.replace(bad)
            log.warning("labels file unreadable (%s); moved to %s and starting empty", err, bad)
        except OSError:
            log.warning("labels file unreadable (%s); starting empty", err)

    def _save(self) -> None:
        paths.ensure(self.path.parent)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".labels-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                json.dump({"version": 1, "devices": self._data}, f, indent=2, sort_keys=True)
                f.write("\n")
            os.replace(tmp, self.path)          # atomic: a crash never leaves a half-written file
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # ---- access --------------------------------------------------------------------------
    def get(self, key: str) -> dict | None:
        with self._lock:
            e = self._data.get(key)
            return dict(e) if e else None

    def all(self) -> dict[str, dict]:
        with self._lock:
            return {k: dict(v) for k, v in self._data.items()}

    def set(self, key: str, *, name=_KEEP, type=_KEEP, notes=_KEEP, auto: dict | None = None) -> None:
        """Update fields of a correction. None/"" clears a field; omitted fields are unchanged."""
        if type is not _KEEP and type is not None and type not in devtypes.TYPES:
            raise ValueError(f"unknown device type {type!r}; valid: {', '.join(sorted(devtypes.TYPES))}")
        with self._lock:
            e = dict(self._data.get(key, {}))
            for field, val in (("name", name), ("type", type), ("notes", notes)):
                if val is _KEEP:
                    continue
                if val is None or (isinstance(val, str) and not val.strip()):
                    e.pop(field, None)
                else:
                    e[field] = val.strip() if isinstance(val, str) else val
            if auto is not None:
                e["auto"] = auto
            if any(k in e for k in ("name", "type", "notes")):
                e["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
                self._data[key] = e
            else:
                self._data.pop(key, None)
            self._save()

    def label_device(self, d: Device, **fields) -> None:
        self.set(key_for(d), auto=snapshot(d), **fields)

    def forget(self, key: str) -> bool:
        with self._lock:
            had = self._data.pop(key, None) is not None
            if had:
                self._save()
            return had

    # ---- applying to scan results ----------------------------------------------------------
    def apply(self, devices: list[Device]) -> None:
        """Overlay corrections on classified devices. Idempotent: the scanner's own verdict is kept in
        auto_type/auto_confidence and restored before each application."""
        with self._lock:
            for d in devices:
                if d.auto_type is not None:
                    d.device_type, d.confidence = d.auto_type, d.auto_confidence
                else:
                    d.auto_type, d.auto_confidence = d.device_type, d.confidence
                d.user_name = d.user_type = d.user_notes = None
                d.evidence = [x for x in d.evidence if x.source != "user"]
                e = self._data.get(key_for(d))
                if not e:
                    continue
                d.user_name, d.user_notes = e.get("name"), e.get("notes")
                if e.get("type") in devtypes.TYPES:
                    d.user_type = d.device_type = e["type"]
                    d.confidence = 1.0
                    d.evidence.insert(0, Evidence("user", e["type"], 1.0, "set by you"))


def suggest_rules(store: LabelStore) -> str:
    """Turn corrections into a ready-to-use custom vendor.toml: devices from the same vendor that you
    labelled with a single type become a moderate vote for that type. Review before using."""
    by_vendor: dict[str, set[str]] = {}
    for e in store.all().values():
        vendor, typ = (e.get("auto") or {}).get("vendor"), e.get("type")
        if vendor and typ:
            by_vendor.setdefault(vendor, set()).add(typ)
    out = ["# Suggested from your corrections (lanwhodis --suggest-rules). Save as <rules dir>/vendor.toml.",
           "# Each vote is moderate (0.6): a nudge for this vendor's other devices, not a certainty.", ""]
    for vendor, types in sorted(by_vendor.items()):
        if len(types) != 1:
            out.append(f"# skipped {vendor!r}: you labelled it as several types ({', '.join(sorted(types))})")
            continue
        pattern = re.escape(vendor.lower())
        literal = f"'{pattern}'" if "'" not in pattern else json.dumps(pattern)   # TOML literal strings can't hold '
        out += ["[[rule]]", f"match = {literal}", f"votes = {{ {next(iter(types))} = 0.6 }}", ""]
    if len(out) == 3:
        out.append("# (no corrections with a known vendor yet)")
    return "\n".join(out) + "\n"
