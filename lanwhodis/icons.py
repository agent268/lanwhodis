"""Device-type pictograms as inline SVG (24x24, stroked). Qt-free: the GUI rasterises these
with QtSvg and the HTML exporter inlines them."""
from __future__ import annotations

from . import devtypes

# Body markup only; wrapped by svg() with stroke styling.
_BODY: dict[str, str] = {
    "computer": '<rect x="3" y="4" width="18" height="12" rx="1.5"/><path d="M8 20h8M12 16v4"/>',
    "laptop": '<rect x="5" y="5" width="14" height="10" rx="1.5"/><path d="M2.5 19h19l-1.5-4H4z"/>',
    "server": '<rect x="3" y="3" width="18" height="7" rx="1.5"/><rect x="3" y="14" width="18" height="7" rx="1.5"/>'
              '<path d="M7 6.5h.01M7 17.5h.01M11 6.5h6M11 17.5h6"/>',
    "raspberry_pi": '<rect x="2" y="6" width="20" height="13" rx="2"/><rect x="5" y="9" width="5" height="5" rx=".5"/>'
                    '<path d="M13 9h5M13 12h3M13 15.5h5M5 17h.01"/>',
    "nas": '<rect x="3" y="3" width="18" height="8" rx="1.5"/><rect x="3" y="13" width="18" height="8" rx="1.5"/>'
           '<circle cx="7" cy="7" r="1"/><circle cx="7" cy="17" r="1"/><path d="M12 7h6M12 17h6"/>',
    "phone": '<rect x="7" y="2" width="10" height="20" rx="2.5"/><path d="M11 18.5h2"/>',
    "tablet": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M11 18h2"/>',
    "tv": '<rect x="2" y="5" width="20" height="13" rx="1.5"/><path d="M8 21h8"/>',
    "streaming": '<rect x="3" y="7" width="18" height="10" rx="2.5"/><path d="M10.5 9.5v5l4-2.5z"/>',
    "media_server": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M3 15h18M7 4v16M17 4v16"/>',
    "speaker": '<rect x="6" y="2" width="12" height="20" rx="2.5"/><circle cx="12" cy="15" r="3.5"/><circle cx="12" cy="7" r="1.2"/>',
    "wireless_display": '<path d="M2 8V6a2 2 0 012-2h16a2 2 0 012 2v12a2 2 0 01-2 2h-6"/><path d="M2 12a9 9 0 019 9M2 16a5 5 0 015 5"/><path d="M2 20h.01"/>',
    "signage": '<rect x="6" y="2" width="12" height="16" rx="1.5"/><path d="M9 22h6M12 18v4"/>',
    "game_console": '<rect x="2" y="7" width="20" height="11" rx="5.5"/><path d="M7 10.5v4M5 12.5h4"/><circle cx="15.5" cy="11.5" r=".8"/><circle cx="18" cy="13.5" r=".8"/>',
    "handheld_console": '<rect x="2" y="6" width="20" height="12" rx="3.5"/><rect x="8" y="8.5" width="8" height="7" rx="1"/><path d="M4.5 12h2M5.5 11v2"/><circle cx="19" cy="12" r=".8"/>',
    "camera": '<rect x="2" y="7" width="14" height="10" rx="2"/><path d="M16 11l6-3.5v9L16 13z"/>',
    "doorbell": '<rect x="7" y="2" width="10" height="20" rx="3"/><circle cx="12" cy="7.5" r="1.3"/><circle cx="12" cy="15.5" r="2.5"/>',
    "thermostat": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><path d="M12 3v2.5"/>',
    "water_heater": '<rect x="6" y="2" width="12" height="20" rx="4"/><path d="M12 8c-2 3-3 4.5-3 6a3 3 0 006 0c0-1.5-1-3-3-6z"/>',
    "garage_door": '<path d="M3 21V9l9-6 9 6v12"/><path d="M7 21v-9h10v9M7 15h10M7 18h10"/>',
    "appliance": '<rect x="4" y="2" width="16" height="20" rx="2"/><circle cx="12" cy="14" r="5"/><circle cx="12" cy="14" r="2"/><path d="M7.5 5.5h.01M10.5 5.5h.01"/>',
    "pet_feeder": '<path d="M4 13h16a8 8 0 01-16 0z"/><path d="M8 9h.01M12 7h.01M16 9h.01M10 10.5h.01M14 10.5h.01"/>',
    "smart_plug": '<rect x="5" y="4" width="14" height="16" rx="3"/><path d="M10 9v2M14 9v2M10 15h4"/>',
    "light": '<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 00-3.5 10.9c.5.4.5 1.1.5 1.6v.5h6v-.5c0-.5 0-1.2.5-1.6A6 6 0 0012 3z"/>',
    "hub": '<path d="M12 2l8.5 5v10L12 22l-8.5-5V7z"/><circle cx="12" cy="12" r="2.5"/>',
    "iot": '<rect x="7" y="7" width="10" height="10" rx="1.5"/><path d="M10 3v4M14 3v4M10 17v4M14 17v4M3 10h4M3 14h4M17 10h4M17 14h4"/>',
    "printer": '<path d="M7 8V3h10v5"/><rect x="3" y="8" width="18" height="9" rx="2"/><rect x="7" y="14" width="10" height="7"/>',
    "voip": '<rect x="3" y="10" width="18" height="10" rx="2"/><path d="M5 10c0-3 3-5 7-5s7 2 7 5"/><path d="M8 14h.01M12 14h.01M16 14h.01M8 17h.01M12 17h.01M16 17h.01"/>',
    "router": '<rect x="3" y="13" width="18" height="7" rx="2"/><path d="M7 16.5h.01M10.5 16.5h.01M7 13V6M17 13V6"/>',
    "gateway": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 010 18M12 3a14 14 0 000 18"/>',
    "switch": '<rect x="2" y="8" width="20" height="9" rx="2"/><path d="M6 11.5v2M9.5 11.5v2M13 11.5v2M16.5 11.5v2"/>',
    "access_point": '<path d="M5 11.5a10 10 0 0114 0M8.5 15a5 5 0 017 0"/><path d="M12 19h.01"/><path d="M4 21h16"/>',
    "extender": '<path d="M6 8.5a8 8 0 0112 0M9 12a4 4 0 016 0"/><rect x="8" y="15" width="8" height="6" rx="1.5"/><path d="M12 12h.01"/>',
    "unknown": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.2a2.6 2.6 0 115 .3c0 1.6-2.5 2-2.5 3.6M12 16.8h.01"/>',
}

