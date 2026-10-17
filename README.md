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
