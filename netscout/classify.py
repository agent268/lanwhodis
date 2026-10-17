"""Weighted-evidence device classifier.

Every signal (OUI vendor, mDNS/UPnP/WS-Discovery services, open ports, names, banners)
casts votes {device_type: weight}. Votes for the same type combine with noisy-OR, so many
weak hints add up but never exceed certainty. Generic types ("iot", "computer") only win
when no specific type has reasonable support.
"""
from __future__ import annotations

import re

from . import devtypes
from .model import Device, Evidence

SPECIFIC_THRESHOLD = 0.45   # a non-generic type at/above this beats any generic type
UNKNOWN_BELOW = 0.20

Votes = dict[str, float]

# --- vendor (from OUI or UPnP manufacturer), lowercase regex -> votes ----------------------
_VENDOR: list[tuple[str, Votes]] = [
    (r"raspberry pi", {"raspberry_pi": .9}),
    (r"\bsonos\b", {"speaker": .95}),
    (r"\broku\b", {"streaming": .9}),
    (r"nintendo", {"handheld_console": .4, "game_console": .6}),
    (r"sony interactive", {"game_console": .92}),
    (r"valve corp", {"handheld_console": .5, "game_console": .3, "computer": .2}),
    (r"ayaneo|anbernic|retroid|\bayn\b|\bgpd\b|powkiddy", {"handheld_console": .7}),
    (r"espressif", {"iot": .7, "smart_plug": .15}),
    (r"tuya", {"iot": .8, "smart_plug": .2}),
    (r"ubiquiti|ubnt", {"access_point": .4, "switch": .15, "router": .15}),
    (r"tp-?link", {"router": .3, "access_point": .25, "smart_plug": .12, "extender": .1}),
    (r"netgear", {"router": .35, "access_point": .2, "extender": .15}),
    (r"\barlo\b", {"camera": .85}),
    (r"\basus(tek)?\b", {"router": .25, "computer": .25, "laptop": .15}),
    (r"linksys|tenda|mercusys|totolink|cudy|wavlink|engenius|edimax|zyxel|trendnet|d-?link",
     {"router": .35, "access_point": .25, "switch": .1}),
    (r"mikrotik|routerboard", {"router": .75}),
    (r"cisco|meraki", {"switch": .35, "router": .3, "access_point": .2}),
    (r"aruba|ruckus|cambium|aerohive|extreme networks", {"access_point": .75}),
    (r"\beero\b", {"router": .5, "access_point": .4}),
    (r"avm|fritz", {"router": .75}),
    (r"devolo", {"extender": .6}),
    (r"arcadyan|arris|technicolor|sagemcom|commscope|ubee|hitron|askey|sercomm|actiontec|calix|zte|fiberhome|zhone",
     {"gateway": .5, "router": .3}),
    (r"teltonika|peplink|cradlepoint|inseego|sierra wireless", {"router": .6}),
    (r"nest labs", {"thermostat": .5, "camera": .3, "doorbell": .15}),
    (r"google", {"speaker": .2, "streaming": .2, "hub": .1, "phone": .1}),
    (r"amazon", {"speaker": .3, "streaming": .3, "tablet": .15}),
    (r"ring (llc|inc)|^ring\b", {"doorbell": .6, "camera": .3}),
    (r"\bblink\b|wyze|reolink|hikvision|dahua|amcrest|foscam|axis comm|vivotek|hanwha|uniview|lorex|swann|"
     r"zhejiang uniview|annke|eufy|tapo|yi technology|imou|ezviz|arlo",
     {"camera": .85}),
    (r"ecobee|tado|netatmo", {"thermostat": .85}),
    (r"honeywell|emerson|resideo", {"thermostat": .4}),
    (r"chamberlain|liftmaster|myq|genie company|overhead door", {"garage_door": .8}),
    (r"rheem|a\.? ?o\.? smith|bradford white|navien|rinnai|bosch thermotechnik", {"water_heater": .6}),
    (r"whirlpool|electrolux|\bbsh\b|miele|haier|midea|ge appliances|maytag|bosch hausger",
     {"appliance": .55}),
    (r"irobot|roborock|ecovacs|dreame|neato|shark ?ninja|sharkninja", {"appliance": .8}),
    (r"\blg elec", {"tv": .35, "appliance": .25, "phone": .1}),
    (r"samsung", {"phone": .2, "tv": .25, "appliance": .15, "tablet": .1}),
    (r"petlibro|petsafe|whisker|litter-?robot|petkit|wopet|sure petcare|dogness|petwant",
     {"pet_feeder": .75}),
    (r"signify|philips lighting|lifx|nanoleaf|yeelight|\bwiz\b|innr|lutron", {"light": .6, "hub": .15}),
    (r"hubitat|smartthings|aeotec|zigbee|z-wave|sigma designs|zwave|control4|crestron|savant",
     {"hub": .55}),
    (r"belkin|wemo", {"smart_plug": .45, "router": .15}),
    (r"sonoff|itead|shelly|allterco|meross|gosund|teckin|athom|kasa", {"smart_plug": .75, "iot": .1}),
    (r"enphase|sma solar|solaredge|generac|sense labs", {"iot": .7}),
    (r"bambu|creality|prusa|elegoo", {"iot": .5, "printer": .2}),
    (r"apple", {"computer": .12, "phone": .12, "laptop": .1, "tablet": .08, "tv": .05}),
    (r"nvidia", {"streaming": .3, "computer": .25}),
    (r"intel corp|dell|lenovo|hp inc|acer|micro-star|\bmsi\b|gigabyte|asrock|clevo|framework|"
     r"compal|quanta|wistron|liteon|azurewave|chicony|realtek",
     {"computer": .3, "laptop": .15}),
    (r"vmware|virtualbox|pcs systems|xensource|parallels", {"server": .5, "computer": .2}),
    (r"xiaomi", {"phone": .25, "iot": .3}),
    (r"huawei", {"phone": .25, "router": .2}),
    (r"oneplus|oppo|vivo mobile|motorola|realme|nothing tech|tecno|infinix|fairphone|hmd", {"phone": .5}),
    (r"vizio|hisense|tcl|skyworth|toshiba (visual|digital)|panasonic|sharp|philips consumer|funai|"
     r"bang & olufsen|konka|changhong|sceptre",
     {"tv": .5}),
    (r"\bsony\b", {"tv": .3, "speaker": .1, "game_console": .1, "phone": .1}),
    (r"brother|canon|epson|lexmark|xerox|ricoh|kyocera|konica|oki data|zebra tech|dymo|seiko epson",
     {"printer": .65}),
    (r"hewlett|hp inc", {"printer": .35, "computer": .3, "laptop": .15}),
    (r"synology|qnap|asustor|terramaster|buffalo|drobo|netgear readynas|western digital|\bwd\b",
     {"nas": .75}),
    (r"polycom|yealink|grandstream|snom|avaya|mitel|fanvil|obihai|ooma|poly\b|ringcentral",
     {"voip": .8}),
    (r"denon|marantz|yamaha|bose|harman|\bjbl\b|klipsch|polk|libratone|teufel|onkyo|pioneer|"
     r"bowers|naim|bluesound|heos|wiim|linkplay|cambridge audio",
     {"speaker": .5}),
    (r"airtame|mersive|screenbeam|ezcast|measy|barco clickshare|clickshare", {"wireless_display": .85}),
    (r"brightsign|iadea|appspace|novastar|scala", {"signage": .85}),
    (r"dell emc|supermicro|super micro|inspur|ibm|oracle|fujitsu", {"server": .5}),
]

