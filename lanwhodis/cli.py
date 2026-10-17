"""lanwhodis command line: scan the local network and print or export the results."""
from __future__ import annotations

import argparse
import signal
import sqlite3
import sys
import threading
import time

from . import __version__, devtypes, export, history, labels, oui, paths, rules, scanner
from .discovery import net


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lanwhodis",
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
    lab = p.add_argument_group("corrections (remembered across scans, keyed by MAC)")
    lab.add_argument("--label", metavar="MAC|IP", help="correct a device; combine with --set-type/-name/-notes")
    lab.add_argument("--set-type", metavar="TYPE", help="device type, e.g. camera, thermostat (see --list-types)")
    lab.add_argument("--set-name", metavar="NAME", help='your name for it ("" clears it)')
    lab.add_argument("--set-notes", metavar="TEXT", help='free-form notes ("" clears them)')
    lab.add_argument("--forget", metavar="MAC|IP", help="remove a correction")
    lab.add_argument("--list-labels", action="store_true", help="show your corrections next to what was auto-detected")
    lab.add_argument("--list-types", action="store_true", help="show valid device types")
    lab.add_argument("--suggest-rules", action="store_true",
                     help="print custom vendor rules derived from your corrections (review, then save as vendor.toml)")
    lab.add_argument("--no-labels", action="store_true", help="ignore your corrections for this scan")
    hist = p.add_argument_group("history (what appeared, left, returned or moved between scans)")
    hist.add_argument("--no-history", action="store_true", help="don't record this scan (history is on by default)")
    hist.add_argument("--known", action="store_true", help="list every device ever seen, with first/last seen")
    hist.add_argument("--events", nargs="?", type=int, const=30, metavar="N",
                      help="show the last N change events (default 30) and exit")
    hist.add_argument("--watch", type=float, metavar="MINUTES",
                      help="rescan every MINUTES and print changes (new / returned / moved / left)")
    hist.add_argument("--forget-history", action="store_true", help="delete the recorded history")
    p.add_argument("--services", action="store_true",
                   help="include each device's advertised services in txt/md output (always in json/xlsx/html)")
    p.add_argument("--no-snmp", action="store_true", help="don't query SNMP (read-only GETs; default community 'public')")
    p.add_argument("--snmp-community", action="append", metavar="NAME",
                   help="SNMP read community to try (repeatable; default: public)")
    p.add_argument("--no-ports", action="store_true", help="skip TCP port probing (faster, quieter)")
    p.add_argument("-t", "--timeout", type=float, default=4.0,
                   help="seconds to listen for mDNS/SSDP/WSD replies (default 4)")
    p.add_argument("-v", "--verbose", action="store_true", help="log discovery progress to stderr")
    p.add_argument("-V", "--version", action="version", version=f"lanwhodis {__version__}")
    return p


def _label_command(args) -> int | None:
    """Handle the corrections options. Returns an exit code, or None when none were used."""
    wants = [args.label, args.forget, args.list_labels, args.list_types, args.suggest_rules]
    if not any(wants):
        return None
    if args.list_types:
        for key, (name, category, _) in sorted(devtypes.TYPES.items(), key=lambda kv: (kv[1][1], kv[0])):
            print(f"{key:18} {name}  [{category}]")
        return 0
    store = labels.LabelStore()
    if args.suggest_rules:
        sys.stdout.write(labels.suggest_rules(store))
        return 0
    if args.list_labels:
        entries = store.all()
        if not entries:
            print(f"no corrections yet ({store.path})")
        for key, e in sorted(entries.items()):
            auto = e.get("auto") or {}
            auto_t = auto.get("type")
            note = ""
            if e.get("type") and auto_t:
                same = "=" if e["type"] == auto_t else "!="
                note = f"  [auto: {devtypes.label(auto_t)} {int((auto.get('confidence') or 0) * 100)}% {same}]"
            print(f"{key:20} {e.get('name', '-'):24} {e.get('type', '-'):16}{note}"
                  + (f"  # {e['notes']}" if e.get("notes") else ""))
        return 0
    try:
        if args.forget:
            key = labels.normalize_key(args.forget, net.read_arp())
            print(f"forgot {key}" if store.forget(key) else f"no correction stored for {key}")
            return 0
        key = labels.normalize_key(args.label, net.read_arp())
        if args.set_type is None and args.set_name is None and args.set_notes is None:
            print("lanwhodis: --label needs at least one of --set-type, --set-name, --set-notes", file=sys.stderr)
            return 2
        fields = {n: v for n, v in (("type", args.set_type), ("name", args.set_name), ("notes", args.set_notes))
                  if v is not None}
        # No scan here, so the only evidence snapshot we can record is the OUI vendor.
        store.set(key, auto={"vendor": oui.lookup(key)} if oui.normalize_mac(key) else None, **fields)
        print(f"saved {key}: " + ", ".join(f"{k}={v!r}" for k, v in fields.items()))
        return 0
    except ValueError as e:
        print(f"lanwhodis: {e}", file=sys.stderr)
        return 2


