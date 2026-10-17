"""docs/DESIGN_LANGUAGE.md mirrors the QML theme: if a token changes, the doc must change with it."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THEME = (ROOT / "lanwhodis" / "gui" / "qml" / "LanWhodis" / "Theme.qml").read_text(encoding="utf-8")
DOC = (ROOT / "docs" / "DESIGN_LANGUAGE.md").read_text(encoding="utf-8").lower()
PROMPT = (ROOT / "docs" / "design-language-prompt.txt").read_text(encoding="utf-8").lower()


def palette_tokens():
    return re.findall(r'readonly property color (\w+):\s+"(#[0-9a-fA-F]{6,8})"', THEME)


def test_every_theme_color_appears_in_the_doc_and_the_prompt():
    missing = [(t, h) for t, h in palette_tokens() if h.lower() not in DOC or h.lower() not in PROMPT]
    assert missing == [], f"design docs are out of date for: {missing}"


def test_scale_multipliers_appear_in_the_doc():
    for name, mult in re.findall(r"readonly property real (\w+):\s+unit \* ([0-9.]+)", THEME):
        assert f"`{name.lower()}` | {float(mult):g} |" in DOC, name   # DOC is lower-cased


def test_category_colors_appear_in_the_doc():
    from lanwhodis import icons
    for color in icons.CATEGORY_COLOR.values():
        assert color.lower() in DOC
