# LanWhodis design language

Reference for the visual system. Token values mirror `lanwhodis/gui/qml/LanWhodis/Theme.qml` (a test fails if they drift, so update both together). The illustrated, shareable version is the published design-language page; the last section of this file is a prompt that lets an AI coding assistant reuse the language. The same prompt is in `design-language-prompt.txt`.

## Principles

1. **Layers are steps, not shadows.** Each surface is a clearly visible luminance step above the one beneath; edges are 1 px borders; no drop shadows.
2. **One accent means "you can act on this".** Status colors (success/warning/danger) report state; category colors identify device kinds.
3. **Shape, color and word together.** A glyph on a tinted tile plus a text label; color is never the only signal.
4. **Pointer and controller first.** Rows are 38 px at 1x; text starts at 12 px.
5. **Show the reasoning.** Detail panels list evidence with weights; section titles are uppercase and letter-spaced.
6. **Every action has a key, and the footer says which.**
7. **One unit scales everything.** unit = 20 px x zoom.

## Color tokens

| Token | Role | Dark | Light | Steam Deck |
|---|---|---|---|---|
| `bg` | App background, behind everything | `#0e141b` | `#f0f4f8` | `#0e141b` |
| `surface` | Cards, the detail panel, the header | `#1a2332` | `#ffffff` | `#1a2332` |
| `surfaceAlt` | Hover fill for cards | `#222d3e` | `#e4e9f0` | `#222d3e` |
| `accent` | Selection, focus, primary actions, links | `#4a9eff` | `#1a6bc2` | `#f38020` |
| `accentDim` | Muted accent (defined for pressed states, used sparingly) | `#2c5f99` | `#1255a0` | `#c06010` |
| `selected` | Fill of the selected card | `#1e3a5f` | `#c8dff7` | `#3d2a18` |
| `text` | Primary text and chrome icons | `#e8edf2` | `#1c2535` | `#e8edf2` |
| `textDim` | Secondary text, labels, counts, IPs | `#8696a8` | `#5d6d80` | `#8696a8` |
| `divider` | Hairlines between regions | `#2a3545` | `#d0d8e0` | `#2a3545` |
| `dialogSurface` | Dialogs, menus, tooltips, toasts | `#232e3d` | `#ffffff` | `#232e3d` |
| `dialogBorder` | Their 1 px edge | `#3c4d61` | `#c3cedb` | `#3c4d61` |
| `scrim` | Dims the app behind a dialog | `#a6040a0d` | `#66141e2d` | `#a6040a0d` |
| `sectionSurface` | Boxed sections in the detail panel | `#1f2a3a` | `#f4f7fb` | `#1f2a3a` |
| `sectionBorder` | Their edge; also input borders | `#33445b` | `#c3cedb` | `#33445b` |
| `buttonSurface` | Default (secondary) button fill | `#33455e` | `#e2e9f1` | `#34455c` |
| `buttonBorder` | Its edge | `#5578a3` | `#93a7bd` | `#5a7699` |
| `inputSurface` | Text inputs, search, segmented control | `#0f1722` | `#ffffff` | `#0f1722` |
| `success` | Status only: NEW and BACK chips, good results | `#4cc38a` | `#2e8f5e` | `#4cc38a` |
| `warning` | Status only: caution, medium confidence | `#e0a84f` | `#b87a1c` | `#e0a84f` |
| `danger` | Status only: destructive actions, low confidence | `#e5534b` | `#c93a33` | `#e5534b` |

Category colors (device kinds only): Computers `#4C8DFF`, Mobile `#B36BFF`, Media `#FF7A59`, Gaming `#2EC4A0`, Smart Home `#F2B01E`, Peripherals `#6E8BA8`, Network `#3FB6E8`, Other `#8A94A3`.

## Scale

