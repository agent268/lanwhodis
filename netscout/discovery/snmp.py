"""SNMP probe: read sysDescr / sysObjectID / sysName / sysUpTime with the default read community.

Read-only: one GET per device using only the community names we are told to try (default
"public"). SNMP-speaking gear (routers, switches, APs, printers, NAS) describes itself precisely.
The sysObjectID's enterprise number names the vendor (see pen.py); sysDescr feeds the Recog
snmp.sys_description fingerprints.
"""
from __future__ import annotations

import random
import socket
from concurrent.futures import ThreadPoolExecutor

from .. import pen
from ..model import Device, ServiceRecord
from . import ber
from .base import ScanContext

OID_SYSDESCR = "1.3.6.1.2.1.1.1.0"
OID_SYSOBJECTID = "1.3.6.1.2.1.1.2.0"
OID_SYSUPTIME = "1.3.6.1.2.1.1.3.0"
OID_SYSNAME = "1.3.6.1.2.1.1.5.0"
OIDS = (OID_SYSDESCR, OID_SYSOBJECTID, OID_SYSUPTIME, OID_SYSNAME)


def build_get(version: int, community: str, request_id: int, oids: tuple[str, ...] = OIDS) -> bytes:
    """SNMP GetRequest. version: 0 = v1, 1 = v2c."""
    varbinds = b"".join(ber.tlv(0x30, ber.oid(o) + ber.NULL) for o in oids)
    pdu = ber.tlv(0xA0, ber.integer(request_id) + ber.integer(0) + ber.integer(0) + ber.tlv(0x30, varbinds))
    return ber.tlv(0x30, ber.integer(version) + ber.octets(community.encode()) + pdu)


def parse_response(data: bytes, request_id: int | None = None) -> dict[str, object]:
    """GetResponse -> {oid: value}. Empty dict for errors, mismatched ids or garbage."""
    try:
        tag, msg, _ = ber.read(data)
        if tag != 0x30:
            return {}
        parts = ber.children(msg)
        if len(parts) < 3 or parts[2][0] != 0xA2:         # GetResponse-PDU
            return {}
        pdu = ber.children(parts[2][1])
        if len(pdu) < 4:
            return {}
        if request_id is not None and int.from_bytes(pdu[0][1], "big", signed=True) != request_id:
            return {}
        if int.from_bytes(pdu[1][1], "big", signed=True) != 0:        # error-status
            return {}
        out: dict[str, object] = {}
        for _, vb in ber.children(pdu[3][1]):
            name, value = ber.children(vb)[:2]
            oid = ber.decode_oid(name[1])
            vtag, vval = value
            if vtag == 0x04:
                out[oid] = vval.decode("utf-8", "replace").replace("\x00", "").strip()
            elif vtag == 0x06:
                out[oid] = ber.decode_oid(vval)
            elif vtag in (0x02, 0x41, 0x42, 0x43, 0x46):
                out[oid] = int.from_bytes(vval, "big", signed=(vtag == 0x02))
            # NULL / noSuchObject / noSuchInstance / endOfMibView carry nothing
        return out
    except (ValueError, IndexError):
        return {}


def query(ip: str, community: str, version: int, timeout: float = 1.0, port: int = 161) -> dict[str, object]:
    request_id = random.getrandbits(30)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(build_get(version, community, request_id), (ip, port))
        while True:
            try:
                data, (src, _) = sock.recvfrom(4096)
            except OSError:
                return {}
            if src == ip:
                return parse_response(data, request_id)
    finally:
        sock.close()


def apply(d: Device, vals: dict[str, object], community: str, version: str) -> None:
    descr = str(vals.get(OID_SYSDESCR) or "")[:300]
    objid = str(vals.get(OID_SYSOBJECTID) or "")
    name = str(vals.get(OID_SYSNAME) or "")[:80]
    uptime = vals.get(OID_SYSUPTIME)
    vendor = pen.vendor_for_oid(objid) if objid else None
    if descr:
        d.facts["snmp_sysdescr"] = descr
        d.text.append(descr)
    if objid:
        d.facts["snmp_sysobjid"] = objid
    if name:
        d.facts["snmp_sysname"] = name
        d.names.setdefault("snmp", name)
    if isinstance(uptime, int):
        d.facts["snmp_uptime_days"] = f"{uptime / 100 / 86400:.1f}"
    if vendor:
        d.facts["snmp_vendor"] = vendor
    d.services.add("snmp:agent")
    details = {"version": version, "community": community}
    if vendor:
        details["enterprise"] = vendor
    d.add_service(ServiceRecord("snmp", "agent", name=name, port=161, details=details))


def probe(ip: str, communities: tuple[str, ...], port: int = 161) -> tuple[dict[str, object], str, str] | None:
    for community in communities:
        for version, label in ((1, "v2c"), (0, "v1")):
            vals = query(ip, community, version, port=port)
            if vals:
                return vals, community, label
    return None


def run(ctx: ScanContext, devices: list[Device], communities: tuple[str, ...] = ("public",)) -> None:
    def work(d: Device) -> None:
        if ctx.stop.is_set():
            return
        found = probe(d.ip, communities)
        if found:
            apply(d, *found)
            ctx.table.touch(d)

    ctx.log(f"snmp: read-only GET, communities {list(communities)}")
    with ThreadPoolExecutor(max_workers=32) as pool:
        list(pool.map(work, devices))