# --- services. keys: "mdns:<type>", "upnp:<deviceType>", "wsd:<type>", "ssdp:<st>" ----------
_SERVICE: dict[str, Votes] = {
    "mdns:_airplay._tcp": {"tv": .3, "streaming": .35, "speaker": .25},
    "mdns:_raop._tcp": {"speaker": .35, "streaming": .15, "computer": .1},
    "mdns:_googlecast._tcp": {"streaming": .35, "tv": .2, "speaker": .2},
    "mdns:_googlezone._tcp": {"speaker": .35},
    "mdns:_spotify-connect._tcp": {"speaker": .5},
    "mdns:_sonos._tcp": {"speaker": .95},
    "mdns:_amzn-wplay._tcp": {"streaming": .85},
    "mdns:_androidtvremote2._tcp": {"tv": .75, "streaming": .2},
    "mdns:_homekit._tcp": {"iot": .3},
    "mdns:_hap._tcp": {"iot": .3},
    "mdns:_matter._tcp": {"iot": .3, "hub": .1},
    "mdns:_matterc._udp": {"iot": .3},
    "mdns:_meshcop._udp": {"hub": .3, "router": .1},
    "mdns:_eero._tcp": {"access_point": .8, "router": .3},
    "mdns:_hue._tcp": {"hub": .9, "light": .2},
    "mdns:_esphomelib._tcp": {"iot": .85},
    "mdns:_nanoleafapi._tcp": {"light": .9},
    "mdns:_printer._tcp": {"printer": .95},
    "mdns:_ipp._tcp": {"printer": .9},
    "mdns:_ipps._tcp": {"printer": .9},
    "mdns:_pdl-datastream._tcp": {"printer": .95},
    "mdns:_scanner._tcp": {"printer": .8},
    "mdns:_uscan._tcp": {"printer": .7},
    "mdns:_rtsp._tcp": {"camera": .45},
    "mdns:_axis-video._tcp": {"camera": .95},
    "mdns:_airport._tcp": {"access_point": .9, "router": .3},
    "mdns:_smb._tcp": {"computer": .25, "nas": .25},
    "mdns:_afpovertcp._tcp": {"nas": .3, "computer": .2},
    "mdns:_nfs._tcp": {"nas": .4, "server": .2},
    "mdns:_adisk._tcp": {"nas": .6},
    "mdns:_workstation._tcp": {"computer": .35, "server": .15},
    "mdns:_ssh._tcp": {"server": .15, "computer": .1},
    "mdns:_sftp-ssh._tcp": {"server": .1},
    "mdns:_companion-link._tcp": {"phone": .3, "tablet": .2, "laptop": .2, "streaming": .15},
    "mdns:_sleep-proxy._udp": {"streaming": .3, "router": .2},
    "mdns:_daap._tcp": {"media_server": .5, "computer": .2},
    "mdns:_dacp._tcp": {"computer": .2},
    "mdns:_plexmediasvr._tcp": {"media_server": .95},
    "mdns:_jellyfin._tcp": {"media_server": .9},
    "mdns:_nvstream._tcp": {"computer": .55},
    "mdns:_steam-link._tcp": {"computer": .3},
    "mdns:_miracast._tcp": {"wireless_display": .9},
    "mdns:_home-assistant._tcp": {"hub": .9, "server": .2},
    "mdns:_http._tcp": {},
    "upnp:internetgatewaydevice": {"router": .9, "gateway": .5},
    "upnp:wandevice": {"router": .5, "gateway": .4},
    "upnp:wanconnectiondevice": {"router": .4, "gateway": .3},
    "upnp:wlanaccesspointdevice": {"access_point": .75},
    "upnp:wfadevice": {"access_point": .5, "router": .2},
    "upnp:mediaserver": {"media_server": .75, "nas": .2},
    "upnp:mediarenderer": {"speaker": .3, "tv": .3, "streaming": .25},
    "upnp:zoneplayer": {"speaker": .95},
    "upnp:printer": {"printer": .9},
    "upnp:printerbasic": {"printer": .9},
    "upnp:dial": {"tv": .35, "streaming": .35},
    "upnp:basic": {"iot": .1},
    "upnp:digitalsecuritycamera": {"camera": .9},
    "upnp:hvac": {"thermostat": .6},
    "upnp:binarylight": {"light": .8},
    "upnp:dimmablelight": {"light": .85},
    "upnp:lightingcontrols": {"light": .6},
    "upnp:controllee": {"smart_plug": .85},      # Belkin WeMo
    "upnp:bridge": {"hub": .5},
    "upnp:sensor": {"iot": .5},
    "wsd:networkvideotransmitter": {"camera": .9},
    "wsd:printdevicetype": {"printer": .9},
    "wsd:printerservice": {"printer": .9},
    "wsd:scandevice": {"printer": .6},
    "wsd:computer": {"computer": .55},
    "wsd:device": {"iot": .05},
    "netbios:nbstat": {"computer": .3},
    "local:self": {"computer": .4},
}