def _scan(args, ifaces, stop, log):
    return scanner.scan(ifaces, timeout=args.timeout, port_scan=not args.no_ports, snmp=not args.no_snmp,
                        snmp_communities=tuple(args.snmp_community or ("public",)),
                        labels=not args.no_labels, stop=stop, log=log)


def _record(devices, ifaces, args, stop):
    """Store the scan in the history; None when disabled, cancelled (a partial scan would make half the
    network look gone) or unavailable. History trouble never costs you the scan results."""
    if args.no_history or stop.is_set():
        return None
    try:
        return history.History().record(devices, [str(i.network) for i in ifaces])
    except (sqlite3.Error, OSError) as e:
        print(f"lanwhodis: history unavailable ({e})", file=sys.stderr)
        return None


def _watch(args, ifaces, stop, log) -> int:
    nets = ", ".join(str(i.network) for i in ifaces)
    print(f"watching {nets} every {args.watch:g} min (Ctrl-C to stop); changes are logged to the history",
          file=sys.stderr)
    while not stop.is_set():
        try:
            devices = _scan(args, ifaces, stop, log)
        except RuntimeError as e:
            print(f"lanwhodis: {e}", file=sys.stderr)
            return 1
        diff = _record(devices, ifaces, args, stop)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        lines = diff.summary_lines() if diff else []
        for line in lines or [f"{len(devices)} devices, no changes"]:
            print(f"{stamp}  {line}", flush=True)
        stop.wait(args.watch * 60)
    return 130


def _history_command(args) -> int | None:
    if not (args.known or args.events is not None or args.forget_history):
        return None
    try:
        h = history.History()
        fmt = lambda ts: time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
        if args.forget_history:
            h.clear()
            print(f"history cleared ({h.path})")
        elif args.known:
            known = h.known()
            if not known:
                print(f"no devices recorded yet ({h.path})")
            for k in known:
                state = f"offline (missed {k.missed} scans)" if k.offline else "online"
                print(f"{k.last_ip:<15} {k.name[:26]:<26} {k.type:<14} first {fmt(k.first_seen)}  "
                      f"last {fmt(k.last_seen)}  seen {k.seen_count}x  {state}")
        else:
            events = h.events(args.events)
            if not events:
                print("no events yet (the first scan of a network is just a baseline)")
            for e in events:
                print(f"{fmt(e.ts)}  {e.kind.upper():<10} {e.name[:26]:<26} {e.detail}")
        return 0
    except (sqlite3.Error, OSError) as e:
        print(f"lanwhodis: history unavailable ({e})", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    args = _parser().parse_args(argv)
    rc = _label_command(args)
    if rc is None:
        rc = _history_command(args)
    if rc is not None:
        return rc
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
        print("lanwhodis: no matching IPv4 interface found", file=sys.stderr)
        return 2

    targets: list[tuple[str, str | None]] = []   # (format, path or None for stdout)
    for path in args.output:
        fmt = args.format if export.format_for_path(path) is None else export.format_for_path(path)
        if fmt is None:
            print(f"lanwhodis: can't infer format for {path!r}; use -f", file=sys.stderr)
            return 2
        targets.append((fmt, path))
    if not targets:
        fmt = args.format or "txt"
        if fmt in export.BINARY:
            print(f"lanwhodis: {fmt} is binary; use -o FILE.{fmt}", file=sys.stderr)
            return 2
        targets.append((fmt, None))

    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    log = (lambda m: print(f"[lanwhodis] {m}", file=sys.stderr)) if args.verbose else (lambda m: None)
    if args.watch:
        if args.output or args.format or args.no_history:
            print("lanwhodis: --watch prints change events from the history; it can't be combined with "
                  "-o / -f / --no-history", file=sys.stderr)
            return 2
        return _watch(args, ifaces, stop, log)
    if not args.verbose:
        print("Scanning " + ", ".join(str(i.network) for i in ifaces) + " …", file=sys.stderr)

    try:
        devices = _scan(args, ifaces, stop, log)
    except RuntimeError as e:
        print(f"lanwhodis: {e}", file=sys.stderr)
        return 1
    diff = _record(devices, ifaces, args, stop)
    for line in (diff.summary_lines() if diff else []):
        print(f"history: {line}", file=sys.stderr)

    meta = {"networks": ", ".join(str(i.network) for i in ifaces), "with_services": args.services}
    for fmt, path in targets:
        if path is None:
            sys.stdout.write(export.render(devices, fmt, meta))  # type: ignore[arg-type]
        else:
            export.write(devices, fmt, path, meta)
            print(f"wrote {path}", file=sys.stderr)
    return 130 if stop.is_set() else 0


if __name__ == "__main__":
    sys.exit(main())
