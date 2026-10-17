import json
import zipfile

import pytest

from netscout import classify, devtypes, export, icons, oui
from netscout.discovery.sweep import _NBSTAT, _parse_nbstat
from netscout.model import Device, DeviceTable


def make(ip="192.168.1.50", mac=None, **kw) -> Device:
    d = DeviceTable().get(ip, mac)
    for k, v in kw.items():
        setattr(d, k, v)
    return d


# --- OUI ---------------------------------------------------------------------------------
def test_normalize_mac_variants():
    assert oui.normalize_mac("AA-BB-CC-DD-EE-FF") == "aa:bb:cc:dd:ee:ff"
    assert oui.normalize_mac("aabb.ccdd.eeff") == "aa:bb:cc:dd:ee:ff"
    assert oui.normalize_mac("nope") is None


def test_lookup_known_vendor_and_random_mac():
    assert "Raspberry Pi" in oui.lookup("2c:cf:67:31:57:fc")
    assert oui.lookup("82:17:3f:57:9d:9b") is None          # locally administered
    assert oui.is_locally_administered("82:17:3f:57:9d:9b")


# --- classification ----------------------------------------------------------------------
def test_raspberry_pi_by_oui():
    d = classify.classify(make(mac="2c:cf:67:31:57:fc"))
    assert d.device_type == "raspberry_pi" and d.confidence > .8


def test_printer_by_mdns_beats_generic_vendor():
    d = make(mac="60:e9:aa:cc:91:e2")
    d.vendor = "Hewlett Packard"
    d.services |= {"mdns:_ipp._tcp", "mdns:_printer._tcp"}
    d.open_ports |= {9100, 631}
    assert classify.classify(d).device_type == "printer"


def test_upnp_gateway_and_default_gateway():
    d = make(is_gateway=True)
    d.services.add("upnp:internetgatewaydevice")
    assert classify.classify(d).device_type == "router"


def test_ios_device_by_lockdown_port_and_random_mac():
    d = make(mac="82:17:3f:57:9d:9b")
    d.open_ports.add(62078)
    assert classify.classify(d).device_type == "phone"


def test_specific_beats_generic_iot():
    d = make()
    d.vendor = "Espressif Inc."
    d.names["dns"] = "kitchen-smartplug"
    assert classify.classify(d).device_type == "smart_plug"


def test_espressif_alone_is_iot():
    d = make()
    d.vendor = "Espressif Inc."
    assert classify.classify(d).device_type == "iot"


def test_steam_deck_hostname_is_handheld():
    d = make(hostname="steamdeck")
    assert classify.classify(d).device_type == "handheld_console"


def test_apple_model_identifier():
    d = make(model="iPad13,4")
    assert classify.classify(d).device_type == "tablet"


def test_nothing_known_is_unknown():
    assert classify.classify(make()).device_type == "unknown"


def test_every_classifier_type_exists_in_catalog_and_has_icon():
    used = set()
    for table in (classify._VENDOR, classify._NAME, classify._TEXT):
        for _, votes in table:
            used |= set(votes)
    for votes in list(classify._SERVICE.values()) + list(classify._PORT.values()):
        used |= set(votes)
    assert used <= set(devtypes.TYPES)
    assert set(devtypes.TYPES) <= set(icons._BODY)


def test_display_name_prefers_readable_over_uuid():
    d = make()
    d.names["mdns"] = "f3056376-3a26-1769-9522-18abcdef0123"
    d.names["friendly"] = "Living Room TV"
    assert d.display_name == "Living Room TV"


# --- protocol parsing --------------------------------------------------------------------
def test_nbstat_request_shape():
    assert len(_NBSTAT) == 50


def test_nbstat_response_parse():
    from netscout.discovery.sweep import _NAME_ENC
    hdr = b"\x13\x37\x84\x00\x00\x00\x00\x01\x00\x00\x00\x00" + _NAME_ENC
    rr = b"\x00\x21\x00\x01\x00\x00\x00\x00\x00\x3f"
    def ent(name, suffix, flags):
        return name.ljust(15).encode() + bytes([suffix]) + flags.to_bytes(2, "big")
    names = b"\x02" + ent("DESKTOP-1", 0, 0x0400) + ent("WORKGROUP", 0, 0x8400)
    parsed, mac = _parse_nbstat(hdr + rr + names + bytes.fromhex("102233445566") + b"\x00" * 40)
    assert parsed == {"workstation": "DESKTOP-1", "workgroup": "WORKGROUP"}
    assert mac == "10:22:33:44:55:66"


