"""Fill design_template.html from design_data.json -> design_language.html (+ the Markdown/prompt files)."""
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
D = json.loads((HERE / "design_data.json").read_text(encoding="utf-8"))
SHOTS = json.loads((HERE / "shots.json").read_text(encoding="utf-8"))
ICON_DIR = Path(r"C:\Users\alex\OneDrive\Code\lanwhodis\lanwhodis\gui\assets\icons")
LW, SFM, U = D["lw"], D["sfm"], D["unit"]
E = html.escape

ROLES = {
    "bg": "App background, behind everything", "surface": "Cards, the detail panel, the header",
    "surfaceAlt": "Hover fill for cards", "accent": "Selection, focus, primary actions, links",
    "accentDim": "Muted accent (defined for pressed states, used sparingly)", "selected": "Fill of the selected card",
    "text": "Primary text and chrome icons", "textDim": "Secondary text, labels, counts, IPs",
    "divider": "Hairlines between regions", "dialogSurface": "Dialogs, menus, tooltips, toasts",
    "dialogBorder": "Their 1 px edge", "scrim": "Dims the app behind a dialog",
    "sectionSurface": "Boxed sections in the detail panel", "sectionBorder": "Their edge; also input borders",
    "buttonSurface": "Default (secondary) button fill", "buttonBorder": "Its edge",
    "inputSurface": "Text inputs, search, segmented control", "accentFill": "Solid primary-button fill (deeper than accent so white ink passes)", "dangerFill": "Solid danger-button fill",
    "accentInk": "Label color on accentFill and dangerFill (white)", "dangerInk": "Label color on dangerFill",
    "success": "Status only: NEW and BACK chips, good results",
    "warning": "Status only: caution, medium confidence", "danger": "Status only: destructive actions, low confidence",
    "successText": "Status chip text (tuned to pass 4.5:1 on its own tint)", "warningText": "Warning chip text", "dangerText": "Danger chip text",
}
ORDER = list(ROLES)


def icon_svg(name: str, size: int) -> str:
    svg = (ICON_DIR / f"{name}.svg").read_text(encoding="utf-8").replace('fill="#212121"', 'fill="currentColor"')
    return re.sub(r'width="\d+" height="\d+"', f'width="{size}" height="{size}"', svg, count=1)


def fill_icons(s: str) -> str:
    return re.sub(r"\{\{I:(\w+):(\d+)\}\}", lambda m: icon_svg(m.group(1), int(m.group(2))), s)


def rgb_hex(h: str) -> str:
    return "#" + h.lstrip("#")[-6:]


def sw(hexv: str, label: str | None = None) -> str:
    c = rgb_hex(hexv)
    shown = label or (hexv if len(hexv.lstrip("#")) == 6 else hexv + " (AARRGGBB)")
    return f'<button type="button" class="sw" data-hex="{hexv}" title="Copy {E(hexv)}"><i style="background:{c}"></i><span>{E(shown)}</span></button>'


# ---- specimen theme variables ---------------------------------------------------------------
sp_css = []
for name, pal in (("dark", LW["dark"]), ("light", LW["light"]), ("deck", LW["deck"])):
    v = {"bg": "bg", "surface": "surface", "surface-alt": "surfaceAlt", "accent": "accent", "selected": "selected",
         "text": "text", "dim": "textDim", "divider": "divider", "dialog": "dialogSurface",
         "dialog-border": "dialogBorder", "section": "sectionSurface", "section-border": "sectionBorder",
         "button": "buttonSurface", "button-border": "buttonBorder", "input": "inputSurface",
         "success": "success", "warning": "warning", "danger": "danger",
         "accent-fill": "accentFill", "danger-fill": "dangerFill", "ink": "accentInk"}
    body = ";".join(f"--sp-{k}:{rgb_hex(pal[t])}" for k, t in v.items())
    sp_css.append(f'.sp[data-sp="{name}"]{{{body}}}')

# ---- colour table -----------------------------------------------------------------------------
rows = []
for tok in ORDER:
    cells = "".join(f"<td>{sw(LW[t][tok])}</td>" for t in ("dark", "light", "deck"))
    rows.append(f"<tr><td>{tok}</td><td>{E(ROLES[tok])}</td>{cells}</tr>")
