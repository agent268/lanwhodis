"""WS-Discovery (UDP 3702): finds ONVIF cameras, WSD printers, Windows machines."""
from __future__ import annotations

import re
import socket
import time
import uuid

from .base import ScanContext

_PROBE = """<?xml version="1.0" encoding="utf-8"?>
<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"
 xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"
 xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery">
<e:Header><w:MessageID>uuid:{mid}</w:MessageID>
<w:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>
<w:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action></e:Header>
<e:Body><d:Probe/></e:Body></e:Envelope>"""

_TYPES = re.compile(r"<(?:\w+:)?Types[^>]*>([^<]*)</(?:\w+:)?Types>")
_XADDR = re.compile(r"<(?:\w+:)?XAddrs[^>]*>([^<]*)</(?:\w+:)?XAddrs>")


def run(ctx: ScanContext) -> None:
    ctx.log("wsd: probe")
    for iface in ctx.ifaces:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            sock.bind((iface.ip, 0))
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(iface.ip))
            sock.settimeout(0.3)
            msg = _PROBE.format(mid=uuid.uuid4()).encode()
            for _ in range(2):
                sock.sendto(msg, ("239.255.255.250", 3702))
            end = time.time() + min(ctx.timeout, 3.0)
            while time.time() < end and not ctx.stop.is_set():
                try:
                    data, (ip, _) = sock.recvfrom(65535)
                except (socket.timeout, OSError):
                    continue
                if not ctx.in_scope(ip):
                    continue
                text = data.decode("utf-8", "replace")
                d = ctx.table.get(ip)
                d.services.add("wsd:device")
                for m in _TYPES.finditer(text):
                    for t in m.group(1).split():
                        short = t.split(":")[-1].lower()
                        d.services.add(f"wsd:{short}")
                        d.facts.setdefault("wsd_types", "")
                        if short not in d.facts["wsd_types"]:
                            d.facts["wsd_types"] += (" " if d.facts["wsd_types"] else "") + short
                for m in _XADDR.finditer(text):
                    d.facts.setdefault("wsd_xaddrs", m.group(1).strip()[:200])
                ctx.table.touch(d)
        finally:
            sock.close()
