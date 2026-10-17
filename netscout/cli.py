"""netscout command line: scan the local network and print or export the results."""
from __future__ import annotations

import argparse
import signal
import sys
import threading

from . import __version__, export, paths, rules, scanner
from .discovery import net


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="netscout",
        description="Discover and identify consumer/SMB devices on the local network.",
        epilog="Output format is inferred from each -o extension "
               f"({', '.join(export.FORMATS)}). Without -o, a text table is printed.")
    p.add_argument("-o", "--output", action="append", default=[], metavar="FILE",
                   help="write results to FILE (repeatable, e.g. -o r.json -o r.xlsx)")
    p.add_argument("-f", "--format", choices=export.FORMATS,
                   help="format for stdout, or to force for -o files with unknown extensions")
    p.add_argument("-i", "--interface", metavar="NAME|IP",
                   help="scan only this interface (name or address substring); default: all")
    p.add_argument("--include-virtual", action="store_true",
                   help="also scan Hyper-V/WSL/Docker/VPN adapters (hidden by default)")
    p.add_argument("--list-interfaces", action="store_true", help="show scannable interfaces and exit")
    p.add_argument("--check-rules", action="store_true",
                   help="validate your custom rules (see README, 'Custom rules') and exit")
    p.add_argument("--no-ports", action="store_true", help="skip TCP port probing (faster, quieter)")
    p.add_argument("-t", "--timeout", type=float, default=4.0,
                   help="seconds to listen for mDNS/SSDP/WSD replies (default 4)")
    p.add_argument("-v", "--verbose", action="store_true", help="log discovery progress to stderr")
    p.add_argument("-V", "--version", action="version", version=f"netscout {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    args = _parser().parse_args(argv)
    if args.check_rules:
        rs = rules.reload()
        print(f"rules dir: {paths.rules_dir()}")
        print(f"loaded {len(rs.vendor)} vendor, {len(rs.names)} name, {len(rs.text)} text, "
              f"{len(rs.services)} service, {len(rs.ports)} port, {len(rs.os_text)} OS-text rules")
        for e in rs.errors:
            print(f"  error: {e}")
        print("OK" if not rs.errors else f"{len(rs.errors)} problem(s); those rules were skipped")
        return 1 if rs.errors else 0
    ifaces = net.list_interfaces(args.include_virtual)

    if args.list_interfaces:
        for i in ifaces:
            print(i.label)
        return 0
    if args.interface:
        q = args.interface.lower()
        ifaces = [i for i in ifaces if q in i.name.lower() or q in i.ip]
    if not ifaces:
        print("netscout: no matching IPv4 interface found", file=sys.stderr)
        return 2

    targets: list[tuple[str, str | None]] = []   # (format, path or None for stdout)
    for path in args.output:
        fmt = args.format if export.format_for_path(path) is None else export.format_for_path(path)
        if fmt is None:
            print(f"netscout: can't infer format for {path!r}; use -f", file=sys.stderr)
            return 2
        targets.append((fmt, path))
    if not targets:
        fmt = args.format or "txt"
        if fmt in export.BINARY:
            print(f"netscout: {fmt} is binary; use -o FILE.{fmt}", file=sys.stderr)
            return 2
        targets.append((fmt, None))

    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    log = (lambda m: print(f"[netscout] {m}", file=sys.stderr)) if args.verbose else (lambda m: None)
    if not args.verbose:
        print("Scanning " + ", ".join(str(i.network) for i in ifaces) + " …", file=sys.stderr)

    try:
        devices = scanner.scan(ifaces, timeout=args.timeout, port_scan=not args.no_ports, stop=stop, log=log)
    except RuntimeError as e:
        print(f"netscout: {e}", file=sys.stderr)
        return 1

    meta = {"networks": ", ".join(str(i.network) for i in ifaces)}
    for fmt, path in targets:
        if path is None:
            sys.stdout.write(export.render(devices, fmt, meta))  # type: ignore[arg-type]
        else:
            export.write(devices, fmt, path, meta)
            print(f"wrote {path}", file=sys.stderr)
    return 130 if stop.is_set() else 0


if __name__ == "__main__":
    sys.exit(main())
