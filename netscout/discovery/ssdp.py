"""SSDP / UPnP: M-SEARCH on every interface, then read each device description XML."""
from __future__ import annotations

import re
import socket
import time
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

from .base import ScanContext

_MSEARCH = ("M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\n"
            'MAN: "ssdp:discover"\r\nMX: 2\r\nST: ssdp:all\r\n\r\n').encode()
_NS = re.compile(r"^\{.*?\}")


def _search(ctx: ScanContext) -> dict[str, dict[str, str]]:
    """ip -> merged SSDP headers (LOCATION, SERVER, plus a set of ST/NT values in 'st')."""
    results: dict[str, dict[str, str]] = {}
    for iface in ctx.ifaces:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            sock.bind((iface.ip, 0))
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(iface.ip))
            sock.settimeout(0.3)
            for _ in range(2):
                sock.sendto(_MSEARCH, ("239.255.255.250", 1900))
            end = time.time() + ctx.timeout
            while time.time() < end and not ctx.stop.is_set():
                try:
                    data, (ip, _) = sock.recvfrom(4096)
                except (socket.timeout, OSError):
                    continue
                hdrs: dict[str, str] = {}
                for line in data.decode("utf-8", "replace").split("\r\n")[1:]:
                    k, _, v = line.partition(":")
                    if v:
                        hdrs[k.strip().lower()] = v.strip()
                r = results.setdefault(ip, {})
                for k in ("location", "server"):
                    if k in hdrs:
                        r.setdefault(k, hdrs[k])
                st = hdrs.get("st") or hdrs.get("nt")
                if st:
                    r["st"] = r.get("st", "") + "|" + st
        finally:
            sock.close()
    return results


def _text(el: ET.Element | None) -> str | None:
    return el.text.strip() if el is not None and el.text and el.text.strip() else None


def _describe(url: str, expect_ip: str) -> dict | None:
    # only follow descriptions hosted by the responder itself (no redirects to other hosts)
    if urlparse(url).hostname != expect_ip:
        return None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "netscout"}),
                                    timeout=2.5) as r:
            root = ET.fromstring(r.read(262144))
    except Exception:
        return None
    out: dict = {"types": []}
    for el in root.iter():
        tag = _NS.sub("", el.tag)
        if tag == "deviceType" and el.text:
            out["types"].append(el.text.strip())
        elif tag in ("friendlyName", "manufacturer", "modelName", "modelDescription", "modelNumber",
                     "presentationURL", "URLBase") and tag not in out:
            v = _text(el)
            if v:
                out[tag] = v
    return out


def _short_type(urn: str) -> str:
    # urn:schemas-upnp-org:device:MediaRenderer:1 -> mediarenderer
    parts = urn.split(":")
    return (parts[-2] if len(parts) >= 2 and parts[-1].isdigit() else parts[-1]).lower()


def run(ctx: ScanContext) -> None:
    ctx.log("ssdp: M-SEARCH")
    found = _search(ctx)
    ctx.log(f"ssdp: {len(found)} responders")
    for ip, h in found.items():
        if not ctx.in_scope(ip):
            continue
        d = ctx.table.get(ip)
        d.services.add("ssdp:responder")
        if h.get("server"):
            d.facts["ssdp_server"] = h["server"]
            d.text.append(h["server"])
        for st in filter(None, h.get("st", "").split("|")):
            if "device:" in st:
                d.services.add(f"upnp:{_short_type(st)}")
            elif "service:" in st:
                d.services.add(f"upnp:{_short_type(st)}")
        ctx.table.touch(d)

    def describe(item: tuple[str, dict[str, str]]) -> None:
        ip, h = item
        loc = h.get("location")
        if not loc or not ctx.in_scope(ip):
            return
        info = _describe(loc, ip)
        if not info:
            return
        d = ctx.table.get(ip)
        for t in info["types"]:
            d.services.add(f"upnp:{_short_type(t)}")
        if info.get("presentationURL"):   # often relative: resolve against URLBase, else the description URL
            d.add_web_url(urljoin(info.get("URLBase") or loc, info["presentationURL"]), "upnp", 0)
        if info.get("friendlyName"):
            d.names.setdefault("upnp", info["friendlyName"])
            d.text.append(info["friendlyName"])
        if info.get("modelName"):
            d.model = d.model or info["modelName"]
            d.text.append(info["modelName"])
        if info.get("modelDescription"):
            d.text.append(info["modelDescription"])
        if info.get("manufacturer"):
            d.facts["manufacturer"] = info["manufacturer"]
            d.text.append(info["manufacturer"])
            d.vendor = d.vendor or info["manufacturer"]
        ctx.table.touch(d)

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(describe, found.items()))
