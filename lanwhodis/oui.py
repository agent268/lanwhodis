"""MAC address -> vendor lookup against the bundled IEEE registry snapshot."""
from __future__ import annotations

import gzip
import re
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).parent / "data" / "oui.tsv.gz"
_HEX = re.compile(r"[^0-9A-Fa-f]")


def normalize_mac(mac: str) -> str | None:
    """Return 'aa:bb:cc:dd:ee:ff' or None if it isn't a 48-bit MAC."""
    h = _HEX.sub("", mac or "")
    if len(h) != 12:
        return None
    h = h.lower()
    return ":".join(h[i:i + 2] for i in range(0, 12, 2))


def is_locally_administered(mac: str) -> bool:
    """Randomized/private MACs (phones rotate these) have the U/L bit set."""
    n = normalize_mac(mac)
    return bool(n and int(n[:2], 16) & 0x02)


@lru_cache(maxsize=1)
def _table() -> dict[str, str]:
    table: dict[str, str] = {}
    if not DATA.exists():
        return table
    with gzip.open(DATA, "rt", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                continue
            prefix, _, vendor = line.rstrip("\n").partition("\t")
            table[prefix] = vendor
    return table


def lookup(mac: str) -> str | None:
    """Vendor for a MAC, preferring the most specific (MA-S > MA-M > MA-L) assignment."""
    n = normalize_mac(mac)
    if not n or is_locally_administered(n):
        return None
    h = n.replace(":", "").upper()
    t = _table()
    for length in (9, 7, 6):
        v = t.get(h[:length])
        if v:
            return v
    return None
