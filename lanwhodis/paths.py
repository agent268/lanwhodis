"""Per-user locations for LanWhodis's own files (rules, labels, history)."""
from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path

log = logging.getLogger("lanwhodis.paths")

APP_DIR = "lanwhodis"
LEGACY_DIR = "netscout"            # the project's name before it became LanWhodis


def _base() -> Path:
    """The platform's per-user data root (the app directory lives inside it)."""
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def data_dir() -> Path:
    """Directory for user data. LANWHODIS_HOME overrides (tests, portable installs); the old
    NETSCOUT_HOME is still honoured. A data directory left by the old name is moved over once."""
    override = os.environ.get("LANWHODIS_HOME") or os.environ.get("NETSCOUT_HOME")
    if override:
        return Path(override)
    new, old = _base() / APP_DIR, _base() / LEGACY_DIR
    if not new.exists() and old.is_dir():
        try:
            shutil.move(str(old), str(new))
            log.info("moved your %s data to %s", LEGACY_DIR, new)
        except OSError as e:           # locked by something? keep working from where the data is
            log.warning("could not move %s to %s (%s); using it in place", old, new, e)
            return old
    return new


def rules_dir() -> Path:
    return data_dir() / "rules"


def ensure(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p