# Accent per category (mid-tone: readable on light and dark backgrounds)
CATEGORY_COLOR = {
    "Computers": "#4C8DFF", "Mobile": "#B36BFF", "Media": "#FF7A59", "Gaming": "#2EC4A0",
    "Smart Home": "#F2B01E", "Peripherals": "#6E8BA8", "Network": "#3FB6E8", "Other": "#8A94A3",
}


# Category colours are right for icons and tiles (3:1) but several fail as 15 px bold label TEXT (4.5:1), most
# of all on the light theme. Same hues, nudged until they reach 4.5:1 on that theme's card surface; a test
# re-measures them against the QML theme. Dark and Deck share a surface, so they share these.
CATEGORY_LABEL_LIGHT = {"Computers": "#3e72cf", "Mobile": "#9358d1", "Media": "#b85840", "Gaming": "#1f836b",
                        "Smart Home": "#966d13", "Peripherals": "#5f7890", "Network": "#2b7c9e", "Other": "#6d7581"}
CATEGORY_LABEL_DARK = {"Peripherals": "#728eab"}          # every other category colour is already readable


def label_colors(device_type: str) -> tuple[str, str]:
    """(dark/deck, light) text colours for a device type's label."""
    cat = devtypes.category(device_type)
    base = CATEGORY_COLOR.get(cat, CATEGORY_COLOR["Other"])
    return CATEGORY_LABEL_DARK.get(cat, base), CATEGORY_LABEL_LIGHT.get(cat, base)


def color(device_type: str) -> str:
    return CATEGORY_COLOR.get(devtypes.category(device_type), CATEGORY_COLOR["Other"])


def svg(device_type: str, size: int = 24, stroke: str | None = None) -> str:
    body = _BODY.get(device_type, _BODY["unknown"])
    stroke = stroke or color(device_type)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'fill="none" stroke="{stroke}" stroke-width="1.7" stroke-linecap="round" '
            f'stroke-linejoin="round">{body}</svg>')
