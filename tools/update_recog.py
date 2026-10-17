"""Fetch the Rapid7 Recog fingerprint databases netscout uses into netscout/data/recog/*.xml.gz.

Recog (https://github.com/rapid7/recog) is BSD-2-Clause; the notice shipped alongside the data is
written to data/recog/LICENSE.txt. Files are pinned to a commit so the bundled data is reproducible.

Usage:
    python tools/update_recog.py              # newest commit on the default branch
    python tools/update_recog.py --ref SHA    # a specific commit
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import urllib.request
from pathlib import Path

REPO = "rapid7/recog"
DATABASES = ["ssh_banners", "http_servers", "html_title", "http_wwwauth", "rtsp_servers", "snmp_sysdescr",
             "snmp_sysobjid", "mdns_device-info_txt"]
OUT = Path(__file__).resolve().parent.parent / "netscout" / "data" / "recog"
UA = {"User-Agent": "netscout-update-recog"}

LICENSE = """Rapid7 Recog fingerprint databases (https://github.com/rapid7/recog)

Copyright (c) 2014, Rapid7, Inc.
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted
provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of conditions
   and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions
   and the following disclaimer in the documentation and/or other materials provided with the
   distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR
IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""


def get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", help="commit SHA (default: newest)")
    args = ap.parse_args()

    commit = json.loads(get(f"https://api.github.com/repos/{REPO}/commits?per_page=1"))[0] if not args.ref \
        else json.loads(get(f"https://api.github.com/repos/{REPO}/commits/{args.ref}"))
    sha, date = commit["sha"], commit["commit"]["committer"]["date"]

    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    for name in DATABASES:
        raw = get(f"https://raw.githubusercontent.com/{REPO}/{sha}/xml/{name}.xml")
        with gzip.GzipFile(OUT / f"{name}.xml.gz", "wb", compresslevel=9, mtime=0) as f:   # mtime=0: stable bytes
            f.write(raw)
        total += (OUT / f"{name}.xml.gz").stat().st_size
        print(f"{name}: {len(raw) // 1024} KiB")
    (OUT / "LICENSE.txt").write_text(LICENSE, encoding="utf-8", newline="\n")
    (OUT / "SOURCE.txt").write_text(f"{REPO} @ {sha}\ncommitted {date}\nfiles: {', '.join(DATABASES)}\n",
                                    encoding="utf-8", newline="\n")
    print(f"pinned {sha[:10]} ({date}); {total // 1024} KiB compressed -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
