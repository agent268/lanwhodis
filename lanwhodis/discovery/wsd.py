"""WS-Discovery (UDP 3702): finds ONVIF cameras, WSD printers, Windows machines."""
from __future__ import annotations

import re
import socket
import time
import uuid

from urllib.parse import unquote

from ..model import Device, ServiceRecord
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


_SCOPES = re.compile(r"<(?:\w+:)?Scopes[^>]*>([^<]*)</(?:\w+:)?Scopes>")
_EPR = re.compile(r"<(?:\w+:)?EndpointReference[^>]*>\s*<(?:\w+:)?Address[^>]*>([^<]*)<")


def parse_probe_match(d: Device, text: str) -> None:
    """Record what a WS-Discovery ProbeMatch says about a device (types, XAddrs, ONVIF scopes).
    XAddrs are SOAP service endpoints: we list them, we never call them."""
    types = [t.split(":")[-1].lower() for m in _TYPES.finditer(text) for t in m.group(1).split()]
    own = [u for u in (d.own_url(x) for m in _XADDR.finditer(text) for x in m.group(1).split()) if u]
    scopes = [s for m in _SCOPES.finditer(text) for s in m.group(1).split()]
    epr = _EPR.search(text)
    details: dict[str, str] = {}
    if own:
        details["xaddrs"] = " ".join(own)
        d.facts.setdefault("wsd_xaddrs", details["xaddrs"][:200])
    if scopes:
        details["scopes"] = " ".join(scopes)[:500]
    if epr:
        details["address"] = epr.group(1).strip()[:100]
    d.services.add("wsd:device")
    for short in dict.fromkeys(types or ["device"]):
        d.services.add(f"wsd:{short}")
        if short not in d.facts.get("wsd_types", ""):
            d.facts["wsd_types"] = (d.facts.get("wsd_types", "") + " " + short).strip()
        d.add_service(ServiceRecord("wsd", short, url=own[0] if own else None, soap=bool(own),
                                    details=dict(details)))
    for s in scopes:      # ONVIF cameras put their name and hardware model in the scopes
        for part, attr in (("/name/", "name"), ("/hardware/", "hardware")):
            if part in s:
                val = unquote(s.split(part, 1)[1]).strip()
                if val and attr == "name":
                    d.names.setdefault("onvif", val)
                elif val:
                    d.model = d.model or val
                    d.text.append(val)


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
                d = ctx.table.get(ip)
                parse_probe_match(d, data.decode("utf-8", "replace"))
                ctx.table.touch(d)
        finally:
            sock.close()