| Token | x unit | px at 1x |
|---|---|---|
| `fontSizeSm` | 0.62 | 12.4 |
| `fontSize` | 0.75 | 15 |
| `fontSizeLg` | 0.95 | 19 |
| `fontSizeXl` | 1.35 | 27 |
| `rowHeight` | 1.9 | 38 |
| `radius` | 0.5 | 10 |
| `radiusLg` | 0.8 | 16 |
| `pad` | 0.5 | 10 |
| `gap` | 0.6 | 12 |

## Component specifications

### Button

- **Height:** 2.1u · 42 px (compact 1.7u · 34 px)
- **Padding:** 0.75u each side · 15 px
- **Icon:** 1.1 × fontSizeLg · 21 px, 9 px gap
- **Radius:** radius · 10 px, border 1 px
- **Variants:** default · primary (accent) · danger · ghost
- **Label:** fontSize; bold on primary and danger
- **States:** hover: fill × 1.14 lighter · press: × 1.18 darker · focus: text-color border · disabled: 40%

### Icon button

- **Size:** 2.1u · 42 px, glyph 55%
- **Radius:** radius · 10 px
- **Active:** accent 22% fill, accent glyph
- **Hover / press:** text color overlay 10% / 16%
- **Tooltip:** dialogSurface, 1 px dialogBorder, fontSizeSm, below the button

### Chip

- **Height:** 1.3u · 26 px, fully rounded
- **Padding:** 0.45u each side
- **Text:** fontSizeSm · 12.4 px, bold
- **Fill / border:** tone at 16% / 35%
- **Tones:** neutral (dim) · accent · success · warning · danger · custom

### Icon tile

- **Sizes:** 2.1u row · 3.1u card · 3u dialog · 4.4u detail · 5.2u empty state
- **Radius:** 28% of size
- **Fill / border:** category color at 17% / 38% (offline: 8% / 15%)
- **Glyph:** 54% of the tile, full category color (offline: 45% opacity)

### Device card

- **Cell:** min width 14u · 280 px, height 6.4u · 128 px, 0.3u · 6 px inset
- **Radius / padding:** radiusLg · 16 px / 0.8u · 16 px
- **Name:** fontSizeLg bold · type label fontSize bold in category color · IP fontSizeSm monospace dim
- **Footer:** vendor (or OS) in dim fontSizeSm, status chip on the right
- **States:** hover: surfaceAlt + border in category color 55% · selected: selected fill, 2 px accent border · press: scale 98.5%

### List row

- **Height:** 2.9u · 58 px, tile 2.1u
- **Columns:** name 30% · type 16% · address 14% · vendor 22% · OS 18%
- **Zebra:** odd rows surface at 50%; selected row uses selected + 1 px accent border
- **Header:** uppercase, bold, letter-spaced fontSizeSm

### Sidebar item

- **Height:** 2.0u · 40 px, radius 10 px
- **Icon:** 1.15 × fontSizeLg, category color (accent when selected)
- **Count:** fontSizeSm dim, right aligned
- **Selected:** accent 20% fill, 0.18u · 4 px accent marker, bold label
- **Compact:** icon only, centered, in a 3.6u · 72 px column

### Boxed section

- **Surface:** sectionSurface, 1 px sectionBorder, radius 10 px
- **Padding:** 1.3 × pad · 13 px sides, pad · 10 px top
- **Title:** fontSizeSm bold uppercase, letter-spacing 1.6 px, dim
- **Rows:** key 34% dim · value 64% text, both fontSizeSm; values are selectable

### Search field

- **Height:** 2.1u · 42 px, fully rounded
- **Fill / border:** inputSurface / sectionBorder; border becomes accent on focus
- **Parts:** leading search icon, text, clear button when not empty; Escape clears and leaves

### Dialog

- **Width:** min(38u · 760 px, window − 3u)
- **Surface:** dialogSurface, 1 px dialogBorder, radiusLg
- **Padding:** 1.1u · 22 px
- **Scrim:** scrim token over the whole window; clicking it closes the dialog
- **Footer:** ghost Cancel, primary Save, optional Reset on the left

