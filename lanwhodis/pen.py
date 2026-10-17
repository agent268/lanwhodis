"""IANA Private Enterprise Numbers: the vendor behind an SNMP sysObjectID."""
from __future__ import annotations

import gzip
from functools import lru_cache
from importlib import resources

_PREFIX = "1.3.6.1.4.1."


@lru_cache(maxsize=1)
def _table() -> dict[int, str]:
    table: dict[int, str] = {}
    path = resources.files("lanwhodis") / "data" / "pen.tsv.gz"
    if not path.is_file():
        return table
    for line in gzip.decompress(path.read_bytes()).decode("utf-8").splitlines():
        if line and not line.startswith("#"):
            num, _, org = line.partition("\t")
            table[int(num)] = org
    return table


def lookup(number: int) -> str | None:
    return _table().get(number)


def vendor_for_oid(sys_object_id: str) -> str | None:
    """'1.3.6.1.4.1.41112.1.6' -> 'Ubiquiti Networks, Inc.'"""
    if not sys_object_id.startswith(_PREFIX):
        return None
    head = sys_object_id[len(_PREFIX):].split(".", 1)[0]
    return lookup(int(head)) if head.isdigit() else None
