"""Banner fingerprinting with Rapid7 Recog databases (BSD-2-Clause; see data/recog/LICENSE.txt).

Recog databases are XML lists of ``<fingerprint pattern=...>`` entries. A banner is matched against a
database's patterns in file order and the first match wins; its ``<param>`` elements describe the
product (``pos="0"`` is a literal ``value``, ``pos="N"`` is regex capture group N). We bundle the
databases for banners lanwhodis already collects (SSH, HTTP Server/<title>/WWW-Authenticate, RTSP,
SNMP, mDNS _device-info) and map the results onto device types / OS families via
data/rules/recog.toml. Refresh the data with tools/update_recog.py.
"""
from __future__ import annotations

import gzip
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources

from .model import Device, RecogMatch

# Recog database key (the XML root's `matches` attribute) -> file in data/recog
_FILES = {
    "ssh.banner": "ssh_banners", "http_header.server": "http_servers", "html_title": "html_title",
    "http_header.wwwauth": "http_wwwauth", "rtsp_header.server": "rtsp_servers",
    "snmp.sys_description": "snmp_sysdescr", "snmp.sys_object_id": "snmp_sysobjid",
    "mdns.device-info.txt": "mdns_device-info_txt",
}
_REF = re.compile(r"\{([\w.]+)\}")
_SSH_PREFIX = re.compile(r"^SSH-\d+\.\d+-")


@dataclass
class _Fingerprint:
    rx: "re.Pattern[str]"
    description: str
    params: list[tuple[int, str, str | None]]     # (pos, name, literal value)


@dataclass
class Database:
    key: str
    prints: list[_Fingerprint] = field(default_factory=list)
    skipped: int = 0                              # patterns Python's re could not compile


@lru_cache(maxsize=None)
def database(key: str) -> Database:
    db = Database(key)
    raw = (resources.files("lanwhodis") / "data" / "recog" / f"{_FILES[key]}.xml.gz").read_bytes()
    for fp in ET.fromstring(gzip.decompress(raw)).findall("fingerprint"):
        try:
            rx = re.compile(fp.get("pattern", ""))
        except re.error:
            db.skipped += 1
            continue
        params = [(int(p.get("pos", "0")), p.get("name", ""), p.get("value"))
                  for p in fp.findall("param") if p.get("name")]
        db.prints.append(_Fingerprint(rx, (fp.findtext("description") or "").strip(), params))
    return db


def match(key: str, text: str) -> RecogMatch | None:
    """First fingerprint in database `key` matching `text`, with params resolved."""
    if not text or key not in _FILES:
        return None
    for fp in database(key).prints:
        m = fp.rx.search(text)
        if not m:
            continue
        params: dict[str, str] = {}
        for pos, name, value in fp.params:
            if pos == 0:
                if value is not None:
                    params[name] = value
            elif pos <= (m.re.groups or 0) and m.group(pos) is not None:
                params[name] = m.group(pos)
        for name, value in list(params.items()):       # {service.version} style references
            params[name] = _REF.sub(lambda r: params.get(r.group(1), r.group(0)), value)
        return RecogMatch(key, text[:200], fp.description, params)
    return None


def _inputs(d: Device) -> list[tuple[str, str]]:
    """(database key, banner text) pairs gathered from what the probes recorded."""
    out: list[tuple[str, str]] = []
    f = d.facts
    if f.get("ssh_banner"):      # Recog's ssh patterns start after the "SSH-2.0-" protocol prefix
        out.append(("ssh.banner", _SSH_PREFIX.sub("", f["ssh_banner"])))
    for k, v in f.items():
        if k.startswith("http") and k.endswith("_server"):
            out.append(("http_header.server", v))
        elif k.startswith("http") and k.endswith("_title"):
            out.append(("html_title", v))
        elif k.startswith("http") and k.endswith("_wwwauth"):
            out.append(("http_header.wwwauth", v))
    if f.get("rtsp_server"):
        out.append(("rtsp_header.server", f["rtsp_server"]))
    if f.get("snmp_sysdescr"):
        out.append(("snmp.sys_description", f["snmp_sysdescr"]))
    if f.get("snmp_sysobjid"):
        out.append(("snmp.sys_object_id", f["snmp_sysobjid"]))
    for s in filter(None, (f.get("device_info_txt") or "").split("|")):
        out.append(("mdns.device-info.txt", s))
    return out


def annotate(d: Device) -> None:
    """Fingerprint every banner collected for `d`; results land in d.recog (idempotent)."""
    d.recog = []
    seen = set()
    for key, text in _inputs(d):
        if (key, text) in seen:
            continue
        seen.add((key, text))
        m = match(key, text)
        if m:
            d.recog.append(m)
            hw = m.params.get("hw.product") or m.params.get("hw.model")
            if hw and not d.model:
                d.model = hw


def certainty(m: RecogMatch, which: str) -> float:
    try:
        return max(0.0, min(1.0, float(m.params.get(f"{which}.certainty", 1))))
    except ValueError:
        return 1.0


def os_family_and_detail(m: RecogMatch, family_map: dict[str, str]) -> tuple[str, str | None] | None:
    """(our OS family, detail) from a match's os.* params, or None when it says nothing about the OS."""
    fam = m.params.get("os.family") or m.params.get("os.product")
    if not fam:
        return None
    family = family_map.get(fam, fam)
    vendor, product, version = m.params.get("os.vendor"), m.params.get("os.product"), m.params.get("os.version")
    name = None
    if product and product.lower() not in (fam.lower(), family.lower()):
        name = product
    elif vendor and vendor.lower() not in (fam.lower(), family.lower(), "microsoft", "apple"):
        name = vendor
    if version and name and version in name:
        version = None
    return family, " ".join(x for x in (name, version) if x) or None
