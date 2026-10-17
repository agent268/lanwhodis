"""Fetch the Fluent UI System Icons LanWhodis uses into lanwhodis/gui/assets/icons/*.svg.

Fluent UI System Icons (https://github.com/microsoft/fluentui-system-icons) are MIT licensed; the notice
is written next to the icons. Files are pinned to a commit so the bundled set is reproducible, and only
the icons listed below are fetched (filled variant first, regular as the fallback). The same icon family
steamos-fm uses, so the two apps look related.

Usage:
    python tools/update_icons.py              # newest commit
    python tools/update_icons.py --ref SHA    # a specific commit
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = "microsoft/fluentui-system-icons"
OUT = Path(__file__).resolve().parent.parent / "lanwhodis" / "gui" / "assets" / "icons"
UA = {"User-Agent": "lanwhodis-update-icons"}

# LanWhodis device type key -> Fluent icon family
DEVICES = {
    "computer": "Desktop", "laptop": "Laptop", "server": "Server", "raspberry_pi": "Developer Board",
    "nas": "Storage", "phone": "Phone", "tablet": "Tablet", "tv": "TV", "streaming": "Cast",
    "media_server": "Server Play", "speaker": "Speaker 2", "wireless_display": "Cast Multiple",
    "signage": "Presenter", "game_console": "Xbox Console", "handheld_console": "Games", "camera": "Camera",
    "doorbell": "Service Bell", "thermostat": "Temperature", "water_heater": "Drop",
    "garage_door": "Home Garage", "appliance": "Washer", "pet_feeder": "Animal Paw Print", "smart_plug": "Plug Connected",
    "light": "Lightbulb", "hub": "Home Database", "iot": "Memory", "printer": "Print", "voip": "Call",
    "router": "Router", "gateway": "Globe", "switch": "Network Adapter", "access_point": "WiFi 1",
    "extender": "WiFi 2", "unknown": "Question Circle",
}
# interface glyph name -> Fluent icon family
UI = {
    "search": "Search", "scan": "Radar", "stop": "Stop", "sync": "Arrow Sync", "export": "Arrow Download",
    "settings": "Settings", "eye": "Eye", "eye_off": "Eye Off", "edit": "Edit", "copy": "Copy", "open": "Open",
    "close": "Dismiss", "add": "Add", "check": "Checkmark", "check_circle": "Checkmark Circle", "info": "Info",
    "warning": "Warning", "history": "History", "tag": "Tag", "filter": "Filter", "grid": "Grid", "list": "List",
    "globe": "Globe", "wifi": "WiFi 1", "shield": "Shield Checkmark", "clock": "Clock", "lock": "Lock Closed",
    "chevron_right": "Chevron Right", "chevron_down": "Chevron Down", "home": "Home", "pin": "Pin",
    "apps": "Apps", "theme": "Dark Theme", "sun": "Weather Sunny", "moon": "Weather Moon", "alert": "Alert",
    "dismiss_circle": "Dismiss Circle", "arrow_sync": "Arrow Sync", "play": "Play", "star": "Star",
    "person": "Person", "key": "Key", "plug": "Plug Connected",
}
SIZES = (24, 20, 28, 32, 16, 48)
STYLES = ("filled", "regular")

NOTICE = """These icons are from the Fluent UI System Icons project (filled variant where available,
otherwise regular), fetched by tools/update_icons.py at the commit recorded in SOURCE.txt:

  https://github.com/microsoft/fluentui-system-icons

MIT License

Copyright (c) 2020 Microsoft Corporation

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
associated documentation files (the "Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the
following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO
EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
USE OR OTHER DEALINGS IN THE SOFTWARE.
"""


def get(url: str) -> bytes | None:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def fetch_icon(sha: str, family: str) -> tuple[bytes, str] | None:
    snake = family.lower().replace(" ", "_")
    for style in STYLES:
        for size in SIZES:
            path = f"assets/{urllib.parse.quote(family)}/SVG/ic_fluent_{snake}_{size}_{style}.svg"
            data = get(f"https://raw.githubusercontent.com/{REPO}/{sha}/{path}")
            if data:
                return data, f"{size}/{style}"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref")
    args = ap.parse_args()
    url = f"https://api.github.com/repos/{REPO}/commits/" + (args.ref or "HEAD")
    commit = json.loads(get(url) or b"{}")
    sha, date = commit["sha"], commit["commit"]["committer"]["date"]

    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("*.svg"):
        stale.unlink()
    missing, report = [], []
    for kind, table, prefix in (("device", DEVICES, "device_"), ("ui", UI, "ui_")):
        for key, family in table.items():
            found = fetch_icon(sha, family)
            if not found:
                missing.append(f"{kind}:{key} ({family})")
                continue
            data, how = found
            (OUT / f"{prefix}{key}.svg").write_bytes(data)
            report.append(f"{prefix}{key} <- {family} [{how}]")
    (OUT / "LICENSE-fluent-icons.txt").write_text(NOTICE, encoding="utf-8", newline="\n")
    (OUT / "SOURCE.txt").write_text(f"{REPO} @ {sha}\ncommitted {date}\n" + "\n".join(report) + "\n",
                                    encoding="utf-8", newline="\n")
    print(f"{len(report)} icons from {sha[:10]} ({date}); {len(list(OUT.glob('*.svg')))} files written")
    if missing:
        print("MISSING:", ", ".join(missing))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
