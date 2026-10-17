pragma Singleton
import QtQuick

// Design tokens. Palette and component language follow steamos-fm's Theme.qml (dark navy + blue accent,
// a light mode, and a Steam Deck mode with the orange accent) so the two apps read as a family.
QtObject {
    id: root

    // "dark" | "light" | "deck"   (bound to backend.theme from Main.qml)
    property string mode: "dark"
    property real zoom: 1.0

    // ── Scale ─────────────────────────────────────────────────────
    readonly property real unit:       20 * zoom
    readonly property real fontSizeSm: unit * 0.62
    readonly property real fontSize:   unit * 0.75
    readonly property real fontSizeLg: unit * 0.95
    readonly property real fontSizeXl: unit * 1.35
    readonly property real rowHeight:  unit * 1.9
    readonly property real radius:     unit * 0.5
    readonly property real radiusLg:   unit * 0.8
    readonly property real pad:        unit * 0.5
    readonly property real gap:        unit * 0.6
    readonly property bool dark:       mode !== "light"

    // ── Active palette (re-bound on mode change) ──────────────────
    readonly property color bg:             _pal.bg
    readonly property color surface:        _pal.surface
    readonly property color surfaceAlt:     _pal.surfaceAlt
    readonly property color accent:         _pal.accent
    readonly property color accentDim:      _pal.accentDim
    readonly property color selected:       _pal.selected
    readonly property color text:           _pal.text
    readonly property color textDim:        _pal.textDim
    readonly property color divider:        _pal.divider
    readonly property color dialogSurface:  _pal.dialogSurface
    readonly property color dialogBorder:   _pal.dialogBorder
    readonly property color scrim:          _pal.scrim
    readonly property color sectionSurface: _pal.sectionSurface
    readonly property color sectionBorder:  _pal.sectionBorder
    readonly property color buttonSurface:  _pal.buttonSurface
    readonly property color buttonBorder:   _pal.buttonBorder
    readonly property color inputSurface:   _pal.inputSurface
    readonly property color success:        _pal.success
    readonly property color warning:        _pal.warning
    readonly property color danger:         _pal.danger

    // accepts a color or a "#rrggbb" string (the model delivers category colours as strings)
    function alpha(c, a) { var q = Qt.color(c); return Qt.rgba(q.r, q.g, q.b, a) }

    property var _pal: _dark
    onModeChanged: {
        switch (mode) {
        case "light": _pal = _light; break
        case "deck":  _pal = _deck;  break
        default:      _pal = _dark;  break
        }
    }

    property var _dark: QtObject {
        readonly property color bg:             "#0e141b"
        readonly property color surface:        "#1a2332"
        readonly property color surfaceAlt:     "#222d3e"
        readonly property color accent:         "#4a9eff"
        readonly property color accentDim:      "#2c5f99"
        readonly property color selected:       "#1e3a5f"
        readonly property color text:           "#e8edf2"
        readonly property color textDim:        "#8696a8"
        readonly property color divider:        "#2a3545"
        readonly property color dialogSurface:  "#232e3d"
        readonly property color dialogBorder:   "#3c4d61"
        readonly property color scrim:          "#a6040a0d"
        readonly property color sectionSurface: "#1f2a3a"
        readonly property color sectionBorder:  "#33445b"
        readonly property color buttonSurface:  "#33455e"
        readonly property color buttonBorder:   "#5578a3"
        readonly property color inputSurface:   "#0f1722"
        readonly property color success:        "#4cc38a"
        readonly property color warning:        "#e0a84f"
        readonly property color danger:         "#e5534b"
    }

    property var _light: QtObject {
        readonly property color bg:             "#f0f4f8"
        readonly property color surface:        "#ffffff"
        readonly property color surfaceAlt:     "#e4e9f0"
        readonly property color accent:         "#1a6bc2"
        readonly property color accentDim:      "#1255a0"
        readonly property color selected:       "#c8dff7"
        readonly property color text:           "#1c2535"
        readonly property color textDim:        "#5d6d80"
        readonly property color divider:        "#d0d8e0"
        readonly property color dialogSurface:  "#ffffff"
        readonly property color dialogBorder:   "#c3cedb"
        readonly property color scrim:          "#66141e2d"
        readonly property color sectionSurface: "#f4f7fb"
        readonly property color sectionBorder:  "#c3cedb"
        readonly property color buttonSurface:  "#e2e9f1"
        readonly property color buttonBorder:   "#93a7bd"
        readonly property color inputSurface:   "#ffffff"
        readonly property color success:        "#2e8f5e"
        readonly property color warning:        "#b87a1c"
        readonly property color danger:         "#c93a33"
    }

    // Steam Deck gaming mode: same navy, orange accent
    property var _deck: QtObject {
        readonly property color bg:             "#0e141b"
        readonly property color surface:        "#1a2332"
        readonly property color surfaceAlt:     "#222d3e"
        readonly property color accent:         "#f38020"
        readonly property color accentDim:      "#c06010"
        readonly property color selected:       "#3d2a18"
        readonly property color text:           "#e8edf2"
        readonly property color textDim:        "#8696a8"
        readonly property color divider:        "#2a3545"
        readonly property color dialogSurface:  "#232e3d"
        readonly property color dialogBorder:   "#3c4d61"
        readonly property color scrim:          "#a6040a0d"
        readonly property color sectionSurface: "#1f2a3a"
        readonly property color sectionBorder:  "#33445b"
        readonly property color buttonSurface:  "#34455c"
        readonly property color buttonBorder:   "#5a7699"
        readonly property color inputSurface:   "#0f1722"
        readonly property color success:        "#4cc38a"
        readonly property color warning:        "#e0a84f"
        readonly property color danger:         "#e5534b"
    }
}
