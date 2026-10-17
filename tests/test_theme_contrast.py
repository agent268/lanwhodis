"""The theme keeps its WCAG contrast promises. Re-measures the real Theme.qml, so a token edit that breaks
readability fails here instead of in somebody's eyes."""
import re
from pathlib import Path

import pytest

from lanwhodis import devtypes, icons

THEME = (Path(__file__).resolve().parent.parent / "lanwhodis" / "gui" / "qml" / "LanWhodis" / "Theme.qml").read_text(encoding="utf-8")


def palettes():
    out = {}
    for name, body in re.findall(r"property var _(dark|light|deck): QtObject \{(.*?)\n    \}", THEME, re.S):
        out[name] = dict(re.findall(r'readonly property color (\w+):\s+"(#[0-9a-fA-F]{6,8})"', body))
    return out


PAL = palettes()


def rgb(h):
    h = h.lstrip("#")[-6:]
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def lum(c):
    f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (f(v) for v in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    hi, lo = sorted((lum(rgb(a) if isinstance(a, str) else a), lum(rgb(b) if isinstance(b, str) else b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def tint(fg_hex, bg_hex, alpha):
    f, b = rgb(fg_hex), rgb(bg_hex)
    return tuple(x * alpha + y * (1 - alpha) for x, y in zip(f, b))


THEMES = ("dark", "light", "deck")


def test_the_three_palettes_define_the_same_tokens():
    assert set(PAL) == set(THEMES)
    assert PAL["dark"].keys() == PAL["light"].keys() == PAL["deck"].keys()


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("fg,bg", [(f, b) for f in ("text", "textDim") for b in ("bg", "surface", "dialogSurface", "sectionSurface")])
def test_text_is_readable_on_every_surface(theme, fg, bg):
    p = PAL[theme]
    assert ratio(p[fg], p[bg]) >= 4.5, f"{theme}: {fg} {p[fg]} on {bg} {p[bg]} = {ratio(p[fg], p[bg]):.2f}"


@pytest.mark.parametrize("theme", THEMES)
def test_text_on_solid_fills_is_readable(theme):
    p = PAL[theme]
    assert ratio(p["accentInk"], p["accent"]) >= 4.5
    assert ratio(p["dangerInk"], p["danger"]) >= 4.5
    assert ratio(p["text"], p["buttonSurface"]) >= 4.5
    assert ratio(p["accent"], p["bg"]) >= 3.0            # accent as icon / focus ring / link


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("tone", ["success", "warning", "danger"])
def test_status_chip_text_is_readable_on_its_own_tint(theme, tone):
    p = PAL[theme]
    chip_bg = tint(p[tone], p["surface"], 0.16)
    assert ratio(p[tone + "Text"], chip_bg) >= 4.5, f"{theme} {tone}"


@pytest.mark.parametrize("theme", THEMES)
def test_device_labels_and_glyphs_are_readable(theme):
    p = PAL[theme]
    for key in devtypes.TYPES:
        dark, light = icons.label_colors(key)
        label = light if theme == "light" else dark
        base = icons.color(key)
        assert ratio(label, p["surface"]) >= 4.5, f"{theme} {key} label {label}"                       # 15px bold text
        assert ratio(label, tint(base, p["surface"], 0.17)) >= 3.0, f"{theme} {key} glyph on tile"    # icon on its tile
        assert ratio(label, p["bg"]) >= 3.0, f"{theme} {key} sidebar icon"                              # icon on the app bg