### Hint bar

- **Height:** 1.9u · 38 px, top hairline
- **Message:** status text, dim, left
- **Key caps:** 1.2u · 24 px high, radius 5 px, text at 8% fill and 22% border, bold 11.4 px

### Toast

- **Surface:** dialogSurface + dialogBorder, radius 10 px
- **Position:** centered, 3.2u · 64 px above the bottom edge
- **Timing:** fade 160 ms, hold 2.6 s

## Contrast audit

44 of 57 measured pairs meet their WCAG target. Below target:

| Theme | Pair | Colors | Ratio | Target |
|---|---|---|---|---|
| Dark | white on accent button | `#ffffff` on `#4a9eff` | 2.75 | 4.5 |
| Dark | white on danger button | `#ffffff` on `#e5534b` | 3.7 | 4.5 |
| Dark | danger chip text | `#e5534b` on `#3a2b36` | 3.6 | 4.5 |
| Light | success chip text | `#2e8f5e` on `#deede5` | 3.33 | 4.5 |
| Light | warning chip text | `#b87a1c` on `#f4eadb` | 3.01 | 4.5 |
| Light | danger chip text | `#c93a33` on `#f6dfde` | 4.01 | 4.5 |
| Light | Media colour on card | `#ff7a59` on `#ffffff` | 2.57 | 3.0 |
| Light | Gaming colour on card | `#2ec4a0` on `#ffffff` | 2.21 | 3.0 |
| Light | Smart Home colour on card | `#f2b01e` on `#ffffff` | 1.91 | 3.0 |
| Light | Network colour on card | `#3fb6e8` on `#ffffff` | 2.32 | 3.0 |
| Deck | white on accent button | `#ffffff` on `#f38020` | 2.65 | 4.5 |
| Deck | white on danger button | `#ffffff` on `#e5534b` | 3.7 | 4.5 |
| Deck | danger chip text | `#e5534b` on `#3a2b36` | 3.6 | 4.5 |

Recommended fix for primary/danger labels: `#0e141b` on the accent (6.72:1 dark, 6.98:1 Steam Deck).

## CSS custom properties