color_table = "".join(rows)

cats = "".join(
    f'<div class="cat"><span class="tile" style="--c:{c};--s:40px">{icon_svg(icon, 22)}</span>'
    f'<div><b>{E(n)}</b><small>{c}</small></div></div>'
    for n, c, icon in (("Computers", D["categories"]["Computers"], "device_computer"),
                       ("Mobile", D["categories"]["Mobile"], "device_phone"),
                       ("Media", D["categories"]["Media"], "device_tv"),
                       ("Gaming", D["categories"]["Gaming"], "device_game_console"),
                       ("Smart Home", D["categories"]["Smart Home"], "ui_home"),
                       ("Peripherals", D["categories"]["Peripherals"], "device_printer"),
                       ("Network", D["categories"]["Network"], "device_router"),
                       ("Other", D["categories"]["Other"], "device_unknown")))

# ---- scale --------------------------------------------------------------------------------------
USE = {"fontSizeSm": "Section titles, chips, IP addresses, counts, hint bar", "fontSize": "Body text, buttons, values",
       "fontSizeLg": "Device names on cards, chrome icon size", "fontSizeXl": "Dialog titles, empty-state headlines",
       "rowHeight": "Reference height of a row or control"}
scale_rows = []
for tok in ("fontSizeSm", "fontSize", "fontSizeLg", "fontSizeXl", "rowHeight"):
    m = D["scale"][tok]
    px = m * U
    sample = (f'<span class="sample" style="font-size:{px:g}px;font-weight:700">Hue Bridge</span>' if tok.startswith("font")
              else f'<span style="display:inline-block;height:{px:g}px;width:90px;border-radius:8px;background:color-mix(in srgb,var(--accent) 20%,transparent);border:1px solid var(--accent)"></span>')
    scale_rows.append(f'<tr class="scale-row"><td>{tok}</td><td class="num">{m:g}</td><td class="num">{px:g}</td><td>{USE[tok]}</td><td>{sample}</td></tr>')

# ---- device-type grid ------------------------------------------------------------------------------
tg = []
for t in D["types"]:
    tg.append(f'<div class="icon-cell"><span class="tile" style="--c:{t["color"]};--s:56px">{icon_svg("device_" + t["key"], 30)}</span>'
              f'<small><b style="color:var(--text);font-weight:600">{E(t["label"])}</b><br>{E(t["category"])}</small></div>')
type_grid = "".join(tg)


# ---- specimen cards ------------------------------------------------------------------------------------
def card(cls, tile_color, icon, name, typ, ip, vendor, chip=""):
    return (f'<div class="c-card {cls}" style="--c:{tile_color}">'
            f'<span class="tile" style="--c:{tile_color};--s:62px;{"opacity:.5;" if cls == "offline" else ""}">{icon_svg(icon, 33)}</span>'
            f'<div><div class="nm">{E(name)}</div><div class="ty">{E(typ)}</div><div class="ip">{E(ip)}</div></div>'
            f'<div class="foot"><span>{E(vendor)}</span>{chip}</div></div>')


new_chip = '<span class="c-chip" style="--t:var(--sp-success)">NEW</span>'
off_chip = '<span class="c-chip" style="--t:var(--sp-dim)">OFFLINE</span>'
cards = (card("", D["categories"]["Network"], "device_router", "eero", "Router", "192.168.1.1", "eero inc.")
         + card("hover", D["categories"]["Computers"], "device_laptop", "Alex-Helios-18", "Laptop", "192.168.1.18", "Intel Corporate")
         + card("selected", D["categories"]["Smart Home"], "device_hub", "Hue Bridge", "Smart Home Hub", "192.168.1.122", "Philips Lighting BV", new_chip)
         + card("offline", D["categories"]["Media"], "device_speaker", "Kitchen Sonos", "Speaker", "192.168.1.231", "Sonos, Inc.", off_chip))

