import QtQuick

// A bundled Fluent icon recoloured to `tint` (served by gui/iconprovider.py as image://lw/).
Image {
    id: root
    property string name: ""
    property color tint: "#ffffff"
    property real size: 24

    width: size
    height: size
    // render at 2x so the icon stays crisp on HiDPI and when zoomed
    sourceSize: Qt.size(Math.ceil(size * 2), Math.ceil(size * 2))
    source: name === "" ? "" : "image://lw/" + encodeURIComponent(name + "," + tint)
    fillMode: Image.PreserveAspectFit
    smooth: true
    mipmap: true
}