# --- open ports ---------------------------------------------------------------------------
_PORT: dict[int, Votes] = {
    22: {"server": .1, "computer": .05},
    23: {"router": .15, "iot": .15},
    53: {"router": .3, "server": .1},
    135: {"computer": .4},
    139: {"computer": .2, "nas": .1},
    445: {"computer": .25, "nas": .15},
    161: {"router": .1, "switch": .15, "printer": .1, "nas": .1},
    515: {"printer": .7},
    548: {"nas": .3, "computer": .15},
    554: {"camera": .6}, 8554: {"camera": .5},
    631: {"printer": .85}, 9100: {"printer": .9},
    1883: {"iot": .35, "hub": .2}, 8883: {"iot": .3},
    2049: {"nas": .35, "server": .2},
    3389: {"computer": .6},
    5000: {"nas": .35}, 5001: {"nas": .45},
    5555: {"tv": .3, "streaming": .3},
    5900: {"computer": .3, "server": .1},
    5985: {"computer": .3},
    6668: {"iot": .5, "smart_plug": .3},
    7000: {"streaming": .3, "tv": .2},
    7547: {"gateway": .7, "router": .3},
    8008: {"streaming": .3, "tv": .15, "speaker": .1}, 8009: {"streaming": .3, "tv": .15, "speaker": .1},
    8060: {"streaming": .9},
    8096: {"media_server": .85}, 8200: {"media_server": .6}, 32400: {"media_server": .9},
    8123: {"hub": .7},
    8291: {"router": .9}, 8728: {"router": .85},
    9999: {"smart_plug": .4, "iot": .2},
    37777: {"camera": .9}, 34567: {"camera": .8}, 55443: {"light": .7},
    62078: {"phone": .85, "tablet": .15},
}

