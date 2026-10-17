"""Static checks over the QML that encode lessons learned the hard way."""
import re
from pathlib import Path

QML = Path(__file__).resolve().parent.parent / "lanwhodis" / "gui" / "qml"
FILES = sorted(QML.rglob("*.qml"))


def test_no_property_is_named_like_a_signal_handler():
    # QML reads `property color onAccent` as a handler for a signal called "accent" and refuses to load the file
    bad = [(f.name, m) for f in FILES for m in re.findall(r"property\s+\w+\s+(on[A-Z]\w*)\s*:", f.read_text(encoding="utf-8"))]
    assert bad == []


def test_animation_durations_go_through_the_reduced_motion_helper():
    bad = []
    for f in FILES:
        if f.name == "Theme.qml":
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"duration:\s*\d", line):
                bad.append(f"{f.name}:{n}")
    assert bad == [], f"use Theme.dur(ms): {bad}"


def test_looping_animations_stop_under_reduced_motion():
    bad = []
    for f in FILES:
        lines = f.read_text(encoding="utf-8").splitlines()
        for n, line in enumerate(lines):
            if "Animation.Infinite" in line and not any("Theme.reduceMotion" in prev for prev in lines[max(0, n - 3):n]):
                bad.append(f"{f.name}:{n + 1}")
    assert bad == []


def test_every_clickable_component_has_an_accessible_name():
    # A MouseArea alone is invisible to a screen reader; the component that owns it must say what it is.
    missing = [f.name for f in FILES if "MouseArea" in f.read_text(encoding="utf-8")
               and "Accessible." not in f.read_text(encoding="utf-8")]
    assert missing == [], f"add Accessible.role/name to: {missing}"


def test_ids_do_not_shadow_a_components_default_property_alias():
    # SectionBox exposes `content`; an `id: content` in a file that instantiates SectionBox makes `content.width`
    # inside its children silently resolve to the alias (a list), collapsing widths to zero.
    aliases = {m for f in FILES for m in re.findall(r"default property alias (\w+):", f.read_text(encoding="utf-8"))}
    bad = [f.name for f in FILES for a in aliases if re.search(rf"\bid:\s*{a}\b", f.read_text(encoding="utf-8"))
           and "SectionBox" in f.read_text(encoding="utf-8")]
    assert bad == [], f"rename the id in: {bad}"


def test_no_control_characters_in_sources():
    # Our own tooling once turned "\\1" and "\\b" into raw control bytes inside regexes; never again.
    root = QML.parent.parent.parent
    bad = []
    for ext in ("*.py", "*.qml", "*.toml", "*.md"):
        for f in root.rglob(ext):
            if any(part in (".venv", ".git", "build", "__pycache__") for part in f.parts):
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
            if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", text):
                bad.append(str(f.relative_to(root)))
    assert bad == []
