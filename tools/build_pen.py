"""Build lanwhodis/data/pen.tsv.gz from the IANA Private Enterprise Numbers registry.

SNMP's sysObjectID is 1.3.6.1.4.1.<enterprise number>...; the number names the vendor. Only the
number and organisation are kept (the registry's contact names/emails are deliberately dropped).

Usage:
    python tools/build_pen.py                # download from iana.org
    python tools/build_pen.py --from FILE    # use an already-downloaded enterprise-numbers.txt
"""
from __future__ import annotations

import argparse
import gzip
import re
import sys
import urllib.request
from pathlib import Path

URL = "https://www.iana.org/assignments/enterprise-numbers.txt"
OUT = Path(__file__).resolve().parent.parent / "lanwhodis" / "data" / "pen.tsv.gz"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", type=Path)
    args = ap.parse_args()
    if args.src:
        text = args.src.read_text(encoding="utf-8", errors="replace")
    else:
        req = urllib.request.Request(URL, headers={"User-Agent": "lanwhodis-build"})
        text = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")

    updated = (re.search(r"\(last updated ([\d-]+)\)", text) or [None, "unknown"])[1]
    lines = text.splitlines()
    rows: dict[int, str] = {}
    i = 0
    while i < len(lines) - 1:
        # entry = "<number>" then the organisation indented by exactly two spaces
        if lines[i].isdigit() and lines[i + 1].startswith("  ") and not lines[i + 1].startswith("   "):
            org = " ".join(lines[i + 1].split())
            if org and org not in ("Reserved", "Unassigned", "---none---"):
                rows[int(lines[i])] = org
            i += 2
        else:
            i += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(OUT, "wb", compresslevel=9, mtime=0) as f:
        f.write(f"#IANA enterprise numbers, registry last updated {updated}\n".encode())
        for n in sorted(rows):
            f.write(f"{n}\t{rows[n]}\n".encode("utf-8"))
    print(f"{len(rows)} enterprises (registry {updated}) -> {OUT} ({OUT.stat().st_size // 1024} KiB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