# --- hostnames / friendly names (lowercase search) -----------------------------------------
_NAME: list[tuple[str, Votes]] = [
    (r"iphone", {"phone": .92}),
    (r"ipad", {"tablet": .92}),
    (r"macbook", {"laptop": .92}),
    (r"imac|mac-?mini|mac-?studio|mac-?pro", {"computer": .85}),
    (r"apple-?tv|appletv", {"streaming": .92}),
    (r"homepod", {"speaker": .95}),
    (r"galaxy-?(tab|s\d+ ?tab)|^sm-t\d", {"tablet": .8}),
    (r"galaxy|^sm-[a-z]\d", {"phone": .6}),
    (r"pixel-?\d", {"phone": .8}),
    (r"oneplus|redmi|xiaomi|poco-", {"phone": .55}),
    (r"android", {"phone": .45, "tablet": .15}),
    (r"kindle|fire-?(hd|tablet)", {"tablet": .8}),
    (r"firetv|fire-?tv|^aft[a-z]", {"streaming": .9}),
    (r"(^|[-_ .])echo|alexa", {"speaker": .75}),
    (r"google-?home|nest-?(mini|audio|hub)|home-?mini", {"speaker": .8}),
    (r"chromecast", {"streaming": .95}),
    (r"^desktop-|^pc-|-pc$|^win-|^workstation", {"computer": .6}),
    (r"laptop|notebook|thinkpad|latitude|\bxps\b|surface|^dell-|^lenovo-", {"laptop": .6}),
    (r"raspberrypi|^pi\d|-pi$|^rpi|^pi-", {"raspberry_pi": .85}),
    (r"steam-?deck", {"handheld_console": .98}),
    (r"xbox", {"game_console": .95}),
    (r"playstation|^ps[345](-|$)", {"game_console": .95}),
    (r"nintendo|^switch$|nintendoswitch", {"handheld_console": .8, "game_console": .3}),
    (r"^roku", {"streaming": .9}),
    (r"printer|^brw|^npi[0-9a-f]|^epson|^canon|laserjet|officejet|deskjet|envy-|^hp[0-9a-f]{6}", {"printer": .8}),
    (r"ipcam|^ipc-|webcam|(^|[-_ ])cam(era)?([-_ 0-9]|$)", {"camera": .65}),
    (r"doorbell", {"doorbell": .9}),
    (r"^ring-", {"doorbell": .6}),
    (r"thermostat", {"thermostat": .9}),
    (r"garage|myq", {"garage_door": .8}),
    (r"water-?heater|rheem", {"water_heater": .8}),
    (r"washer|dryer|washing|dishwasher|fridge|refrigerator|(^|[-_ ])oven|robovac|roomba|vacuum",
     {"appliance": .75}),
    (r"feeder|petlibro|petsafe", {"pet_feeder": .85}),
    (r"lg-?webos|lgwebostv|webos|\[lg\]", {"tv": .85}),
    (r"bravia|smart-?tv|samsung-?tv|\[tv\]|tizen|vizio|^tcl|(^|[-_ .])tv([-_ .0-9]|$)", {"tv": .65}),
    (r"^esp[-_]?[0-9a-f]+|esp32|esp8266|tasmota|wled|shelly|espressif", {"iot": .75}),
    (r"homeassistant|hassio", {"hub": .85, "server": .3}),
    (r"pi-?hole", {"server": .5}),
    (r"(^|[-_])hub([-_]|$)", {"hub": .5}),
    (r"smartplug|outlet|(^|[-_ ])plug|hs1[01]0|kp\d{3}", {"smart_plug": .6}),
    (r"bulb|lamp|(^|[-_ ])hue|lifx", {"light": .55}),
    (r"diskstation|synology|qnap|(^|[-_ ])nas([-_ 0-9]|$)", {"nas": .8}),
    (r"^usw|switch", {"switch": .5}),
    (r"^uap|^u6-|(^|[-_ ])ap([-_ ]?\d|$)|accesspoint|(^|[-_ ])wap([-_ ]|$)", {"access_point": .6}),
    (r"extender|repeater|^rex|wn\d{4}ex", {"extender": .7}),
    (r"router|gateway|^rt-|openwrt|dd-wrt|pfsense|opnsense|mikrotik|edgerouter|fritz\.?box|^ac\d{4}",
     {"router": .55}),
    (r"ubuntu|debian|fedora|linux|server|(^|[-_])srv|^vm-?|proxmox|esxi|docker|k8s|node\d", {"server": .45}),
    (r"phone|^moto|motorola", {"phone": .4}),
    (r"tablet|^tab[-_ 0-9]", {"tablet": .5}),
    (r"projector|miracast|screenbeam|airtame", {"wireless_display": .8}),
    (r"signage|brightsign", {"signage": .85}),
    (r"voip|sip-|yealink|polycom", {"voip": .8}),
]