SPECS = [
    ("Button", [("Height", "2.1u · 42 px (compact 1.7u · 34 px)"), ("Padding", "0.75u each side · 15 px"), ("Icon", "1.1 × fontSizeLg · 21 px, 9 px gap"),
                ("Radius", "radius · 10 px, border 1 px"), ("Variants", "default · primary (accent) · danger · ghost"),
                ("Label", "fontSize; bold on primary and danger"),
                ("States", "hover: fill × 1.14 lighter · press: × 1.18 darker · focus: text-color border · disabled: 40%")]),
    ("Icon button", [("Size", "2.1u · 42 px, glyph 55%"), ("Radius", "radius · 10 px"), ("Active", "accent 22% fill, accent glyph"),
                     ("Hover / press", "text color overlay 10% / 16%"), ("Tooltip", "dialogSurface, 1 px dialogBorder, fontSizeSm, below the button")]),
    ("Chip", [("Height", "1.3u · 26 px, fully rounded"), ("Padding", "0.45u each side"), ("Text", "fontSizeSm · 12.4 px, bold"),
              ("Fill / border", "tone at 16% / 35%"), ("Tones", "neutral (dim) · accent · success · warning · danger · custom")]),
    ("Icon tile", [("Sizes", "2.1u row · 3.1u card · 3u dialog · 4.4u detail · 5.2u empty state"), ("Radius", "28% of size"),
                   ("Fill / border", "category color at 17% / 38% (offline: 8% / 15%)"), ("Glyph", "54% of the tile, full category color (offline: 45% opacity)")]),
    ("Device card", [("Cell", "min width 14u · 280 px, height 6.4u · 128 px, 0.3u · 6 px inset"), ("Radius / padding", "radiusLg · 16 px / 0.8u · 16 px"),
                     ("Name", "fontSizeLg bold · type label fontSize bold in category color · IP fontSizeSm monospace dim"),
                     ("Footer", "vendor (or OS) in dim fontSizeSm, status chip on the right"),
                     ("States", "hover: surfaceAlt + border in category color 55% · selected: selected fill, 2 px accent border · press: scale 98.5%")]),
    ("List row", [("Height", "2.9u · 58 px, tile 2.1u"), ("Columns", "name 30% · type 16% · address 14% · vendor 22% · OS 18%"),
                  ("Zebra", "odd rows surface at 50%; selected row uses selected + 1 px accent border"), ("Header", "uppercase, bold, letter-spaced fontSizeSm")]),
    ("Sidebar item", [("Height", "2.0u · 40 px, radius 10 px"), ("Icon", "1.15 × fontSizeLg, category color (accent when selected)"),
                      ("Count", "fontSizeSm dim, right aligned"), ("Selected", "accent 20% fill, 0.18u · 4 px accent marker, bold label"),
                      ("Compact", "icon only, centered, in a 3.6u · 72 px column")]),
    ("Boxed section", [("Surface", "sectionSurface, 1 px sectionBorder, radius 10 px"), ("Padding", "1.3 × pad · 13 px sides, pad · 10 px top"),
                       ("Title", "fontSizeSm bold uppercase, letter-spacing 1.6 px, dim"), ("Rows", "key 34% dim · value 64% text, both fontSizeSm; values are selectable")]),
    ("Search field", [("Height", "2.1u · 42 px, fully rounded"), ("Fill / border", "inputSurface / sectionBorder; border becomes accent on focus"),
                      ("Parts", "leading search icon, text, clear button when not empty; Escape clears and leaves")]),
    ("Dialog", [("Width", "min(38u · 760 px, window − 3u)"), ("Surface", "dialogSurface, 1 px dialogBorder, radiusLg"), ("Padding", "1.1u · 22 px"),
                ("Scrim", "scrim token over the whole window; clicking it closes the dialog"), ("Footer", "ghost Cancel, primary Save, optional Reset on the left")]),
    ("Hint bar", [("Height", "1.9u · 38 px, top hairline"), ("Message", "status text, dim, left"), ("Key caps", "1.2u · 24 px high, radius 5 px, text at 8% fill and 22% border, bold 11.4 px")]),
    ("Toast", [("Surface", "dialogSurface + dialogBorder, radius 10 px"), ("Position", "centered, 3.2u · 64 px above the bottom edge"), ("Timing", "fade 160 ms, hold 2.6 s")]),
]
spec_cards = "".join(
    f'<div class="spec-card"><h3>{E(t)}</h3><table><tbody>' + "".join(f"<tr><td>{E(k)}</td><td>{E(v)}</td></tr>" for k, v in rs) + "</tbody></table></div>"
    for t, rs in SPECS)

