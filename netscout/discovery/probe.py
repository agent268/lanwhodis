"""Unicast probing of hosts already found: TCP ports, reverse DNS, HTTP/SSH/RTSP banners."""
from __future__ import annotations

import json
import re
import socket
import ssl
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

from ..classify import _PORT
from ..model import Device
import sys

from .base import ScanContext, run_cmd

PROBE_PORTS = sorted(set(_PORT) | {80, 443, 8080, 8443})
HTTP_PORTS = (80, 8080, 443, 8443, 5000, 8000)
_TITLE = re.compile(r"<title[^>]*>\s*([^<]{1,100}?)\s*</title>", re.I)
_UNVERIFIED = ssl.create_default_context()
_UNVERIFIED.check_hostname = False
_UNVERIFIED.verify_mode = ssl.CERT_NONE


def _open(ip: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def scan_ports(ctx: ScanContext, devices: list[Device], timeout: float = 0.7) -> None:
    jobs = [(d, p) for d in devices for p in PROBE_PORTS]
    done = 0

    def work(job: tuple[Device, int]) -> None:
        nonlocal done
        d, p = job
        if not ctx.stop.is_set() and _open(d.ip, p, timeout):
            d.open_ports.add(p)
        done += 1
        if done % 50 == 0:
            ctx.progress("ports", done / len(jobs))

    with ThreadPoolExecutor(max_workers=128) as pool:
        list(pool.map(work, jobs))
    ctx.progress("ports", 1.0)


def _http_get(url: str, timeout: float = 2.0) -> tuple[str, dict, str] | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "netscout"})
        with urllib.request.urlopen(req, timeout=timeout, context=_UNVERIFIED) as r:
            return str(r.status), dict(r.headers), r.read(16384).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:   # 401/403 pages still carry Server header and title
        try:
            return str(e.code), dict(e.headers), e.read(16384).decode("utf-8", "replace")
        except Exception:
            return None
    except Exception:
        return None


def _banners(d: Device) -> None:
    for port in HTTP_PORTS:
        if port not in d.open_ports:
            continue
        scheme = "https" if port in (443, 8443) else "http"
        res = _http_get(f"{scheme}://{d.ip}:{port}/")
        if not res:
            continue
        _, headers, body = res
        server = headers.get("Server") or headers.get("server")
        title = _TITLE.search(body)
        www = headers.get("WWW-Authenticate") or headers.get("www-authenticate")
        if server:
            d.text.append(server)
            d.facts[f"http{port}_server"] = server
        if title:
            d.text.append(title.group(1))
            d.facts[f"http{port}_title"] = title.group(1)
        if www and "realm=" in www.lower():
            d.text.append(www)   # many cameras/routers put the model in the auth realm
    if 22 in d.open_ports:
        try:
            with socket.create_connection((d.ip, 22), timeout=1.5) as s:
                s.settimeout(1.5)
                banner = s.recv(128).decode("ascii", "replace").strip()
            if banner.startswith("SSH-"):
                d.facts["ssh_banner"] = banner
                d.text.append(banner)
        except OSError:
            pass
    if 554 in d.open_ports:
        try:
            with socket.create_connection((d.ip, 554), timeout=1.5) as s:
                s.settimeout(1.5)
                s.sendall(f"OPTIONS rtsp://{d.ip}/ RTSP/1.0\r\nCSeq: 1\r\n\r\n".encode())
                resp = s.recv(512).decode("ascii", "replace")
            m = re.search(r"^Server:\s*(.+)$", resp, re.M | re.I)
            if m:
                d.facts["rtsp_server"] = m.group(1).strip()
                d.text.append(m.group(1))
        except OSError:
            pass
    if 8060 in d.open_ports:   # Roku External Control Protocol
        res = _http_get(f"http://{d.ip}:8060/query/device-info")
        if res:
            try:
                root = ET.fromstring(res[2])
                g = lambda t: (root.findtext(t) or "").strip()
                if g("model-name"):
                    d.model = d.model or g("model-name")
                if g("user-device-name") or g("friendly-device-name"):
                    d.names.setdefault("roku", g("user-device-name") or g("friendly-device-name"))
                d.text.append("roku " + g("model-name"))
            except ET.ParseError:
                pass
    if 8008 in d.open_ports:   # Google Cast
        res = _http_get(f"http://{d.ip}:8008/setup/eureka_info")
        if res:
            try:
                info = json.loads(res[2])
                if info.get("name"):
                    d.names.setdefault("cast", info["name"])
                if info.get("model_name"):
                    d.model = d.model or info["model_name"]
                    d.text.append(info["model_name"])
            except ValueError:
                pass


_TTL = re.compile(r"ttl[=:]\s*(\d+)", re.I)


def _ttl(d: Device) -> None:
    """One ICMP echo via the system ping (no raw sockets); TTL hints at the OS family."""
    args = (["ping", "-n", "1", "-w", "1000", d.ip] if sys.platform == "win32"
            else ["ping", "-c", "1", "-W", "1", d.ip])
    m = _TTL.search(run_cmd(args, timeout=4))
    if m:
        d.facts["ttl"] = m.group(1)


def _rdns(d: Device) -> None:
    try:
        host = socket.gethostbyaddr(d.ip)[0]
    except OSError:
        return
    if host and host != d.ip:
        short = host.split(".")[0]
        d.names.setdefault("dns", short)
        if not d.hostname:
            d.hostname = short


def enrich(ctx: ScanContext, devices: list[Device]) -> None:
    def work(d: Device) -> None:
        if ctx.stop.is_set():
            return
        _rdns(d)
        _ttl(d)
        _banners(d)
        ctx.table.touch(d)

    with ThreadPoolExecutor(max_workers=32) as pool:
        list(pool.map(work, devices))