```css
/* LanWhodis design tokens. Dark is the default; light and Steam Deck override it.
   --lw-on-accent is the recommended label color for primary/danger buttons (see the audit). */
:root {
  --lw-unit: 20px;            /* multiply by the user's zoom */
  --lw-font-size-sm: calc(var(--lw-unit) * 0.62);
  --lw-font-size: calc(var(--lw-unit) * 0.75);
  --lw-font-size-lg: calc(var(--lw-unit) * 0.95);
  --lw-font-size-xl: calc(var(--lw-unit) * 1.35);
  --lw-row-height: calc(var(--lw-unit) * 1.9);
  --lw-radius: calc(var(--lw-unit) * 0.5);
  --lw-radius-lg: calc(var(--lw-unit) * 0.8);
  --lw-pad: calc(var(--lw-unit) * 0.5);
  --lw-gap: calc(var(--lw-unit) * 0.6);
  --lw-font: "Segoe UI", system-ui, "DejaVu Sans", sans-serif;
  --lw-mono: "Cascadia Mono", Consolas, "DejaVu Sans Mono", monospace;
}
:root,
:root[data-theme="dark"] {
  --lw-bg: #0e141b;
  --lw-surface: #1a2332;
  --lw-surface-alt: #222d3e;
  --lw-accent: #4a9eff;
  --lw-accent-dim: #2c5f99;
  --lw-selected: #1e3a5f;
  --lw-text: #e8edf2;
  --lw-text-dim: #8696a8;
  --lw-divider: #2a3545;
  --lw-dialog-surface: #232e3d;
  --lw-dialog-border: #3c4d61;
  --lw-scrim: rgba(4, 10, 13, 0.65);
  --lw-section-surface: #1f2a3a;
  --lw-section-border: #33445b;
  --lw-button-surface: #33455e;
  --lw-button-border: #5578a3;
  --lw-input-surface: #0f1722;
  --lw-success: #4cc38a;
  --lw-warning: #e0a84f;
  --lw-danger: #e5534b;
  --lw-on-accent: #0e141b;
}
:root[data-theme="light"] {
  --lw-bg: #f0f4f8;
  --lw-surface: #ffffff;
  --lw-surface-alt: #e4e9f0;
  --lw-accent: #1a6bc2;
  --lw-accent-dim: #1255a0;
  --lw-selected: #c8dff7;
  --lw-text: #1c2535;
  --lw-text-dim: #5d6d80;
  --lw-divider: #d0d8e0;
  --lw-dialog-surface: #ffffff;
  --lw-dialog-border: #c3cedb;
  --lw-scrim: rgba(20, 30, 45, 0.40);
  --lw-section-surface: #f4f7fb;
  --lw-section-border: #c3cedb;
  --lw-button-surface: #e2e9f1;
  --lw-button-border: #93a7bd;
  --lw-input-surface: #ffffff;
  --lw-success: #2e8f5e;
  --lw-warning: #b87a1c;
  --lw-danger: #c93a33;
  --lw-on-accent: #ffffff;
}
:root[data-theme="deck"] {
  --lw-bg: #0e141b;
  --lw-surface: #1a2332;
  --lw-surface-alt: #222d3e;
  --lw-accent: #f38020;
  --lw-accent-dim: #c06010;
  --lw-selected: #3d2a18;
  --lw-text: #e8edf2;
  --lw-text-dim: #8696a8;
  --lw-divider: #2a3545;
  --lw-dialog-surface: #232e3d;
  --lw-dialog-border: #3c4d61;
  --lw-scrim: rgba(4, 10, 13, 0.65);
  --lw-section-surface: #1f2a3a;
  --lw-section-border: #33445b;
  --lw-button-surface: #34455c;
  --lw-button-border: #5a7699;
  --lw-input-surface: #0f1722;
  --lw-success: #4cc38a;
  --lw-warning: #e0a84f;
  --lw-danger: #e5534b;
  --lw-on-accent: #0e141b;
}
```

## Prompt for an AI coding assistant

