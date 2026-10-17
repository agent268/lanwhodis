"""SMB probe: identify a host's real OS version and name without credentials.

Sends an SMB2 NEGOTIATE, then a SESSION_SETUP carrying only an NTLMSSP NEGOTIATE message, and reads
the server's NTLMSSP CHALLENGE: it reports the Windows version (major.minor.build), the computer /
domain names, and the negotiate response adds the SMB dialect, signing policy and boot time. We then
close the connection - no authentication is attempted (the same technique as nmap's
smb-os-discovery). Samba and most NAS firmwares answer without a version, which itself is a hint.
"""
from __future__ import annotations

import datetime as dt
import os
import socket
import struct
from concurrent.futures import ThreadPoolExecutor

from ..model import Device, ServiceRecord
from . import ber
from .base import ScanContext

_SIG = b"NTLMSSP\x00"
_FILETIME_EPOCH = 116444736000000000
_DIALECTS = {0x0202: "2.0.2", 0x0210: "2.1", 0x0300: "3.0", 0x0302: "3.0.2", 0x0311: "3.1.1"}
_SPNEGO_OID = ber.oid("1.3.6.1.5.5.2")
_NTLM_OID = ber.oid("1.3.6.1.4.1.311.2.2.10")
_AV_NAMES = {1: "computer", 2: "domain", 3: "dns_name", 4: "dns_domain", 5: "dns_tree"}


# ---- message builders --------------------------------------------------------------------

def _frame(payload: bytes) -> bytes:
    return b"\x00" + len(payload).to_bytes(3, "big") + payload      # NetBIOS session service header


def _header(command: int, message_id: int) -> bytes:
    return struct.pack("<4sHHIHHIIQIIQ16s", b"\xfeSMB", 64, 0, 0, command, 1, 0, 0, message_id, 0, 0, 0,
                       b"\x00" * 16)


def negotiate_request() -> bytes:
    # We stop at 3.0.2: SMB 3.1.1 requires negotiate contexts, which a bare probe doesn't need.
    dialects = (0x0202, 0x0210, 0x0300, 0x0302)
    body = struct.pack("<HHHHI16sQ", 36, len(dialects), 1, 0, 0, os.urandom(16), 0)
    return _frame(_header(0, 0) + body + b"".join(struct.pack("<H", x) for x in dialects))


def ntlm_negotiate() -> bytes:
    flags = (0x00000001 | 0x00000004 | 0x00000200 | 0x00008000 | 0x00080000 | 0x00800000
             | 0x02000000 | 0x20000000 | 0x80000000)   # unicode, target, NTLM, sign, ESS, target info, version, 128, 56
    version = struct.pack("<BBH", 10, 0, 19041) + b"\x00\x00\x00" + bytes([15])
    return (_SIG + struct.pack("<II", 1, flags) + struct.pack("<HHI", 0, 0, 40)
            + struct.pack("<HHI", 0, 0, 40) + version)


def spnego_init(ntlm: bytes) -> bytes:
    """Wrap an NTLMSSP token in the SPNEGO NegTokenInit that SMB servers expect."""
    mech_types = ber.tlv(0xA0, ber.tlv(0x30, _NTLM_OID))
    mech_token = ber.tlv(0xA2, ber.octets(ntlm))
    neg_init = ber.tlv(0xA0, ber.tlv(0x30, mech_types + mech_token))
    return ber.tlv(0x60, _SPNEGO_OID + neg_init)


def session_setup_request(blob: bytes) -> bytes:
    body = struct.pack("<HBBIIHHQ", 25, 0, 1, 0, 0, 64 + 24, len(blob), 0) + blob
    return _frame(_header(1, 1) + body)


# ---- response parsers --------------------------------------------------------------------