# ---- contrast ----------------------------------------------------------------------------------------------
checks = D["contrast"]
THEME = {"dark": "Dark", "light": "Light", "deck": "Deck"}
REAL = list(checks)
fails = [c for c in REAL if not c["ok"]]
fix = next(c for c in checks if c["theme"] == "dark" and c["pair"] == "accentInk on accentFill")


def pair_html(c):
    return (f'<span class="pair"><i style="background:{c["bg"]};color:{c["fg"]}">Aa</i><span class="mono" style="font-size:12px">{c["fg"]} on {c["bg"]}</span></span>')


def crow(c, with_result=False):
    res = (f'<td class="{"ok" if c["ok"] else "fail"}">{"pass" if c["ok"] else "below target"}</td>' if with_result
           else f'<td>{E(c["use"])}</td>')
    return (f'<tr><td>{THEME[c["theme"]]}</td><td>{E(c["pair"])}</td><td>{pair_html(c)}</td>'
            f'<td class="num {"fail" if not c["ok"] else ""}">{c["ratio"]}</td><td class="num">{c["need"]}</td>{res}</tr>')


sfm_fail_rows = "".join(
    f'<tr><td>{THEME[c["theme"]]}</td><td>{E(c["pair"])}</td><td>{pair_html(c)}</td><td class="num fail">{c["ratio"]}</td><td class="num">{c["need"]}</td><td class="fail">below target</td></tr>'
    for c in D["sfm_contrast"] if not c["ok"])
by_theme = {t: [c for c in REAL if c["theme"] == t] for t in ("dark", "light", "deck")}
summary = (f'<div class="stat"><b>{len(REAL) - len(fails)} / {len(REAL)}</b><span>measured pairs meet their target</span></div>'
           + "".join(f'<div class="stat"><b>{sum(c["ok"] for c in by_theme[t])} / {len(by_theme[t])}</b><span>{THEME[t]} theme</span></div>'
                     for t in ("dark", "light", "deck")))
contrast_fails = "".join(crow(c) for c in fails)
contrast_all = "".join(crow(c, True) for c in checks)

# ---- css vars --------------------------------------------------------------------------------------------------
kebab = lambda s: re.sub(r"([A-Z])", lambda m: "-" + m.group(1).lower(), s)


def css_block(sel, pal):
    return sel + " {\n" + "\n".join(f"  --dw-{kebab(t)}: {pal[t]};" for t in ORDER) + "\n}"


on_accent_dark, on_accent_light = "#0e141b", "#ffffff"
css = ("/* Deckwork design tokens. Dark is the default; light and Steam Deck override it.\n"
       "   Solid buttons use --dw-accent-fill / --dw-danger-fill with --dw-accent-ink / --dw-danger-ink. */\n"
       ":root {\n  --dw-unit: 20px;            /* multiply by the user's zoom */\n"
       + "".join(f"  --dw-{kebab(k)}: calc(var(--dw-unit) * {v:g});\n" for k, v in D["scale"].items())
       + "  --dw-font: \"Segoe UI\", system-ui, \"DejaVu Sans\", sans-serif;\n  --dw-mono: \"Cascadia Mono\", Consolas, \"DejaVu Sans Mono\", monospace;\n}\n"
       + css_block(':root,\n:root[data-theme="dark"]', LW["dark"])
       + "\n" + css_block(':root[data-theme="light"]', LW["light"])
       + "\n" + css_block(':root[data-theme="deck"]', LW["deck"]))
css = css.replace("#a6040a0d", "rgba(4, 10, 13, 0.65)").replace("#66141e2d", "rgba(20, 30, 45, 0.40)")  # QML #AARRGGBB -> CSS

