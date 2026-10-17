# LanWhodis

*New phone, who dis?* - but for every gadget on your network.

Local-network device scanner for consumer and SMB gear. One Python core, two front ends (CLI + PySide6 GUI),
runs on Windows, Linux and SteamOS (desktop mode). No elevation required.

> Formerly "netscout". Your data directory is migrated automatically on first run (`%APPDATA%\netscout` ->
> `%APPDATA%\lanwhodis`, or the XDG equivalent) and the old `NETSCOUT_HOME` variable still works as an alias
> for `LANWHODIS_HOME`.

## Install

    python -m venv .venv && .venv/bin/pip install -e ".[gui,dev]"      # Windows: .venv\Scripts\pip

## Use

    lanwhodis                                  # scan, print a table
    lanwhodis -o scan.xlsx -o scan.json        # format inferred from extension
    lanwhodis -f md > scan.md                  # text formats can go to stdout
    lanwhodis --list-interfaces ; lanwhodis -i Wi-Fi --no-ports -v
    lanwhodis-gui

Formats: json, html, md, csv, xlsx, pdf, txt (GUI: the export button, or Ctrl+E).

## The GUI

`lanwhodis-gui` is a Qt Quick (QML) app in the same visual language as steamos-fm: deep navy surfaces with a blue
accent (an orange Steam Deck theme and a light theme are one click away), rounded cards, boxed sections with
letter-spaced titles, and [Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) (MIT)
recoloured per theme. Each device gets a tinted icon tile in its category colour.

- **Browse:** card grid or dense list, category sidebar with counts, instant search, New / Offline filters.
- **Detail panel:** what it is and how sure we are, quick actions (open web UI, edit, copy IP/MAC), history, every
  advertised service, and the evidence behind the verdict.
- **Keys:** arrows to move, `O` open web UI, `E` edit, `Ctrl+F` search, `F5` scan, `Ctrl+E` export,
  `Ctrl+T` theme, `Ctrl +/-/0` zoom. Everything is also clickable.
- **Layout:** `lanwhodis/gui/qml/` is the UI (components in `qml/LanWhodis/`, tokens in `Theme.qml`); all logic is in
  `gui/backend.py`, so the QML is rendering only. Icons are fetched by `tools/update_icons.py` at a pinned commit.

## How devices are identified

1. **Host discovery** - NetBIOS node-status sweep to wake the ARP cache, then read it (every live host answers ARP).
2. **MAC OUI** - bundled IEEE MA-L/MA-M/MA-S snapshot (`python tools/build_oui.py` refreshes it).
3. **Service discovery** - mDNS/DNS-SD (all service types), SSDP/UPnP (+ device description XML),
   WS-Discovery (ONVIF cameras, WSD printers), NetBIOS names.
4. **Probes** - TCP port set, HTTP title/Server, SSH/RTSP banners, Roku ECP, Google Cast, reverse DNS.
5. **Classifier** (`lanwhodis/classify.py`) - rule tables vote `{type: weight}`; votes combine by noisy-OR;
   generic types (IoT, Computer) only win when nothing specific has >= 45% support. The GUI's detail pane and
   the XLSX "Evidence" sheet show exactly why each type was chosen.

Adding a device type: `devtypes.py` (catalog) + `icons.py` (SVG) + rules in `classify.py`. A test enforces all three agree.

## Layout

`lanwhodis/` core is Qt-free and importable as a library (`scanner.scan()`, `export.render()`); `lanwhodis/gui/` is the only Qt code.

## OS detection

`lanwhodis/osdetect.py` votes an OS family (+ detail) from: ICMP TTL, SSH/HTTP/UPnP/RTSP banners, Apple model
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

Classification rules are data (`lanwhodis/data/rules/*.toml`, packaged and strictly validated). To teach lanwhodis
about your own gear, drop files with the **same names** in your rules folder (`lanwhodis --check-rules` prints its
location and validates them; a bad rule is reported and skipped, never fatal):

    # <rules dir>/vendor.toml  - regex on the OUI / UPnP manufacturer, votes are device-type -> weight (0..1)
    [[rule]]
    match = 'acme widgets'
    votes = { pet_feeder = 0.9 }

    # <rules dir>/services.toml - key is "<protocol>:<service>"; replaces the packaged entry of the same key
    [services]
    "mdns:_acme._tcp" = { pet_feeder = 0.95 }

Files: `vendor`, `names` (hostnames/friendly names), `text` (banners, models, titles), `services`, `ports`, `os`.
Weights for one type combine by noisy-OR; valid types are in `lanwhodis/devtypes.py`.

## Banner fingerprinting (Rapid7 Recog)

SSH, HTTP (Server / `<title>` / WWW-Authenticate), RTSP, SNMP and mDNS `_device-info` banners are matched against
bundled [Rapid7 Recog](https://github.com/rapid7/recog) databases (BSD-2-Clause, notice in `lanwhodis/data/recog/`),
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

Wrong guess? Fix it once and it sticks. GUI: select a device and press **E** (or click **Edit**) to set its name, type
and notes; reset any time.
CLI:

    lanwhodis --label aa:bb:cc:dd:ee:01 --set-type camera --set-name "Porch Cam" --set-notes "front door"
    lanwhodis --list-labels            # your corrections next to what was auto-detected (!= marks disagreements)
    lanwhodis --forget aa:bb:cc:dd:ee:01
    lanwhodis --suggest-rules > vendor.toml    # turn corrections into custom vendor rules (review first)

Corrections live in `labels.json` in the data dir, keyed by MAC (phones with randomized MACs keep one MAC per
network). They override the type/name with 100% confidence, the scanner's own verdict is kept beside them, and each
correction records what the scanner saw - so a disagreement is also a bug report you can act on (`--suggest-rules`
or a custom rule). `--no-labels` ignores them for one scan.

## History (presence and change tracking)

Every completed scan is recorded in a local SQLite file (`history.db` in the data dir; `--no-history` skips it,
`--forget-history` deletes it). The first scan of a network is a silent baseline; after that you get **new**,
**returned**, **moved** (same MAC, new IP) and **left** events. WiFi gear naps, so a device only counts as *left* after
missing two consecutive scans. Networks are tracked independently, and a stopped (partial) scan is never recorded.

    lanwhodis                      # prints "history: NEW 192.168.1.51 ..." lines after the table (stderr)
    lanwhodis --watch 10           # rescan every 10 minutes, print only what changed
    lanwhodis --known              # every device ever seen: first/last seen, online/offline
    lanwhodis --events 50          # recent change events

GUI: NEW / BACK / OFFLINE badges on the cards, a "New or back" and "Offline" filter in the sidebar, remembered-but-silent
devices shown dimmed (toggle "Show offline"), and
a summary in the status bar. Exports gain a "First seen" column; JSON has a `history` object per device.

## Design language

The visual system (tokens for the dark, light and Steam Deck themes, component specs, a contrast audit) is written up in
[`docs/DESIGN_LANGUAGE.md`](docs/DESIGN_LANGUAGE.md); a ready-to-paste prompt for reusing it in another project is in
[`docs/design-language-prompt.txt`](docs/design-language-prompt.txt). A test keeps the doc in step with `Theme.qml`.
