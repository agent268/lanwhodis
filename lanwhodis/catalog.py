"""Friendly display names for advertised services (data: lanwhodis/data/catalog.toml)."""
from __future__ import annotations

import tomllib
from functools import lru_cache
from importlib import resources


@lru_cache(maxsize=1)
def _catalog() -> dict[str, dict[str, str]]:
    text = (resources.files("lanwhodis") / "data" / "catalog.toml").read_text(encoding="utf-8")
    return tomllib.loads(text)


def friendly(protocol: str, kind: str) -> str:
    """'mdns', '_ipp._tcp' -> 'Internet Printing (IPP)'; unknown kinds are returned prettified."""
    cat = _catalog()
    key = kind.removesuffix(".local").removesuffix(".")
    if protocol == "ssdp":           # search targets: upnp:rootdevice, ssdp:all, urn:...:device|service:Type:1
        parts = key.split(":")
        versioned = len(parts) > 2 and parts[-1].replace("-", "").replace(".", "").isdigit()
        short = (parts[-2] if versioned else parts[-1]).lower()
        return cat.get("upnp", {}).get(short) or (short if key.startswith("urn:") else key)
    hit = cat.get(protocol, {}).get(key if protocol != "upnp" else key.lower())
    if hit:
        return hit
    pretty = key.strip("_").replace("._tcp", "").replace("._udp", "").replace("-", " ").replace("_", " ")
    return pretty[:1].upper() + pretty[1:] if pretty else kind