# --- free text: model strings, UPnP names, HTTP <title>/Server, SSH banners ----------------
_TEXT: list[tuple[str, Votes]] = [
    (r"iphone\d+,\d+", {"phone": .98}),
    (r"ipad\d+,\d+", {"tablet": .98}),
    (r"macbook", {"laptop": .95}),
    (r"macmini|imac|macpro|macstudio", {"computer": .9}),
    (r"appletv\d", {"streaming": .98}),
    (r"audioaccessory", {"speaker": .98}),
    (r"\broku\b", {"streaming": .9}),
    (r"xbox", {"game_console": .95}),
    (r"playstation", {"game_console": .95}),
    (r"nintendo", {"handheld_console": .5, "game_console": .3}),
    (r"steam ?deck|jupiter", {"handheld_console": .9}),
    (r"chromecast", {"streaming": .95}),
    (r"nest (mini|audio|hub)|home (mini|max)|google home|lenovo ?(cd|smart (clock|display))|smart clock",
     {"speaker": .93}),
    (r"nest wifi|nest ?wifi point", {"access_point": .8, "router": .3}),
    (r"google tv|android tv|androidtv|bravia|webos|tizen|smart ?tv|vizio|hisense|\btcl\b", {"tv": .7}),
    (r"fire ?tv", {"streaming": .9}),
    (r"apple ?tv", {"streaming": .95}),
    (r"homepod", {"speaker": .95}),
    (r"echo (dot|show|studio|pop)|alexa", {"speaker": .75}),
    (r"sonos", {"speaker": .95}),
    (r"hue bridge|philips hue", {"hub": .85}),
    (r"internetgatewaydevice|wanipconnection", {"router": .9}),
    (r"hikvision|dahua|reolink|amcrest|foscam|ip ?camera|network camera|onvif|\bdvr\b|\bnvr\b|webcam",
     {"camera": .8}),
    (r"printer|laserjet|officejet|deskjet|inkjet|\bmfp\b|laserwriter|ecotank|pixma", {"printer": .9}),
    (r"synology|diskstation|qnap|readynas", {"nas": .9}),
    (r"truenas|unraid|openmediavault|freenas", {"nas": .6, "server": .3}),
    (r"plex media server|plex", {"media_server": .9}),
    (r"jellyfin|emby|minidlna|serviio|mediatomb|gerbera|universal media server|twonky",
     {"media_server": .85}),
    (r"\bkodi\b", {"media_server": .5, "computer": .2}),
    (r"mediaserver", {"media_server": .6}),
    (r"openwrt|dd-wrt|tomato|pfsense|opnsense|routeros|edgeos|mikrotik|asuswrt|fritz!?box",
     {"router": .8}),
    (r"unifi|access point|wireless-ap", {"access_point": .6}),
    (r"managed switch|poe switch|gigabit switch|smart switch|ethernet switch", {"switch": .8}),
    (r"extender|repeater", {"extender": .7}),
    (r"raspberry|raspbian|raspios", {"raspberry_pi": .8}),
    (r"home assistant", {"hub": .9}),
    (r"thermostat", {"thermostat": .9}),
    (r"doorbell", {"doorbell": .9}),
    (r"garage", {"garage_door": .6}),
    (r"water heater|waterheater", {"water_heater": .8}),
    (r"dishwasher|washer|dryer|refrigerator|robot vacuum|roomba", {"appliance": .75}),
    (r"pet feeder|petlibro|pet-feeder", {"pet_feeder": .9}),
    (r"miracast|wireless display|airtame|screenbeam|wifi display", {"wireless_display": .8}),
    (r"signage|brightsign|digital sign", {"signage": .85}),
    (r"ip phone|voip|sip phone|yealink|polycom|grandstream", {"voip": .8}),
    (r"esphome|tasmota|wled|shelly", {"iot": .75}),
    (r"vmware|esxi|proxmox|hyper-v", {"server": .5}),
    (r"dropbear", {"router": .3, "iot": .2}),
    (r"openssh", {"server": .15, "computer": .1}),
    (r"windows|microsoft-httpapi|microsoft-iis", {"computer": .3}),
]

