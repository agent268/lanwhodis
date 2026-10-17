import QtQuick

// A device's icon on a tinted rounded square; the tint is the device category colour.
Rectangle {
    id: tile

    property string iconName: ""
    property color tileColor: Theme.accent
    property real size: Theme.unit * 3
    property bool dim: false

    width: size
    height: size
    radius: size * 0.28
    color: Theme.alpha(tileColor, dim ? 0.08 : 0.17)
    border.width: 1
    border.color: Theme.alpha(tileColor, dim ? 0.15 : 0.38)

    Icon {
        anchors.centerIn: parent
        name: tile.iconName
        tint: tile.tileColor
        size: tile.size * 0.54
        opacity: tile.dim ? 0.45 : 1.0
    }
}