# ---- lineage ----------------------------------------------------------------------------------------------------------
WHY = {"textDim": "Lighter, for contrast on cards at 12 px", "sectionSurface": "Darker, so a section sits between the card and the input",
       "sectionBorder": "Softer edge to match the darker section", "scrim": "Slightly stronger dim behind dialogs"}
lin_rows = []
for theme in ("dark", "light", "deck"):
    for ch in D["lineage"][theme]["changed"]:
        lin_rows.append(f'<tr><td><code>{ch["token"]}</code> <span class="dim">({THEME[theme].lower()})</span></td><td>{sw(ch["steamos_fm"])}</td><td>{sw(ch["lanwhodis"])}</td><td>{WHY.get(ch["token"], "")}</td></tr>')
lineage = "".join(lin_rows)

# ---- the reusable prompt ----------------------------------------------------------------------------------------------
tok_lines = []
for tok in ORDER:
    tok_lines.append(f"{tok}: dark {LW['dark'][tok]} | light {LW['light'][tok]} | deck {LW['deck'][tok]}")
cat_lines = ", ".join(f"{n} {c}" for n, c in D["categories"].items())
scale_lines = "; ".join(f"{k} = {v:g}u ({v * U:g}px)" for k, v in D["scale"].items())
PROMPT = f"""You are helping me build UI in the "Deckwork" design language, the shared language of steamos-fm and LanWhodis. Follow it closely and ask before you deviate.

CHARACTER
Deep navy surfaces, ONE blue accent, rounded cards, icon tiles tinted by category, boxed sections with small uppercase letter-spaced titles. Calm, dense, friendly to a mouse and a game controller. No drop shadows. No gradients. No emoji as icons.

TOKENS (use the names in code; never hard-code hex inside a component)
Colors are #RRGGBB, except scrim which is #AARRGGBB.
{chr(10).join(tok_lines)}
Solid buttons use accentFill / dangerFill with accentInk / dangerInk (white) labels; the bright accent is for icons, focus rings, links and selection.
Category colors (device kinds, never state): {cat_lines}.

SCALE (everything is a multiple of one unit; unit = 20px x user zoom)
{scale_lines}.
Fonts: the platform UI font (Segoe UI / system-ui / DejaVu Sans). Monospace only for IPs, MACs and literals. Weights: regular and bold only.
Section titles: uppercase, bold, fontSizeSm, letter-spacing 0.08u, textDim.

SHAPE AND DEPTH
Radius: 0.5u controls and sections, 0.8u cards and dialogs, pills fully rounded, icon tiles 28% of their size. Borders are always 1px (selected card: 2px accent). Depth comes only from stepping surface colors (bg -> surface -> surfaceAlt / dialogSurface) plus a hairline border. Every layer must be a clearly visible step lighter than the one below it.

RECIPES
- Icon tile: rounded square, fill = category color at 17%, border = 38%, glyph at 54% of the tile in the full category color. Offline: 8% / 15%, glyph at 45% opacity.
- Chip: height 1.3u, pill, fontSizeSm bold, text = tone, fill 16%, border 35%. Tones: neutral(textDim), accent, success, warning, danger.
- Button: height 2.1u, radius 0.5u, 1px border, optional 1.1 x fontSizeLg icon. Default = buttonSurface + buttonBorder. Primary = accentFill with accentInk label, bold. Danger = dangerFill with dangerInk label, bold. Ghost = transparent, no border. Hover lighter (x1.14; only x1.04 on primary and danger so white ink stays above 4.5:1), press darker (x1.18), disabled 40% opacity, keyboard focus is a 2px accent ring just outside the control.
- Device card: radius 0.8u, surface fill, 1px divider; tile left, then name (fontSizeLg bold), type (fontSize bold, category color), IP (fontSizeSm mono, textDim); footer: vendor + status chip. Hover: surfaceAlt fill, border = category color at 55%. Selected: selected fill + 2px accent border.
- Sidebar item: height 2.0u, selected = accent at 20% fill + 4px accent marker + bold; counts in textDim.
- Boxed section: sectionSurface, 1px sectionBorder, radius 0.5u, uppercase title, key/value rows (key 34% textDim, value text).
- Inputs: height 2.1u, inputSurface fill, sectionBorder border, accent border on focus; search is a pill with a leading icon.
- Dialog: dialogSurface, 1px dialogBorder, radius 0.8u, scrim behind it, Escape or scrim click closes, primary action on the right.
- Hint bar: 1.9u footer; status text left, key caps right (1.2u high, 5px radius, text at 8% fill and 22% border).
- Empty state: centered 5.2u tile with a soft pulsing halo, headline fontSizeXl bold, one sentence in textDim, one primary button.
Icons: Fluent UI System Icons (MIT), filled variant, recolored at draw time with the theme color.

BEHAVIOR
Color transitions 90-110ms; card press scales to 98.5% over 80ms; toast fades 160ms and holds 2.6s. Motion never changes layout. Keyboard: arrows move through lists, plain-letter shortcuts are ignored while a text field has focus, and a hint bar teaches the keys. Layout collapses in two steps: the sidebar becomes icons-only below 1120px, then the detail panel narrows and the hint legend hides below 1000px.

ACCESSIBILITY (already built into the tokens above; keep it that way)
- Every text/background pair you introduce must reach 4.5:1 (normal text, including 15px bold); icons and large text 3:1. Measure; do not eyeball.
- Never put white or black text on the bright accent. Use accentFill + accentInk. Hover and press states must keep the ratio.
- Category colors are for glyphs. For label text in the light theme use the darker label variant of each category color.
- Status chip text uses successText / warningText / dangerText, not the raw status colors.
- Focus: a 2px accent ring just outside every focusable element. Honor the OS reduce-motion setting (durations go to 0). Give interactive components accessible roles and names.

HOW TO WORK
1. Ask which stack I use (web, Qt Quick, Flutter, SwiftUI, ...). Do not assume.
2. Create the theme/token file first: all tokens above, three themes, the unit and scale, and a way to switch themes at runtime.
3. Build the primitives next (Button, IconButton, Chip, IconTile, BoxedSection, Input, Dialog, HintBar), each reading only tokens.
4. Then compose screens. Show me screenshots in dark, light and deck before calling anything done.
5. Do not add shadows, gradients, extra accent colors, or color-only status. Status always has a word or an icon too.
6. If something is not covered here, extend the system with the same rules (steps not shadows, one accent, unit multiples) and tell me what you added.
"""

