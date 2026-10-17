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