def _filetime(ft: int) -> dt.datetime | None:
    if ft <= 0:
        return None
    try:
        return dt.datetime.fromtimestamp((ft - _FILETIME_EPOCH) / 1e7, dt.timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def parse_negotiate(resp: bytes) -> dict | None:
    if len(resp) < 64 + 56 or resp[:4] != b"\xfeSMB" or struct.unpack_from("<I", resp, 8)[0] != 0:
        return None
    _, secmode, dialect, _, guid, _, _, _, _, systime, starttime = struct.unpack_from("<HHHH16sIIIIQQ", resp, 64)
    return {"dialect": _DIALECTS.get(dialect, f"0x{dialect:04x}"),
            "signing": "required" if secmode & 0x2 else "enabled" if secmode & 0x1 else "off",
            "server_guid": guid.hex(), "system_time": _filetime(systime), "boot_time": _filetime(starttime)}


def parse_challenge(resp: bytes) -> dict | None:
    """Find the NTLMSSP CHALLENGE (type 2) anywhere in a session-setup response and decode it."""
    i = resp.find(_SIG + b"\x02\x00\x00\x00")
    if i < 0 or i + 56 > len(resp):
        return None
    flags = struct.unpack_from("<I", resp, i + 20)[0]
    ti_len, _, ti_off = struct.unpack_from("<HHI", resp, i + 40)
    out: dict = {"ntlm_version": None}
    if flags & 0x02000000:
        major, minor, build = struct.unpack_from("<BBH", resp, i + 48)
        if major or minor or build:                       # Samba/NAS leave the version zeroed
            out["ntlm_version"] = (major, minor, build)
    pos, end = i + ti_off, min(i + ti_off + ti_len, len(resp))
    while pos + 4 <= end:                                  # AV pairs: id, length, UTF-16LE value
        av, n = struct.unpack_from("<HH", resp, pos)
        pos += 4
        if av == 0:
            break
        value = resp[pos:pos + n]
        pos += n
        if av in _AV_NAMES:
            out[_AV_NAMES[av]] = value.decode("utf-16-le", "replace")
        elif av == 7 and len(value) == 8:
            out["timestamp"] = _filetime(struct.unpack("<Q", value)[0])
    return out


def windows_name(major: int, minor: int, build: int) -> str:
    """Marketing name for an NTLMSSP version. Windows 11 and Server share some build numbers."""
    if (major, minor) == (10, 0):
        if build == 20348:
            name = "Windows Server 2022"
        elif build == 17763:
            name = "Windows 10 1809 / Server 2019"
        elif build == 14393:
            name = "Windows 10 1607 / Server 2016"
        elif build >= 26100:
            name = "Windows 11 / Server 2025"
        elif build >= 22000:
            name = "Windows 11"
        else:
            name = "Windows 10"
    else:
        name = {(6, 3): "Windows 8.1 / Server 2012 R2", (6, 2): "Windows 8 / Server 2012",
                (6, 1): "Windows 7 / Server 2008 R2", (6, 0): "Windows Vista / Server 2008",
                (5, 2): "Windows XP x64 / Server 2003", (5, 1): "Windows XP"}.get((major, minor),
                                                                                   f"Windows NT {major}.{minor}")
    return f"{name} (build {build})"


# ---- network ----------------------------------------------------------------------------

def _recv_frame(sock: socket.socket) -> bytes:
    head = b""
    while len(head) < 4:
        chunk = sock.recv(4 - len(head))
        if not chunk:
            raise ConnectionError("closed")
        head += chunk
    n = int.from_bytes(head[1:], "big")
    if n > 1 << 20:
        raise ValueError("oversized SMB frame")
    body = b""
    while len(body) < n:
        chunk = sock.recv(n - len(body))
        if not chunk:
            raise ConnectionError("closed")
        body += chunk
    return body


def probe(ip: str, timeout: float = 2.5, port: int = 445) -> dict | None:
    try:
        with socket.create_connection((ip, port), timeout=timeout) as s:
            s.settimeout(timeout)
            s.sendall(negotiate_request())
            info = parse_negotiate(_recv_frame(s))
            if not info:
                return None
            s.sendall(session_setup_request(spnego_init(ntlm_negotiate())))
            info.update(parse_challenge(_recv_frame(s)) or {})
            return info
    except (OSError, ValueError, struct.error):
        return None


def apply(d: Device, info: dict) -> None:
    d.facts["smb_dialect"] = f"{info['dialect']} (highest offered: 3.0.2)"
    d.facts["smb_signing"] = info["signing"]
    if info.get("boot_time"):
        d.facts["boot_time"] = info["boot_time"].strftime("%Y-%m-%d %H:%M UTC")
        if info.get("system_time"):
            d.facts["smb_uptime_days"] = f"{(info['system_time'] - info['boot_time']).total_seconds() / 86400:.1f}"
    ver = info.get("ntlm_version")
    if ver:
        os_name = windows_name(*ver)
        d.facts["smb_os"] = os_name
        d.text.append(f"smb-ntlm: {os_name}")
    else:
        d.text.append("smb-server: samba-or-embedded (no NTLM version)")
    if info.get("computer"):
        d.names.setdefault("smb", info["computer"])
    for key in ("domain", "dns_name"):
        if info.get(key):
            d.facts[f"smb_{key}"] = info[key]
    d.services.add("smb:server")
    details = {"dialect": info["dialect"], "signing": info["signing"]}
    if ver:
        details["os"] = d.facts["smb_os"]
    if info.get("domain"):
        details["domain"] = info["domain"]
    d.add_service(ServiceRecord("smb", "ntlm", name=info.get("computer", ""), port=445, details=details))


def run(ctx: ScanContext, devices: list[Device]) -> None:
    targets = [d for d in devices if 445 in d.open_ports]
    ctx.log(f"smb: NTLM challenge probe on {len(targets)} hosts (no authentication)")

    def work(d: Device) -> None:
        if ctx.stop.is_set():
            return
        info = probe(d.ip)
        if info:
            apply(d, info)
            ctx.table.touch(d)

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(work, targets))
