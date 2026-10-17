# netscout

Local-network device scanner for consumer and SMB gear. One Python core, two front ends (CLI + PySide6 GUI),
runs on Windows, Linux and SteamOS (desktop mode). No elevation required.

## Install

    python -m venv .venv && .venv/bin/pip install -e ".[gui,dev]"      # Windows: .venv\Scripts\pip

## Use

    netscout                                  # scan, print a table
    netscout -o scan.xlsx -o scan.json        # format inferred from extension
    netscout -f md > scan.md                  # text formats can go to stdout
    netscout --list-interfaces ; netscout -i Wi-Fi --no-ports -v
    netscout-gui

Formats: json, html, md, csv, xlsx, pdf, txt (GUI: Export… button).

## How devices are identified

1. **Host discovery** - NetBIOS node-status sweep to wake the ARP cache, then read it (every live host answers ARP).
2. **MAC OUI** - bundled IEEE MA-L/MA-M/MA-S snapshot (`python tools/build_oui.py` refreshes it).
3. **Service discovery** - mDNS/DNS-SD (all service types), SSDP/UPnP (+ device description XML),
   WS-Discovery (ONVIF cameras, WSD printers), NetBIOS names.
4. **Probes** - TCP port set, HTTP title/Server, SSH/RTSP banners, Roku ECP, Google Cast, reverse DNS.
5. **Classifier** (`netscout/classify.py`) - rule tables vote `{type: weight}`; votes combine by noisy-OR;
   generic types (IoT, Computer) only win when nothing specific has >= 45% support. The GUI's detail pane and
   the XLSX "Evidence" sheet show exactly why each type was chosen.

Adding a device type: `devtypes.py` (catalog) + `icons.py` (SVG) + rules in `classify.py`. A test enforces all three agree.

## Layout

`netscout/` core is Qt-free and importable as a library (`scanner.scan()`, `export.render()`); `netscout/gui/` is the only Qt code.

## OS detection

`netscout/osdetect.py` votes an OS family (+ detail) from: ICMP TTL, SSH/HTTP/UPnP/RTSP banners, Apple model
identifiers, port signatures (3389/135 Windows, 62078 iOS, 8060 Roku, ...), NetBIOS, vendor, and - for the
scanning machine itself - the exact local OS. TTL alone is labelled "TTL guess" and only nudges the device type.
OS and device type feed each other (a Roku OS device is a streaming box; a Windows host with `arm64` in its name
is a computer). Not implemented: passive TCP/IP-stack and DHCP fingerprinting (need raw sockets), SMB dialect
probing (planned alongside the steamos-fm SMB integration).

## Linux testing

Tests run on Windows and in WSL (`Ubuntu-26.04`): `pytest` covers the `ip neigh` / `route print` / `arp -a` parsers
with real output samples. WSL2 NAT only sees its own vNAT subnet, so LAN discovery on Linux needs real hardware
(or `networkingMode=mirrored` in `.wslconfig`).

## Custom rules

Classification rules are data (`netscout/data/rules/*.toml`, packaged and strictly validated). To teach netscout
about your own gear, drop files with the **same names** in your rules folder (`netscout --check-rules` prints its
location and validates them; a bad rule is reported and skipped, never fatal):

    # <rules dir>/vendor.toml  - regex on the OUI / UPnP manufacturer, votes are device-type -> weight (0..1)
    [[rule]]
    match = 'acme widgets'
    votes = { pet_feeder = 0.9 }

    # <rules dir>/services.toml - key is "<protocol>:<service>"; replaces the packaged entry of the same key
    [services]
    "mdns:_acme._tcp" = { pet_feeder = 0.95 }

Files: `vendor`, `names` (hostnames/friendly names), `text` (banners, models, titles), `services`, `ports`, `os`.
Weights for one type combine by noisy-OR; valid types are in `netscout/devtypes.py`.

## Banner fingerprinting (Rapid7 Recog)

SSH, HTTP (Server / `<title>` / WWW-Authenticate), RTSP, SNMP and mDNS `_device-info` banners are matched against
bundled [Rapid7 Recog](https://github.com/rapid7/recog) databases (BSD-2-Clause, notice in `netscout/data/recog/`),
pinned to a commit recorded in `data/recog/SOURCE.txt`. Results (product, OS vendor/version, hardware device and
model) feed OS detection and the device-type classifier through `data/rules/recog.toml`. Refresh with
`python tools/update_recog.py`.

## SNMP and SMB probes

Both are read-only and unauthenticated, on by default, and skipped with `--no-snmp` / `--no-ports`:

- **SNMP** (`discovery/snmp.py`): one GET for sysDescr / sysObjectID / sysName / sysUpTime using only the community
  names you allow (`--snmp-community`, default `public`). The sysObjectID's IANA enterprise number names the
  vendor (`data/pen.tsv.gz`, rebuilt by `tools/build_pen.py`); sysDescr goes through the Recog SNMP fingerprints.
  A device that answers is listed as "SNMP agent (readable with the default community)" - worth knowing about.
- **SMB** (`discovery/smb.py`): SMB2 NEGOTIATE plus an anonymous NTLM NEGOTIATE; the server's NTLM challenge reports
  the real Windows version/build, computer and domain name, signing policy and boot time. No login is attempted
  and nothing is read from the host. Samba/NAS answer without a version, which is only a weak hint.

## Corrections (device memory)

Wrong guess? Fix it once and it sticks. GUI: right-click a device -> **Edit name / type / notes...** (reset any time).
CLI:

    netscout --label aa:bb:cc:dd:ee:01 --set-type camera --set-name "Porch Cam" --set-notes "front door"
    netscout --list-labels            # your corrections next to what was auto-detected (!= marks disagreements)
    netscout --forget aa:bb:cc:dd:ee:01
    netscout --suggest-rules > vendor.toml    # turn corrections into custom vendor rules (review first)

Corrections live in `labels.json` in the data dir, keyed by MAC (phones with randomized MACs keep one MAC per
network). They override the type/name with 100% confidence, the scanner's own verdict is kept beside them, and each
correction records what the scanner saw - so a disagreement is also a bug report you can act on (`--suggest-rules`
or a custom rule). `--no-labels` ignores them for one scan.

## History (presence and change tracking)

Every completed scan is recorded in a local SQLite file (`history.db` in the data dir; `--no-history` skips it,
`--forget-history` deletes it). The first scan of a network is a silent baseline; after that you get **new**,
**returned**, **moved** (same MAC, new IP) and **left** events. WiFi gear naps, so a device only counts as *left* after
missing two consecutive scans. Networks are tracked independently, and a stopped (partial) scan is never recorded.

    netscout                      # prints "history: NEW 192.168.1.51 ..." lines after the table (stderr)
    netscout --watch 10           # rescan every 10 minutes, print only what changed
    netscout --known              # every device ever seen: first/last seen, online/offline
    netscout --events 50          # recent change events

GUI: a Status column (New / Returned / Offline), remembered-but-silent devices shown dimmed ("Show offline"), and
a summary in the status bar. Exports gain a "First seen" column; JSON has a `history` object per device.
