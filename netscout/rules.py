"""Declarative classification rules, loaded from TOML.

Packaged rules live in ``netscout/data/rules/*.toml`` and are validated strictly (a bad packaged
rule is a bug). Users can add or override rules with files of the same names in
``<data dir>/rules`` (see ``paths.rules_dir``); those are validated leniently - a bad user rule is
reported and skipped so it can never break a scan.

File kinds (one file per kind, same format for packaged and user files):

* ``vendor.toml`` / ``names.toml`` / ``text.toml``: ``[[rule]]`` with ``match`` (regex, case
  insensitive) and ``votes`` (device type -> weight 0..1).
* ``services.toml``: ``[services]`` table, ``"proto:service" = { type = weight }``. A user entry
  replaces the packaged entry with the same key.
* ``ports.toml``: ``[ports]`` table, ``"445" = { type = weight }``.
* ``os.toml``: ``[[text]]``, ``[[port]]``, ``[[vendor]]``, ``[ttl."64"]`` and ``[[type_votes]]``
  (see the packaged file for fields).
"""
from __future__ import annotations

import logging
import re
import tomllib
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Callable

from . import devtypes, paths

log = logging.getLogger("netscout.rules")

Votes = dict[str, float]
RegexRules = list[tuple["re.Pattern[str]", Votes]]
FILES = ("vendor.toml", "names.toml", "text.toml", "services.toml", "ports.toml", "os.toml", "recog.toml")


class RuleError(ValueError):
    """A rule failed validation."""


@dataclass
class OsRule:
    rx: "re.Pattern[str] | None"
    family: str
    detail: str | None
    weight: float


@dataclass
class RuleSet:
    vendor: RegexRules = field(default_factory=list)
    names: RegexRules = field(default_factory=list)
    text: RegexRules = field(default_factory=list)
    services: dict[str, Votes] = field(default_factory=dict)
    ports: dict[int, Votes] = field(default_factory=dict)
    os_text: list[OsRule] = field(default_factory=list)
    os_ports: dict[int, OsRule] = field(default_factory=dict)
    os_vendor: list[OsRule] = field(default_factory=list)
    os_ttl: dict[int, dict[str, float]] = field(default_factory=dict)
    os_type_votes: dict[tuple[str, str | None], Votes] = field(default_factory=dict)
    recog_devices: dict[str, Votes] = field(default_factory=dict)     # Recog hw/os.device -> type votes
    recog_os: dict[str, str] = field(default_factory=dict)            # Recog os.family -> our OS family
    recog_os_ignore: set[str] = field(default_factory=set)            # os.device values whose "OS" is firmware
    errors: list[str] = field(default_factory=list)      # user-rule problems (lenient mode)


# ---- validation helpers ------------------------------------------------------------------

