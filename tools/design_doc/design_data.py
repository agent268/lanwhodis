"""Extract the design system from the real source files and measure it. Output: design_data.json."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\alex\OneDrive\Code\lanwhodis")
from lanwhodis import devtypes, icons  # noqa: E402

LW = Path(r"C:\Users\alex\OneDrive\Code\lanwhodis\lanwhodis\gui")
SFM = Path(r"C:\Users\alex\OneDrive\Code\steamos\steamos-fm\src\steamos_fm\ui\SteamosFM\Theme.qml")
OUT = Path(__file__).with_name("design_data.json")

PAL_RE = re.compile(r"property var (_dark|_light|_deck): QtObject \{(.*?)\n    \}", re.S)
TOK_RE = re.compile(r'readonly property color (\w+):\s+"(#[0-9a-fA-F]{6,8})"')


def palettes(qml: str) -> dict:
    out = {}
    for name, body in PAL_RE.findall(qml):
        out[name.strip("_")] = dict(TOK_RE.findall(body))
    return out


lw_qml = (LW / "qml" / "LanWhodis" / "Theme.qml").read_text(encoding="utf-8")
sfm_qml = SFM.read_text(encoding="utf-8")
lw, sfm = palettes(lw_qml), palettes(sfm_qml)

# ---- scale tokens (LanWhodis) ------------------------------------------------------------
scale = {}
for name, mult in re.findall(r"readonly property real (\w+):\s+unit \* ([0-9.]+)", lw_qml):
    scale[name] = float(mult)
UNIT = 20


# ---- contrast ----------------------------------------------------------------------------
def rgb(h):
    h = h.lstrip("#")
    if len(h) == 8:                      # QML #AARRGGBB
        h = h[2:]
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def lum(c):
    f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (f(v) for v in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def lighter(h, f):
    """Qt.lighter(): scale HSV value."""
    import colorsys
    hh, sat, v = colorsys.rgb_to_hsv(*rgb(h))
    r, g, b = colorsys.hsv_to_rgb(hh, sat, min(1.0, v * f))
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def blend(fg, bg, a):
    return tuple(f * a + b * (1 - a) for f, b in zip(fg, bg))


def hexs(c):
    return "#" + "".join(f"{round(v * 255):02x}" for v in c)


WHITE, BLACK = (1, 1, 1), (0, 0, 0)
checks = []
for theme, p in lw.items():
    bg, surf, sect = rgb(p["bg"]), rgb(p["surface"]), rgb(p["sectionSurface"])
    def add(label, fg, bgc, need, use):
        r = ratio(fg, bgc)
        checks.append({"theme": theme, "pair": label, "fg": hexs(fg), "bg": hexs(bgc), "ratio": round(r, 2),
                       "need": need, "ok": r >= need, "use": use})
    add("text on background", rgb(p["text"]), bg, 4.5, "body text")
    add("text on card surface", rgb(p["text"]), surf, 4.5, "device names")
    add("dim text on background", rgb(p["textDim"]), bg, 4.5, "sidebar headings, counts (12px)")
    add("dim text on card surface", rgb(p["textDim"]), surf, 4.5, "IP, vendor (12px)")
    add("dim text on section", rgb(p["textDim"]), sect, 4.5, "detail labels (12px)")
    add("accent on background", rgb(p["accent"]), bg, 3.0, "icons, focus ring, links (UI component)")
    add("accentInk on accentFill", rgb(p["accentInk"]), rgb(p["accentFill"]), 4.5, "primary button label (bold 15px)")
    add("accentInk on accentFill, hovered", rgb(p["accentInk"]), rgb(lighter(p["accentFill"], 1.04)), 4.5, "primary button label while hovered")
    add("dangerInk on dangerFill", rgb(p["dangerInk"]), rgb(p["dangerFill"]), 4.5, "danger button label")
    add("text on secondary button", rgb(p["text"]), rgb(p["buttonSurface"]), 4.5, "default button label")
    for tone in ("success", "warning", "danger"):
        chip_bg = blend(rgb(p[tone]), surf, 0.16)
        add(f"{tone} chip text", rgb(p[tone + "Text"]), chip_bg, 4.5, "status chip (12px bold)")
    # category: glyph colour on its tile, and the (separately tuned) label colour on the card
    for cat, col in icons.CATEGORY_COLOR.items():
        lab = icons.CATEGORY_LABEL_LIGHT.get(cat, col) if theme == "light" else icons.CATEGORY_LABEL_DARK.get(cat, col)
        add(f"{cat} glyph on its tile", rgb(lab), blend(rgb(col), surf, 0.17), 3.0, "icon glyph (drawn in the label colour)")
        add(f"{cat} label on card", rgb(lab), surf, 4.5, "type label (bold 15px)")

# steamos-fm's own palette, as it stands today (hard-coded white button ink is the shipped behaviour)
sfm_checks = []
for theme, p in sfm.items():
    for label, fg, bgk in (("dim text on surface", "textDim", "surface"), ("dim text on dialog", "textDim", "dialogSurface"),
                           ("dim text on section", "textDim", "sectionSurface")):
        if fg in p and bgk in p:
            r = ratio(rgb(p[fg]), rgb(p[bgk]))
            sfm_checks.append({"theme": theme, "pair": label, "fg": p[fg], "bg": p[bgk], "ratio": round(r, 2), "need": 4.5, "ok": r >= 4.5})
    if "accent" in p:
        r = ratio(WHITE, rgb(p["accent"]))
        sfm_checks.append({"theme": theme, "pair": "white on accent button", "fg": "#ffffff", "bg": p["accent"], "ratio": round(r, 2), "need": 4.5, "ok": r >= 4.5})

# ---- device type -> category/icon/colour -------------------------------------------------
types = []
for key, (label, cat, generic) in devtypes.TYPES.items():
    svg = (LW / "assets" / "icons" / f"device_{key}.svg").read_text(encoding="utf-8")
    types.append({"key": key, "label": label, "category": cat, "color": icons.color(key),
                  "svg": svg.replace('fill="#212121"', 'fill="currentColor"')})

# ---- steamos-fm lineage ------------------------------------------------------------------
lineage = {}
for theme in ("dark", "light", "deck"):
    a, b = lw[theme], sfm.get(theme, {})
    lineage[theme] = {
        "same": sorted(k for k in a if k in b and a[k].lower() == b[k].lower()),
        "changed": [{"token": k, "steamos_fm": b[k], "lanwhodis": a[k]} for k in sorted(a) if k in b and a[k].lower() != b[k].lower()],
        "new": sorted(k for k in a if k not in b),
    }
lineage["steamos_only"] = sorted(k for k in sfm.get("dark", {}) if k not in lw["dark"])

data = {"lw": lw, "sfm": sfm, "scale": scale, "unit": UNIT, "categories": icons.CATEGORY_COLOR,
        "contrast": checks, "sfm_contrast": sfm_checks, "label_light": icons.CATEGORY_LABEL_LIGHT, "label_dark": icons.CATEGORY_LABEL_DARK, "types": types, "lineage": lineage, "qml_theme": lw_qml}
OUT.write_text(json.dumps(data, indent=1), encoding="utf-8")

fails = [c for c in checks if not c["ok"]]
print(f"{len(lw)} themes, {len(types)} device types, {len(checks)} contrast checks, {len(fails)} below target")
for c in fails:
    print(f"  FAIL {c['theme']:5} {c['pair']:34} {c['fg']} on {c['bg']} = {c['ratio']} (need {c['need']})")
print("steamos-fm failing:", [(c["theme"], c["pair"], c["ratio"]) for c in sfm_checks if not c["ok"]])
print("lineage dark changed:", [(x['token'], x['steamos_fm'], x['lanwhodis']) for x in lineage['dark']['changed']])
print("new in LanWhodis:", lineage['dark']['new'], "| steamos-fm only:", lineage['steamos_only'])
print("scale:", scale)
