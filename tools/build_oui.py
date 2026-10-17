"""Build lanwhodis/data/oui.tsv.gz from the IEEE registries (MA-L, MA-M, MA-S).

Usage:
    python tools/build_oui.py              # download from standards-oui.ieee.org
    python tools/build_oui.py --from DIR   # use already-downloaded oui.csv / mam.csv / oui36.csv

Output lines are "<hex prefix>\t<vendor>"; prefix length (6/7/9 hex digits) encodes
the assignment size, so the lookup can prefer the most specific match.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import sys
import urllib.request
from datetime import date
from pathlib import Path

SOURCES = {
    "oui.csv": "https://standards-oui.ieee.org/oui/oui.csv",
    "mam.csv": "https://standards-oui.ieee.org/oui28/mam.csv",
    "oui36.csv": "https://standards-oui.ieee.org/oui36/oui36.csv",
}
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130 Safari/537.36"
OUT = Path(__file__).resolve().parent.parent / "lanwhodis" / "data" / "oui.tsv.gz"


def fetch(name: str, src_dir: Path | None) -> str:
    if src_dir:
        return (src_dir / name).read_text(encoding="utf-8-sig")
    req = urllib.request.Request(SOURCES[name], headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8-sig")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", type=Path)
    args = ap.parse_args()

    rows: dict[str, str] = {}
    for name in SOURCES:
        for rec in csv.DictReader(io.StringIO(fetch(name, args.src))):
            prefix = rec["Assignment"].strip().upper()
            org = " ".join(rec["Organization Name"].split())
            if prefix and org:
                rows[prefix] = org

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", encoding="utf-8", newline="\n") as f:
        f.write(f"#built {date.today().isoformat()} from IEEE MA-L/MA-M/MA-S\n")
        for prefix in sorted(rows):
            f.write(f"{prefix}\t{rows[prefix]}\n")
    print(f"{len(rows)} assignments -> {OUT} ({OUT.stat().st_size // 1024} KiB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