```text
You are helping me build UI in the "LanWhodis" design language (it descends from steamos-fm). Follow it closely and ask before you deviate.

CHARACTER
Deep navy surfaces, ONE blue accent, rounded cards, icon tiles tinted by category, boxed sections with small uppercase letter-spaced titles. Calm, dense, friendly to a mouse and a game controller. No drop shadows. No gradients. No emoji as icons.

TOKENS (use the names in code; never hard-code hex inside a component)
Colors are #RRGGBB, except scrim which is #AARRGGBB.
bg: dark #0e141b | light #f0f4f8 | deck #0e141b
surface: dark #1a2332 | light #ffffff | deck #1a2332
surfaceAlt: dark #222d3e | light #e4e9f0 | deck #222d3e
accent: dark #4a9eff | light #1a6bc2 | deck #f38020
accentDim: dark #2c5f99 | light #1255a0 | deck #c06010
selected: dark #1e3a5f | light #c8dff7 | deck #3d2a18
text: dark #e8edf2 | light #1c2535 | deck #e8edf2
textDim: dark #8696a8 | light #5d6d80 | deck #8696a8
divider: dark #2a3545 | light #d0d8e0 | deck #2a3545
dialogSurface: dark #232e3d | light #ffffff | deck #232e3d
dialogBorder: dark #3c4d61 | light #c3cedb | deck #3c4d61
scrim: dark #a6040a0d | light #66141e2d | deck #a6040a0d
sectionSurface: dark #1f2a3a | light #f4f7fb | deck #1f2a3a
sectionBorder: dark #33445b | light #c3cedb | deck #33445b
buttonSurface: dark #33455e | light #e2e9f1 | deck #34455c
buttonBorder: dark #5578a3 | light #93a7bd | deck #5a7699
inputSurface: dark #0f1722 | light #ffffff | deck #0f1722
success: dark #4cc38a | light #2e8f5e | deck #4cc38a
warning: dark #e0a84f | light #b87a1c | deck #e0a84f
danger: dark #e5534b | light #c93a33 | deck #e5534b
Add one token the original lacks: onAccent = #0e141b on dark and deck, #ffffff on light (label color on accent/danger fills).
Category colors (device kinds, never state): Computers #4C8DFF, Mobile #B36BFF, Media #FF7A59, Gaming #2EC4A0, Smart Home #F2B01E, Peripherals #6E8BA8, Network #3FB6E8, Other #8A94A3.

SCALE (everything is a multiple of one unit; unit = 20px x user zoom)
fontSizeSm = 0.62u (12.4px); fontSize = 0.75u (15px); fontSizeLg = 0.95u (19px); fontSizeXl = 1.35u (27px); rowHeight = 1.9u (38px); radius = 0.5u (10px); radiusLg = 0.8u (16px); pad = 0.5u (10px); gap = 0.6u (12px).
Fonts: the platform UI font (Segoe UI / system-ui / DejaVu Sans). Monospace only for IPs, MACs and literals. Weights: regular and bold only.
Section titles: uppercase, bold, fontSizeSm, letter-spacing 0.08u, textDim.

SHAPE AND DEPTH
Radius: 0.5u controls and sections, 0.8u cards and dialogs, pills fully rounded, icon tiles 28% of their size. Borders are always 1px (selected card: 2px accent). Depth comes only from stepping surface colors (bg -> surface -> surfaceAlt / dialogSurface) plus a hairline border. Every layer must be a clearly visible step lighter than the one below it.

RECIPES
- Icon tile: rounded square, fill = category color at 17%, border = 38%, glyph at 54% of the tile in the full category color. Offline: 8% / 15%, glyph at 45% opacity.
- Chip: height 1.3u, pill, fontSizeSm bold, text = tone, fill 16%, border 35%. Tones: neutral(textDim), accent, success, warning, danger.
- Button: height 2.1u, radius 0.5u, 1px border, optional 1.1 x fontSizeLg icon. Default = buttonSurface + buttonBorder. Primary = accent fill, bold. Danger = danger fill, bold. Ghost = transparent, no border. Hover lighter (x1.14), press darker (x1.18), disabled 40% opacity, keyboard focus visible.
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

ACCESSIBILITY (improvements over the original, apply them)
- Measured contrast: white text on the accent blue is 2.75:1 and on the Deck orange 2.65:1, which fails WCAG AA for normal text. Use onAccent (above) for primary and danger labels instead; #0e141b on #4a9eff is 6.72:1.
- Light theme: category colors fail as 15px label text on white (Smart Home yellow is 1.9:1). Use the text color for labels and keep the category color on the glyph, or add darker light-theme variants.
- Light-theme status chips (success, warning, danger on their 16% tint) reach only 3.0-4.0:1; darken those tones in the light theme.
- Focus: use a 2px accent ring with a 2px offset on every focusable element.
- Honor the OS reduce-motion setting; give interactive components accessible roles and names.
- Check every NEW text/background pair you introduce: 4.5:1 for normal text, 3:1 for icons and large text.

HOW TO WORK
1. Ask which stack I use (web, Qt Quick, Flutter, SwiftUI, ...). Do not assume.
2. Create the theme/token file first: all tokens above, three themes, the unit and scale, and a way to switch themes at runtime.
3. Build the primitives next (Button, IconButton, Chip, IconTile, BoxedSection, Input, Dialog, HintBar), each reading only tokens.
4. Then compose screens. Show me screenshots in dark, light and deck before calling anything done.
5. Do not add shadows, gradients, extra accent colors, or color-only status. Status always has a word or an icon too.
6. If something is not covered here, extend the system with the same rules (steps not shadows, one accent, unit multiples) and tell me what you added.

```
