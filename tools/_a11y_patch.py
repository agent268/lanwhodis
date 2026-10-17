"""One-off patch: apply the audit fixes to the QML components. Not kept after the branch is reviewed."""
import re
from pathlib import Path

Q = Path(__file__).resolve().parent.parent / "lanwhodis" / "gui" / "qml"
L = Q / "LanWhodis"


def edit(path: Path, pairs, count=1):
    s = path.read_text(encoding="utf-8")
    for old, new in pairs:
        assert old in s, f"{path.name}: {old[:60]!r}"
        s = s.replace(old, new, count)
    path.write_text(s, encoding="utf-8", newline="\n")


# 1) every animation duration goes through Theme.dur(); looping animations stop under reduced motion
for f in [Q / "Main.qml", *L.glob("*.qml")]:
    s = f.read_text(encoding="utf-8")
    new = re.sub(r"duration: (\d+)", r"duration: Theme.dur(\1)", s)
    new = new.replace("running: backend.scanning\n", "running: backend.scanning && !Theme.reduceMotion\n")
    new = new.replace("running: root.busy\n", "running: root.busy && !Theme.reduceMotion\n")
    if new != s:
        f.write_text(new, encoding="utf-8", newline="\n")

# 2) focus ring snippet (2 px accent, 3 px outside the control) shared by the focusable components
RING = """
    // keyboard focus: a clear 2 px ring just outside the control (only Tab can focus these, so no ring after a click)
    Rectangle {
        visible: parent.activeFocus
        anchors.fill: parent
        anchors.margins: -3
        radius: parent.radius + 3
        color: "transparent"
        border.width: 2
        border.color: Theme.accent
    }
"""

# --- LwButton ---------------------------------------------------------------------------------
edit(L / "LwButton.qml", [
    ("    readonly property color _fg: (primary || danger) ? \"#ffffff\" : Theme.text\n",
     "    readonly property color _fg: danger ? Theme.onDanger : primary ? Theme.onAccent : Theme.text\n"),
    ("    border.color: activeFocus ? Theme.text\n                 : (primary || danger) ? Qt.darker(_base, 1.15) : Theme.buttonBorder\n",
     "    border.color: (primary || danger) ? Qt.darker(_base, 1.15) : Theme.buttonBorder\n"),
    ("    Keys.onReturnPressed: btn.clicked()\n",
     "    Accessible.role: Accessible.Button\n    Accessible.name: btn.text !== \"\" ? btn.text : btn.tooltip\n"
     "    Accessible.onPressAction: btn.clicked()\n    Keys.onReturnPressed: btn.clicked()\n"),
    ("    Row {\n        id: row\n", RING + "\n    Row {\n        id: row\n"),
])

# --- IconButton -------------------------------------------------------------------------------
edit(L / "IconButton.qml", [
    ("    border.width: activeFocus ? 1 : 0\n    border.color: Theme.text\n", ""),
    ("    Keys.onReturnPressed: btn.clicked()\n",
     "    Accessible.role: Accessible.Button\n    Accessible.name: btn.tooltip\n    Accessible.checkable: true\n"
     "    Accessible.checked: btn.active\n    Accessible.onPressAction: btn.clicked()\n    Keys.onReturnPressed: btn.clicked()\n"),
    ("    Icon {\n        anchors.centerIn: parent\n", RING + "\n    Icon {\n        anchors.centerIn: parent\n"),
])

# --- SidebarItem (had no visible focus at all) -------------------------------------------------
edit(L / "SidebarItem.qml", [
    ("    Keys.onReturnPressed: item.clicked()\n",
     "    Accessible.role: Accessible.Button\n    Accessible.name: item.label + (item.count >= 0 ? \", \" + item.count : \"\")\n"
     "    Accessible.checkable: true\n    Accessible.checked: item.selected\n    Accessible.onPressAction: item.clicked()\n"
     "    Keys.onReturnPressed: item.clicked()\n"),
    ("    Rectangle {                       // selection marker\n", RING + "\n    Rectangle {                       // selection marker\n"),
])

# --- Chip: text uses the contrast-tuned tone, fill/border keep the base tone ------------------------
edit(L / "Chip.qml", [
    ("    implicitHeight: Theme.unit * 1.3\n",
     "    // 12 px text on its own 16% tint needs a tuned colour; the custom tone is supplied by the caller\n"
     "    readonly property color _text: tone === \"success\" ? Theme.successText\n"
     "                                 : tone === \"warning\" ? Theme.warningText\n"
     "                                 : tone === \"danger\" ? Theme.dangerText\n"
     "                                 : tone === \"neutral\" ? Theme.textDim : _tone\n\n"
     "    Accessible.role: Accessible.StaticText\n    Accessible.name: chip.text\n\n"
     "    implicitHeight: Theme.unit * 1.3\n"),
    ("            name: chip.iconName\n            tint: chip._tone\n", "            name: chip.iconName\n            tint: chip._text\n"),
    ("            text: chip.text\n            color: chip._tone\n", "            text: chip.text\n            color: chip._text\n"),
])

# --- SearchField / EditDialog / PopupMenu names -------------------------------------------------
edit(L / "SearchField.qml", [
    ("    function focusField()", "    Accessible.role: Accessible.EditableText\n    Accessible.name: field.placeholder\n\n    function focusField()"),
])
edit(L / "EditDialog.qml", [
    ("    visible: false\n    z: 100\n", "    visible: false\n    z: 100\n    Accessible.role: Accessible.Dialog\n    Accessible.name: \"Edit device\"\n"),
])

# --- cards and rows: label colour roles + names ------------------------------------------------------
for name in ("DeviceCard.qml", "DeviceRow.qml"):
    edit(L / name, [
        ("    required property string subtitle\n",
         "    required property string subtitle\n    required property string labelDark\n    required property string labelLight\n"
         "    required property string status_text\n"),
        ("    property bool selected: false\n",
         "    property bool selected: false\n    Accessible.role: Accessible.ListItem\n"
         "    Accessible.name: cell.name + \", \" + cell.typeLabel + \", \" + cell.ip + (cell.status_text !== \"\" ? \", \" + cell.status_text : \"\")\n"
         "    Accessible.selected: cell.selected\n    Accessible.onPressAction: cell.activated()\n"),
        ("Theme.alpha(cell.color, cell.offline ? 0.55 : 1.0)",
         "Theme.alpha(Theme.labelColor(cell.labelDark, cell.labelLight), cell.offline ? 0.7 : 1.0)"),
    ])

# --- detail panel type chip uses the label colour ----------------------------------------------------
edit(L / "DetailPanel.qml", [
    ("customColor: panel.cur.color || Theme.accent }",
     "customColor: Theme.labelColor(panel.cur.labelDark || panel.cur.color || Theme.accent, panel.cur.labelLight || panel.cur.color || Theme.accent) }"),
])

# --- Main: reduced motion binding ------------------------------------------------------------------------
edit(Q / "Main.qml", [
    ("    Binding { target: Theme; property: \"zoom\"; value: backend.zoom }\n",
     "    Binding { target: Theme; property: \"zoom\"; value: backend.zoom }\n"
     "    Binding { target: Theme; property: \"reduceMotion\"; value: backend.reduceMotion }\n"),
])
print("QML patched")