# ---- assemble ----------------------------------------------------------------------------------------------------------------
tpl = (HERE / "design_template.html").read_text(encoding="utf-8")
subs = {
    "SPECIMEN_THEMES": "\n".join(sp_css), "SHOT_GRID": SHOTS["q1_grid_dark"], "COLOR_TABLE": color_table,
    "CATEGORY_SWATCHES": cats, "SCALE_ROWS": "".join(scale_rows), "TYPE_GRID": type_grid, "CARDS": cards,
    "SFM_DARK": SHOTS["sfm_dark"], "SFM_LIGHT": SHOTS["sfm_light"], "SFM_DECK": SHOTS["sfm_deck"],
    "SFM_PROPS": SHOTS["sfm_props"], "LW_LIGHT": SHOTS["q3_light"], "SFM_FAILS": sfm_fail_rows, "SPEC_CARDS": spec_cards, "CONTRAST_SUMMARY": summary, "CONTRAST_FAILS": contrast_fails, "CONTRAST_ALL": contrast_all,
    "FIX_RATIO": str(fix["ratio"]), "N_CHECKS": str(len(checks)), "CSS_VARS": E(css), "QML_THEME": E(D["qml_theme"]),
    "PROMPT": E(PROMPT), "LINEAGE": lineage,
}
tpl = tpl.replace(".foot { padding-top: 24px;", ".colophon { padding-top: 24px;").replace('<div class="foot">\n        <p>Icons:', '<div class="colophon">\n        <p>Icons:')
for k, v in subs.items():
    tpl = tpl.replace("{{" + k + "}}", v)
tpl = fill_icons(tpl)
left = re.findall(r"\{\{[^}]+\}\}", tpl)
if left:
    sys.exit(f"unfilled placeholders: {set(left)}")
