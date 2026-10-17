"""Presence and change history: what showed up, left, returned or moved between scans (SQLite).

Devices are keyed like corrections (MAC, else ``ip:<addr>``). Each device belongs to the network (CIDR)
it was seen on, and changes are tracked per network:

* the first scan that covers a network is a silent *baseline* (no "new" flood on day one);
* a device missing from a scan of its network gets ``missed += 1``; WiFi devices nap and miss single
  scans all the time, so it is only reported as *left* after MISSING_AFTER consecutive misses and as
  *returned* when it reappears after that;
* a known device showing up at a different IP is reported as *ip_changed*.

Scanning only one interface never disturbs devices recorded on another network.
"""
from __future__ import annotations

import ipaddress
import logging
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path

from . import paths
from .labels import key_for
from .model import Device

log = logging.getLogger("netscout.history")

MISSING_AFTER = 2        # consecutive scans a device must miss before it counts as "left"
RETENTION_DAYS = 365

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (id INTEGER PRIMARY KEY, started REAL NOT NULL, count INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS scan_networks (
    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE, network TEXT NOT NULL,
    PRIMARY KEY (scan_id, network));
CREATE TABLE IF NOT EXISTS devices (
    key TEXT PRIMARY KEY, mac TEXT, name TEXT, type TEXT, vendor TEXT, os TEXT, last_ip TEXT, network TEXT,
    first_seen REAL NOT NULL, last_seen REAL NOT NULL, seen_count INTEGER NOT NULL DEFAULT 1,
    missed INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS sightings (
    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE, key TEXT NOT NULL, ip TEXT NOT NULL,
    PRIMARY KEY (scan_id, key));
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY, ts REAL NOT NULL, scan_id INTEGER, key TEXT NOT NULL, kind TEXT NOT NULL,
    name TEXT, detail TEXT);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
"""


@dataclass
class KnownDevice:
    key: str
    mac: str | None
    name: str
    type: str
    vendor: str | None
    os: str | None
    last_ip: str
    network: str | None
    first_seen: float
    last_seen: float
    seen_count: int
    missed: int

    @property
    def offline(self) -> bool:
        return self.missed >= 1


@dataclass
class Event:
    ts: float
    kind: str            # new | left | returned | ip_changed
    key: str
    name: str
    detail: str


@dataclass
class Diff:
    scan_id: int = 0
    baseline_networks: list[str] = field(default_factory=list)
    new: list[Device] = field(default_factory=list)
    returned: list[Device] = field(default_factory=list)
    moved: list[tuple[Device, str]] = field(default_factory=list)       # (device, previous ip)
    left: list[KnownDevice] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.new or self.returned or self.moved or self.left)

    def summary_lines(self) -> list[str]:
        out = []
        if self.baseline_networks:
            out.append("first scan of " + ", ".join(self.baseline_networks) + " recorded as the baseline")
        for d in self.new:
            out.append(f"NEW       {d.ip:<15} {d.display_name} ({d.type_label})")
        for d in self.returned:
            out.append(f"RETURNED  {d.ip:<15} {d.display_name} ({d.type_label})")
        for d, old in self.moved:
            out.append(f"MOVED     {d.ip:<15} {d.display_name} (was {old})")
        for k in self.left:
            out.append(f"LEFT      {k.last_ip:<15} {k.name} ({k.type}, not seen for {k.missed} scans)")
        return out


def _network_of(ip: str, networks: list[str]) -> str | None:
    try:
        addr = ipaddress.ip_address(ip)
        return next((n for n in networks if addr in ipaddress.ip_network(n, strict=False)), None)
    except ValueError:
        return None


class History:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else paths.data_dir() / "history.db"
        self._init()

    # ---- plumbing ------------------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        paths.ensure(self.path.parent)
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init(self) -> None:
        try:
            with closing(self._connect()) as c, c:
                c.executescript(_SCHEMA)
        except sqlite3.DatabaseError as e:          # not a database / corrupt: set it aside, start fresh
            bad = self.path.with_suffix(f".bad-{int(time.time())}")
            try:
                self.path.replace(bad)
                log.warning("history database unreadable (%s); moved to %s and starting empty", e, bad)
            except OSError:
                log.warning("history database unreadable (%s)", e)
            with closing(self._connect()) as c, c:
                c.executescript(_SCHEMA)

    @staticmethod
    def _known(r: sqlite3.Row) -> KnownDevice:
        return KnownDevice(r["key"], r["mac"], r["name"] or r["last_ip"], r["type"] or "unknown", r["vendor"],
                           r["os"], r["last_ip"], r["network"], r["first_seen"], r["last_seen"],
                           r["seen_count"], r["missed"])

    # ---- recording -----------------------------------------------------------------------
    def record(self, devices: list[Device], networks: list[str], now: float | None = None) -> Diff:
        """Store one completed scan of `networks` and report what changed since the previous one."""
        now = time.time() if now is None else now
        diff = Diff()
        with closing(self._connect()) as c, c:       # one transaction
            known_nets = {r[0] for r in c.execute("SELECT DISTINCT network FROM scan_networks")}
            baseline = {n for n in networks if n not in known_nets}
            diff.baseline_networks = sorted(baseline)
            diff.scan_id = c.execute("INSERT INTO scans(started, count) VALUES (?, ?)", (now, len(devices))).lastrowid
            c.executemany("INSERT INTO scan_networks(scan_id, network) VALUES (?, ?)",
                          [(diff.scan_id, n) for n in networks])

            seen: set[str] = set()
            for d in devices:
                key = key_for(d)
                seen.add(key)
                net = _network_of(d.ip, networks)
                row = c.execute("SELECT * FROM devices WHERE key = ?", (key,)).fetchone()
                status, previous_ip = "known", None
                if row is None:
                    status = "new" if net not in baseline else "known"
                    c.execute("INSERT INTO devices(key, mac, name, type, vendor, os, last_ip, network, first_seen,"
                              " last_seen) VALUES (?,?,?,?,?,?,?,?,?,?)",
                              (key, d.mac, d.display_name, d.device_type, d.vendor, d.os_label, d.ip, net, now, now))
                    first, count = now, 1
                    if status == "new":
                        diff.new.append(d)
                        self._event(c, now, diff.scan_id, key, "new", d.display_name, d.ip)
                else:
                    first, count = row["first_seen"], row["seen_count"] + 1
                    if row["missed"] >= MISSING_AFTER:
                        status = "returned"
                        diff.returned.append(d)
                        self._event(c, now, diff.scan_id, key, "returned", d.display_name,
                                    f"{d.ip} after {row['missed']} missed scans")
                    if row["last_ip"] != d.ip:
                        previous_ip = row["last_ip"]
                        diff.moved.append((d, previous_ip))
                        self._event(c, now, diff.scan_id, key, "ip_changed", d.display_name,
                                    f"{previous_ip} -> {d.ip}")
                    c.execute("UPDATE devices SET mac=?, name=?, type=?, vendor=?, os=?, last_ip=?, network=?,"
                              " last_seen=?, seen_count=?, missed=0 WHERE key=?",
                              (d.mac, d.display_name, d.device_type, d.vendor, d.os_label, d.ip, net, now,
                               count, key))
                c.execute("INSERT OR IGNORE INTO sightings(scan_id, key, ip) VALUES (?,?,?)",
                          (diff.scan_id, key, d.ip))
                d.history = {"status": status, "first_seen": first, "seen_count": count, "previous_ip": previous_ip}

            # devices on a network we just scanned that didn't answer
            marks = ",".join("?" * len(networks))
            for r in c.execute(f"SELECT * FROM devices WHERE network IN ({marks})", networks).fetchall():
                if r["key"] in seen:
                    continue
                missed = r["missed"] + 1
                c.execute("UPDATE devices SET missed=? WHERE key=?", (missed, r["key"]))
                if missed == MISSING_AFTER:
                    k = self._known(r)
                    k.missed = missed
                    diff.left.append(k)
                    self._event(c, now, diff.scan_id, r["key"], "left", k.name, f"last seen at {k.last_ip}")
            self._prune(c, now)
        return diff

    @staticmethod
    def _event(c, ts, scan_id, key, kind, name, detail) -> None:
        c.execute("INSERT INTO events(ts, scan_id, key, kind, name, detail) VALUES (?,?,?,?,?,?)",
                  (ts, scan_id, key, kind, name, detail))

    @staticmethod
    def _prune(c, now: float) -> None:
        cutoff = now - RETENTION_DAYS * 86400
        c.execute("DELETE FROM scans WHERE started < ?", (cutoff,))          # cascades to sightings/networks
        c.execute("DELETE FROM devices WHERE last_seen < ?", (cutoff,))
        c.execute("DELETE FROM events WHERE ts < ?", (cutoff,))

    # ---- queries -------------------------------------------------------------------------
    def known(self) -> list[KnownDevice]:
        with closing(self._connect()) as c:
            return [self._known(r) for r in c.execute("SELECT * FROM devices ORDER BY last_seen DESC")]

    def offline(self, networks: list[str], present_keys: set[str]) -> list[KnownDevice]:
        """Known devices of these networks that were not in the scan just recorded."""
        marks = ",".join("?" * len(networks))
        with closing(self._connect()) as c:
            rows = c.execute(f"SELECT * FROM devices WHERE network IN ({marks}) AND missed >= 1"
                             " ORDER BY last_seen DESC", networks).fetchall()
        return [self._known(r) for r in rows if r["key"] not in present_keys]

    def events(self, limit: int = 30) -> list[Event]:
        with closing(self._connect()) as c:
            return [Event(r["ts"], r["kind"], r["key"], r["name"] or r["key"], r["detail"] or "")
                    for r in c.execute("SELECT * FROM events ORDER BY ts DESC, id DESC LIMIT ?", (limit,))]

    def scan_count(self) -> int:
        with closing(self._connect()) as c:
            return c.execute("SELECT COUNT(*) FROM scans").fetchone()[0]

    def clear(self) -> None:
        with closing(self._connect()) as c, c:
            for table in ("sightings", "events", "scan_networks", "scans", "devices"):
                c.execute(f"DELETE FROM {table}")
