"""Device type catalog. Keys are stable identifiers used in exports and icon lookup."""
from __future__ import annotations

# key -> (label, category, generic)
# generic types lose ties against specific ones (an "IoT" guess shouldn't beat "doorbell").
TYPES: dict[str, tuple[str, str, bool]] = {
    "computer":         ("Computer", "Computers", True),
    "laptop":           ("Laptop", "Computers", False),
    "server":           ("Server", "Computers", False),
    "raspberry_pi":     ("Raspberry Pi", "Computers", False),
    "nas":              ("NAS / File Server", "Computers", False),
    "phone":            ("Phone", "Mobile", False),
    "tablet":           ("Tablet", "Mobile", False),
    "tv":               ("TV", "Media", False),
    "streaming":        ("Streaming Device", "Media", False),
    "media_server":     ("Media Server", "Media", False),
    "speaker":          ("Speaker", "Media", False),
    "wireless_display": ("Wireless Display", "Media", False),
    "signage":          ("Digital Signage", "Media", False),
    "game_console":     ("Game Console", "Gaming", False),
    "handheld_console": ("Handheld Console", "Gaming", False),
    "camera":           ("Camera", "Smart Home", False),
    "doorbell":         ("Doorbell", "Smart Home", False),
    "thermostat":       ("Thermostat", "Smart Home", False),
    "water_heater":     ("Water Heater", "Smart Home", False),
    "garage_door":      ("Garage Door Opener", "Smart Home", False),
    "appliance":        ("Appliance", "Smart Home", False),
    "pet_feeder":       ("Pet Feeder", "Smart Home", False),
    "smart_plug":       ("Smart Plug / Switch", "Smart Home", False),
    "light":            ("Smart Light", "Smart Home", False),
    "hub":              ("Smart Home Hub", "Smart Home", False),
    "iot":              ("IoT Device", "Smart Home", True),
    "printer":          ("Printer", "Peripherals", False),
    "voip":             ("VoIP Phone", "Peripherals", False),
    "router":           ("Router", "Network", False),
    "gateway":          ("Gateway / Modem", "Network", False),
    "switch":           ("Network Switch", "Network", False),
    "access_point":     ("Access Point", "Network", False),
    "extender":         ("Range Extender", "Network", False),
    "unknown":          ("Unknown", "Other", True),
}


def label(key: str) -> str:
    return TYPES.get(key, TYPES["unknown"])[0]


def category(key: str) -> str:
    return TYPES.get(key, TYPES["unknown"])[1]


def is_generic(key: str) -> bool:
    return TYPES.get(key, TYPES["unknown"])[2]
