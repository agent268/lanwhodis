"""Per-user locations for netscout's own files (rules, labels, history)."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def data_dir() -> Path:
    """Directory for user data. NETSCOUT_HOME overrides (used by tests and portable installs)."""
    override = os.environ.get("NETSCOUT_HOME")
    if override:
        return Path(override)
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "netscout"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "netscout"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "netscout"


def rules_dir() -> Path:
    return data_dir() / "rules"


def ensure(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p