# --- exports -----------------------------------------------------------------------------
@pytest.fixture
def devices():
    a = classify.classify(make("192.168.1.2", "2c:cf:67:31:57:fc", hostname="pi,<b>"))
    b = classify.classify(make("192.168.1.10", None))
    return [a, b]


@pytest.mark.parametrize("fmt", export.FORMATS)
def test_every_format_renders(devices, fmt, tmp_path):
    p = export.write(devices, fmt, tmp_path / f"out.{fmt}", {"networks": "192.168.1.0/24"})
    assert p.stat().st_size > 100


def test_json_roundtrip(devices):
    data = json.loads(export.render(devices, "json"))
    assert data["meta"]["count"] == 2 and data["devices"][0]["type"] == "raspberry_pi"


def test_html_escapes_and_inlines_icons(devices):
    out = export.render(devices, "html")
    assert "pi,&lt;b&gt;" in out and "pi,<b>" not in out and "<svg" in out


def test_csv_header_and_md_table(devices):
    assert export.render(devices, "csv").splitlines()[0].startswith("IP,Name,Type")
    assert "| IP | Name |" in export.render(devices, "md")


def test_xlsx_has_sheets(devices, tmp_path):
    p = export.write(devices, "xlsx", tmp_path / "o.xlsx")
    with zipfile.ZipFile(p) as z:
        assert "xl/worksheets/sheet2.xml" in z.namelist()


def test_pdf_magic(devices):
    assert export.render(devices, "pdf")[:5] == b"%PDF-"


def test_format_inference():
    assert export.format_for_path("x/Report.XLSX") == "xlsx"
    assert export.format_for_path("noext") is None


# --- OS detection ------------------------------------------------------------------------
from netscout import osdetect


def os_of(**kw):
    d = make()
    d.text = kw.pop("text", [])
    d.facts.update(kw.pop("facts", {}))
    d.open_ports |= set(kw.pop("ports", []))
    for k, v in kw.items():
        setattr(d, k, v)
    osdetect.detect(d)
    return d


def test_os_ssh_banner_ubuntu():
    d = os_of(text=["SSH-2.0-OpenSSH_9.6p1 Ubuntu-3ubuntu13.5"], facts={"ttl": "64"})
    assert (d.os_hint, d.os_detail) == ("Linux", "Ubuntu") and d.os_confidence > .85


def test_os_windows_from_ttl_ports_and_netbios():
    d = os_of(ports=[135, 445, 3389], facts={"ttl": "128"})
    assert d.os_hint == "Windows" and d.os_confidence > .8


def test_os_upnp_windows_version():
    d = os_of(text=["Microsoft-Windows/10.0 UPnP/1.0 UPnP-Device-Host/1.0"])
    assert d.os_hint == "Windows" and d.os_detail == "NT 10.0"


def test_os_ios_from_lockdown_port_and_ttl_hop_decrement():
    d = os_of(ports=[62078], facts={"ttl": "62"})     # 62 = 64 minus 2 hops
    assert d.os_hint == "iOS"


def test_os_feeds_device_type():
    d = make()
    d.text = ["Linux/3.14 UPnP/1.0 MiniUPnPd/1.9"]
    d.services.add("upnp:internetgatewaydevice")
    assert classify.classify(d).device_type == "router" and d.os_hint == "Linux"
    t = make()
    t.text = ["webOS TV"]
    assert classify.classify(t).device_type == "tv"


def test_os_unknown_without_evidence():
    assert os_of().os_hint is None


def test_os_in_exports(devices):
    devices[0].text.append("SSH-2.0-OpenSSH_8.4p1 Debian-5")
    classify.classify(devices[0])
    assert "Debian" in export.render(devices, "csv")


# --- OS-specific command output parsers --------------------------------------------------
from netscout.discovery import net as netmod