def _weight(v, where: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1:
        raise RuleError(f"{where}: weight must be a number between 0 and 1, got {v!r}")
    return float(v)


def _votes(raw, where: str) -> Votes:
    if not isinstance(raw, dict):
        raise RuleError(f"{where}: votes must be a table like {{ camera = 0.8 }}")
    out = {}
    for t, w in raw.items():
        if t not in devtypes.TYPES:
            raise RuleError(f"{where}: unknown device type {t!r}")
        out[t] = _weight(w, where)
    return out


def _regex(raw, where: str) -> "re.Pattern[str]":
    if not isinstance(raw, str) or not raw:
        raise RuleError(f"{where}: match must be a non-empty regex string")
    try:
        return re.compile(raw, re.I)
    except re.error as e:
        raise RuleError(f"{where}: bad regex {raw!r}: {e}") from None


def _os_rule(raw: dict, where: str, needs_regex: bool) -> OsRule:
    if not isinstance(raw.get("family"), str):
        raise RuleError(f"{where}: family is required")
    return OsRule(_regex(raw.get("match"), where) if needs_regex else None, raw["family"],
                  raw.get("detail"), _weight(raw.get("weight"), where))


# ---- loading -----------------------------------------------------------------------------

def _each(items, label: str, fn: Callable, strict: bool, rs: RuleSet, src: str) -> list:
    out = []
    for i, raw in enumerate(items, 1):
        try:
            out.append(fn(raw, f"{src} {label} #{i}"))
        except RuleError as e:
            if strict:
                raise
            rs.errors.append(str(e))
    return out


def _apply(rs: RuleSet, name: str, doc: dict, strict: bool, src: str) -> None:
    def rx_rule(raw, where):
        return _regex(raw.get("match"), where), _votes(raw.get("votes"), where)

    if name in ("vendor.toml", "names.toml", "text.toml"):
        target = getattr(rs, name.split(".")[0])
        target += _each(doc.get("rule", []), "rule", rx_rule, strict, rs, src)
    elif name == "services.toml":
        for key, raw in doc.get("services", {}).items():
            try:
                rs.services[key.lower()] = _votes(raw, f"{src} service {key!r}")
            except RuleError as e:
                if strict:
                    raise
                rs.errors.append(str(e))
    elif name == "ports.toml":
        for key, raw in doc.get("ports", {}).items():
            try:
                if not key.isdigit() or not 0 < int(key) < 65536:
                    raise RuleError(f"{src} port {key!r}: not a valid TCP port")
                rs.ports[int(key)] = _votes(raw, f"{src} port {key}")
            except RuleError as e:
                if strict:
                    raise
                rs.errors.append(str(e))
    elif name == "recog.toml":
        for key, raw in doc.get("hw_device", {}).items():
            try:
                rs.recog_devices[key] = _votes(raw, f"{src} hw_device {key!r}")
            except RuleError as e:
                if strict:
                    raise
                rs.errors.append(str(e))
        rs.recog_os_ignore |= {str(x) for x in doc.get("os_ignore", {}).get("devices", [])}
        for key, fam in doc.get("os_family", {}).items():
            if isinstance(fam, str) and fam:
                rs.recog_os[key] = fam
            elif strict:
                raise RuleError(f"{src} os_family {key!r}: must map to a non-empty string")
            else:
                rs.errors.append(f"{src} os_family {key!r}: must map to a non-empty string")
    elif name == "os.toml":
        rs.os_text += _each(doc.get("text", []), "text", lambda r, w: _os_rule(r, w, True), strict, rs, src)
        rs.os_vendor += _each(doc.get("vendor", []), "vendor", lambda r, w: _os_rule(r, w, True), strict, rs, src)
        for rule in _each(doc.get("port", []), "port", lambda r, w: (r.get("port"), _os_rule(r, w, False)),
                          strict, rs, src):
            if isinstance(rule[0], int):
                rs.os_ports[rule[0]] = rule[1]
        for ttl, votes in doc.get("ttl", {}).items():
            try:
                rs.os_ttl[int(ttl)] = {fam: _weight(w, f"{src} ttl {ttl}") for fam, w in votes.items()}
            except (RuleError, ValueError) as e:
                if strict:
                    raise
                rs.errors.append(str(e))

        def tv(raw, where):
            return (raw.get("family"), raw.get("detail")), _votes(raw.get("votes"), where)

        for key, votes in _each(doc.get("type_votes", []), "type_votes", tv, strict, rs, src):
            rs.os_type_votes[key] = votes


def _read_toml(path: Path | None, text: str | None = None) -> dict:
    try:
        return tomllib.loads(text if text is not None else path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise RuleError(f"{path}: {e}") from None


def load(user_dir: Path | None = None, use_user: bool = True) -> RuleSet:
    rs = RuleSet()
    pkg = resources.files("netscout") / "data" / "rules"
    for name in FILES:
        _apply(rs, name, _read_toml(Path(name), (pkg / name).read_text(encoding="utf-8")), True, f"[{name}]")
    if use_user:
        d = user_dir if user_dir is not None else paths.rules_dir()
        for name in FILES:
            f = d / name
            if not f.is_file():
                continue
            try:
                _apply(rs, name, _read_toml(f), False, f"[user {name}]")
            except RuleError as e:
                rs.errors.append(str(e))
    for e in rs.errors:
        log.warning("ignoring user rule: %s", e)
    return rs


_cache: RuleSet | None = None


def get() -> RuleSet:
    global _cache
    if _cache is None:
        _cache = load()
    return _cache


def reload(user_dir: Path | None = None) -> RuleSet:
    """Drop the cache (tests, or after the user edits rules); optionally point at another user dir."""
    global _cache
    _cache = load(user_dir)
    return _cache