_VENDOR_C = [(re.compile(p), v) for p, v in _VENDOR]
_NAME_C = [(re.compile(p), v) for p, v in _NAME]
_TEXT_C = [(re.compile(p), v) for p, v in _TEXT]


def _vote(ev: list[Evidence], source: str, votes: Votes, detail: str) -> None:
    for t, w in votes.items():
        ev.append(Evidence(source, t, w, detail))


def gather(d: Device) -> list[Evidence]:
    ev: list[Evidence] = []

    if d.vendor:
        v = d.vendor.lower()
        for rx, votes in _VENDOR_C:
            if rx.search(v):
                _vote(ev, "oui", votes, d.vendor)

    for key in d.services:
        votes = _SERVICE.get(key.lower())
        if votes:
            _vote(ev, key.split(":", 1)[0], votes, key)

    for p in d.open_ports:
        votes = _PORT.get(p)
        if votes:
            _vote(ev, "port", votes, f"tcp/{p}")

    names = [n for n in ([d.hostname] + list(d.names.values())) if n]
    for n in names:
        nl = n.lower()
        for rx, votes in _NAME_C:
            if rx.search(nl):
                _vote(ev, "name", votes, n)

    blobs = ([d.model] if d.model else []) + d.text
    for b in blobs:
        bl = b.lower()
        for rx, votes in _TEXT_C:
            if rx.search(bl):
                _vote(ev, "text", votes, b[:80])

    if d.is_gateway:
        _vote(ev, "gateway", {"router": .9, "gateway": .3}, "default gateway")
    if d.random_mac:
        _vote(ev, "mac", {"phone": .25, "laptop": .1, "tablet": .1}, "randomized MAC")
    return ev


def classify(d: Device) -> Device:
    d.evidence = gather(d)
    scores: dict[str, float] = {}
    for e in d.evidence:
        scores[e.device_type] = 1 - (1 - scores.get(e.device_type, 0.0)) * (1 - e.weight)

    specific = {t: s for t, s in scores.items() if not devtypes.is_generic(t)}
    best_specific = max(specific, key=specific.get, default=None)
    if best_specific and specific[best_specific] >= SPECIFIC_THRESHOLD:
        d.device_type, d.confidence = best_specific, min(specific[best_specific], .99)
    elif scores:
        # generic types are penalised slightly so a weak specific guess can still edge them out
        pick = max(scores, key=lambda t: scores[t] * (0.85 if devtypes.is_generic(t) else 1.0))
        d.device_type, d.confidence = pick, min(scores[pick], .99)
    else:
        d.device_type, d.confidence = "unknown", 0.0

    if d.confidence < UNKNOWN_BELOW:
        d.device_type = "unknown"
    return d