(HERE / "design_language.html").write_text(tpl, encoding="utf-8")

# Markdown + prompt for the repo
md = ["# Deckwork design language", "",
      "Deckwork is the visual system shared by steamos-fm and LanWhodis. Token values mirror `lanwhodis/gui/qml/LanWhodis/Theme.qml` "
      "(a test fails if they drift, so update both together). The illustrated version is `deckwork-design-language.html`; the last section of this "
      "file is a prompt that lets an AI coding assistant reuse the language. The same prompt is in `design-language-prompt.txt`.", "", "## Principles", "",
      "1. **Layers are steps, not shadows.** Each surface is a clearly visible luminance step above the one beneath; edges are 1 px borders; no drop shadows.",
      "2. **One accent means \"you can act on this\".** Status colors (success/warning/danger) report state; category colors identify device kinds.",
      "3. **Shape, color and word together.** A glyph on a tinted tile plus a text label; color is never the only signal.",
      "4. **Pointer and controller first.** Rows are 38 px at 1x; text starts at 12 px.",
      "5. **Show the reasoning.** Detail panels list evidence with weights; section titles are uppercase and letter-spaced.",
      "6. **Every action has a key, and the footer says which.**", "7. **One unit scales everything.** unit = 20 px x zoom.", "",
      "## Color tokens", "", "| Token | Role | Dark | Light | Steam Deck |", "|---|---|---|---|---|"]
md += [f"| `{t}` | {ROLES[t]} | `{LW['dark'][t]}` | `{LW['light'][t]}` | `{LW['deck'][t]}` |" for t in ORDER]
md += ["", "Category colors (device kinds only): " + ", ".join(f"{n} `{c}`" for n, c in D["categories"].items()) + ".", "",
       "## Scale", "", "| Token | x unit | px at 1x |", "|---|---|---|"]
md += [f"| `{k}` | {v:g} | {v * U:g} |" for k, v in D["scale"].items()]
md += ["", "## Component specifications", ""]
for t, rs in SPECS:
    md += [f"### {t}", ""] + [f"- **{k}:** {v}" for k, v in rs] + [""]
md += ["## Contrast audit", "",
       f"The shared core as LanWhodis ships it: {len(REAL) - len(fails)} of {len(REAL)} measured pairs meet their WCAG target "
       "(4.5:1 text including 15px bold, 3:1 icons). Solid buttons use `accentFill` / `dangerFill` with white ink.", ""]
if fails:
    md += ["Below target:", "", "| Theme | Pair | Colors | Ratio | Target |", "|---|---|---|---|---|"]
    md += [f"| {THEME[c['theme']]} | {c['pair']} | `{c['fg']}` on `{c['bg']}` | {c['ratio']} | {c['need']} |" for c in fails]
    md += [""]
sfm_bad = [c for c in D["sfm_contrast"] if not c["ok"]]
md += ["steamos-fm today (not yet adopted): " + str(len(sfm_bad)) + " pairs below target.", "",
       "| Theme | Pair | Colors | Ratio | Target |", "|---|---|---|---|---|"]
md += [f"| {THEME[c['theme']]} | {c['pair']} | `{c['fg']}` on `{c['bg']}` | {c['ratio']} | {c['need']} |" for c in sfm_bad]
md += ["",
       "## CSS custom properties", "", "```css", css, "```", "", "## Prompt for an AI coding assistant", "", "```text", PROMPT, "```", ""]
Path(r"C:\Users\alex\OneDrive\Code\lanwhodis\docs").mkdir(exist_ok=True)
Path(r"C:\Users\alex\OneDrive\Code\lanwhodis\docs\DESIGN_LANGUAGE.md").write_text("\n".join(md), encoding="utf-8", newline="\n")
Path(r"C:\Users\alex\OneDrive\Code\lanwhodis\docs\design-language-prompt.txt").write_text(PROMPT, encoding="utf-8", newline="\n")
print("html", (HERE / "design_language.html").stat().st_size // 1024, "KiB;", len(fails), "failing pairs;", "fix ratio", fix["ratio"])
