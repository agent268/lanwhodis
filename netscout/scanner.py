"""Scan orchestration. Used by both the CLI and the GUI; has no UI dependencies."""
from __future__ import annotations

import ipaddress
import threading
from typing import Callable

from . import classify, recog
from .discovery import mdns, net, probe, ssdp, sweep, wsd
from .discovery.base import Iface, ScanContext
from .model import Device, DeviceTable


def scan(
    ifaces: list[Iface] | None = None,
    *,
    timeout: float = 4.0,
    port_scan: bool = True,
    stop: threading.Event | None = None,
    log: Callable[[str], None] = lambda m: None,
    progress: Callable[[str, float], None] = lambda s, f: None,
    on_update: Callable[[Device], None] | None = None,
) -> list[Device]:
    """Run all discovery stages and return classified devices sorted by IP."""
    ifaces = ifaces or net.list_interfaces()
    if not ifaces:
        raise RuntimeError("no usable IPv4 network interface found")
    table = DeviceTable(on_update=on_update)
    gateways = net.default_gateways()
    for i in ifaces:   # a big subnet is clamped to a /24; still probe the gateway if it lies outside it
        if i.full_network:
            i.extra_hosts = [g for g in gateways if ipaddress.ip_address(g) in i.full_network
                             and ipaddress.ip_address(g) not in i.network]
    ctx = ScanContext(table=table, ifaces=ifaces, gateways=gateways,
                      stop=stop or threading.Event(), log=log, progress=progress,
                      timeout=timeout, port_scan=port_scan)

    # Stage 1: everything that listens passively or sweeps, concurrently.
    threads = []
    for name, fn in (("sweep", sweep.run), ("mdns", mdns.run), ("ssdp", ssdp.run), ("wsd", wsd.run)):
        t = threading.Thread(target=_guard, args=(name, fn, ctx), name=name, daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

    # Fill MACs for hosts only seen via multicast, now that the ARP cache is warm.
    arp = net.read_arp()
    for d in table.all():
        if d.ip in ctx.gateways:
            d.is_gateway = True
        if not d.mac and d.ip in arp:
            table.get(d.ip, arp[d.ip])

    # Stage 2: unicast probing of the hosts we know about.
    devices = table.all()
    if port_scan and not ctx.stop.is_set():
        log(f"probing ports on {len(devices)} hosts")
        probe.scan_ports(ctx, devices)
    if not ctx.stop.is_set():
        log("reading banners / reverse DNS")
        probe.enrich(ctx, devices)

    # TCP probes force ARP resolution, so hosts that stayed silent in the sweep now have neighbor
    # entries; fill their MACs (and so vendor/OUI evidence) before classifying.
    arp = net.read_arp()
    for d in devices:
        if not d.mac and d.ip in arp:
            table.get(d.ip, arp[d.ip])

    for d in devices:
        recog.annotate(d)
        classify.classify(d)
        table.touch(d)
    return devices


def _guard(name: str, fn, ctx: ScanContext) -> None:
    try:
        fn(ctx)
    except Exception as e:   # one broken protocol must not kill the scan
        ctx.log(f"{name}: failed ({type(e).__name__}: {e})")