WIN_ARP = """
Interface: 192.168.1.18 --- 0x12
  Internet Address      Physical Address      Type
  192.168.1.1           fc-3f-a6-55-0f-92     dynamic
  192.168.1.17          82-17-3f-57-9d-9b     dynamic
  192.168.1.255         ff-ff-ff-ff-ff-ff     static
  224.0.0.22            01-00-5e-00-00-16     static
"""
LINUX_NEIGH = """192.168.1.1 dev eth0 lladdr fc:3f:a6:55:0f:92 REACHABLE
192.168.1.77 dev eth0  FAILED
192.168.1.20 dev eth0 lladdr 2c:cf:67:31:57:fc STALE
"""


@pytest.mark.parametrize("platform_name,text,expected", [
    ("win32", WIN_ARP, {"192.168.1.1": "fc:3f:a6:55:0f:92", "192.168.1.17": "82:17:3f:57:9d:9b"}),
    ("linux", LINUX_NEIGH, {"192.168.1.1": "fc:3f:a6:55:0f:92", "192.168.1.20": "2c:cf:67:31:57:fc"}),
])
def test_read_arp_parses_both_platforms(monkeypatch, platform_name, text, expected):
    monkeypatch.setattr(netmod.sys, "platform", platform_name)
    monkeypatch.setattr(netmod, "run_cmd", lambda *a, **k: text)
    assert netmod.read_arp() == expected


def test_default_gateway_parsers(monkeypatch):
    monkeypatch.setattr(netmod.sys, "platform", "win32")
    monkeypatch.setattr(netmod, "run_cmd", lambda *a, **k:
                        "  0.0.0.0          0.0.0.0      192.168.1.1     192.168.1.18     25\n")
    assert netmod.default_gateways() == {"192.168.1.1"}
    monkeypatch.setattr(netmod.sys, "platform", "linux")
    monkeypatch.setattr(netmod, "run_cmd", lambda *a, **k: "default via 10.0.0.1 dev wlan0 proto dhcp\n")
    assert netmod.default_gateways() == {"10.0.0.1"}


def test_local_os_is_authoritative():
    d = make()
    d.text = ["local-os: linux | steamos holo"]
    osdetect.detect(d)
    assert (d.os_hint, d.os_detail) == ("Linux", "SteamOS") and d.os_confidence > .98


def test_clamped_subnet_keeps_gateway_probeable():
    import ipaddress
    from netscout.discovery.base import Iface
    i = Iface("eth0", "172.19.233.225", ipaddress.ip_network("172.19.233.0/24"),
              full_network=ipaddress.ip_network("172.19.224.0/20"), extra_hosts=["172.19.224.1"])
    assert "172.19.224.1" in i.hosts()


def test_arm64_windows_hostname_is_computer():
    # regression: Windows-on-ARM laptop whose only signals were a hostname and TTL 128
    d = make(hostname="Alex-Arm64")
    d.facts["ttl"] = "128"
    classify.classify(d)
    assert d.device_type == "computer" and d.os_hint == "Windows" and d.confidence >= .5


def test_ttl_alone_nudges_toward_computer_but_does_not_decide():
    d = make()
    d.facts["ttl"] = "128"
    classify.classify(d)
    assert d.os_detail == "TTL guess" and d.device_type in ("computer", "unknown")


def test_laptop_model_family_in_name():
    assert classify.classify(make(hostname="ASUS-Vivobook-S15")).device_type == "laptop"


def test_weak_vendor_only_os_hint_is_hidden():
    d = make()
    d.vendor = "Microsoft Corporation"
    osdetect.detect(d)
    assert d.os_hint is None


def test_local_os_detail_keeps_case():
    d = make()
    d.text = ["local-os: linux | Ubuntu 26.04 LTS (WSL)"]
    osdetect.detect(d)
    assert d.os_detail == "Ubuntu 26.04 LTS (WSL)"


def test_gaming_laptop_hostnames():
    for name in ("Alex-Helios-18", "Predator-Triton-500", "Nitro-5", "alienware-m16"):
        assert classify.classify(make(hostname=name)).device_type == "laptop", name
