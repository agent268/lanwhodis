"""mDNS / DNS-SD (Bonjour/Avahi): enumerate every advertised service type, then resolve each."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf, ZeroconfServiceTypes

from ..model import ServiceRecord
from .base import ScanContext

_META = "_services._dns-sd._udp.local."


def _txt(props: dict) -> dict[str, str]:
    out = {}
    for k, v in props.items():
        key = k.decode("utf-8", "replace") if isinstance(k, bytes) else str(k)
        out[key.lower()] = v.decode("utf-8", "replace") if isinstance(v, bytes) else ("" if v is None else str(v))
    return out


def run(ctx: ScanContext) -> None:
    zc = Zeroconf()
    try:
        ctx.log("mdns: enumerating service types")
        types = list(ZeroconfServiceTypes.find(zc=zc, timeout=ctx.timeout))
        if ctx.stop.is_set():
            return
        found: set[tuple[str, str]] = set()

        def handler(zeroconf, service_type, name, state_change):
            if state_change is ServiceStateChange.Added:
                found.add((service_type, name))

        browser = ServiceBrowser(zc, types, handlers=[handler]) if types else None
        time.sleep(min(ctx.timeout, 3.0))
        if browser:
            browser.cancel()
        ctx.log(f"mdns: {len(types)} service types, {len(found)} instances")

        def resolve(item: tuple[str, str]) -> None:
            stype, name = item
            info = zc.get_service_info(stype, name, timeout=2000)
            if not info:
                return
            props = _txt(info.properties or {})
            for addr in info.parsed_addresses():
                if ":" in addr or not ctx.in_scope(addr):
                    continue
                d = ctx.table.get(addr)
                short = stype.replace(".local.", "")
                d.services.add(f"mdns:{short}")
                inst = name[: -len(stype) - 1] if name.endswith("." + stype) else name
                d.names.setdefault("mdns", inst)
                d.add_service(ServiceRecord("mdns", short, name=inst, port=info.port or None,
                                            details={k: v[:120] for k, v in list(props.items())[:24]}))
                if info.server:
                    host = info.server.rstrip(".")
                    d.facts.setdefault("mdns_host", host)
                    if not d.hostname and host.endswith(".local"):
                        d.hostname = host[:-6]
                if info.port:
                    d.facts[f"mdns:{short}"] = f"port {info.port}"
                if short in ("_http._tcp", "_https._tcp") and info.port:
                    path = props.get("path") or "/"
                    scheme = "https" if short == "_https._tcp" else "http"
                    d.add_web_url(f"{scheme}://{addr}:{info.port}{path if path.startswith('/') else '/' + path}",
                                  "mdns", 2)
                if props.get("adminurl"):     # printers (IPP) and some cast devices publish this
                    d.add_web_url(props["adminurl"], "mdns", 1)
                # model hints live in TXT records: model/md/am/ty/product, fn/fn=friendly name
                for key in ("model", "md", "am", "ty", "product", "modelname"):
                    if props.get(key):
                        d.model = d.model or props[key]
                        d.text.append(props[key])
                        break
                for key in ("fn", "friendlyname", "name"):
                    if props.get(key):
                        d.names.setdefault("friendly", props[key])
                        break
                if props.get("manufacturer") or props.get("mfg"):
                    d.facts.setdefault("manufacturer", props.get("manufacturer") or props["mfg"])
                if short == "_device-info._tcp":
                    if props.get("model"):
                        d.text.append(props["model"])
                    d.facts["device_info_txt"] = "|".join(f"{k}={v}" for k, v in props.items())[:400]
                ctx.table.touch(d)

        with ThreadPoolExecutor(max_workers=16) as pool:
            list(pool.map(resolve, sorted(found)))
    finally:
        zc.close()
