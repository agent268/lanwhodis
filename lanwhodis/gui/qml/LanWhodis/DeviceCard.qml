import QtQuick

// A device as a card in the grid view. Used as a GridView delegate: roles arrive as required properties.
Item {
    id: cell

    required property int index
    required property string sid
    required property string name
    required property string ip
    required property string typeLabel
    required property string color
    required property string iconName
    required property string vendor
    required property string os
    required property string status
    required property bool edited
    required property bool offline
    required property string subtitle
    required property string labelDark
    required property string labelLight

    property bool selected: false
    Accessible.role: Accessible.ListItem
    Accessible.name: cell.name + ", " + cell.typeLabel + ", " + cell.ip + (cell.status !== "" ? ", " + cell.status : "")
    Accessible.selected: cell.selected
    Accessible.onPressAction: cell.activated()
    signal activated()
    signal opened()

    Rectangle {
        id: card
        anchors.fill: parent
        anchors.margins: Theme.unit * 0.3
        radius: Theme.radiusLg
        color: cell.selected ? Theme.selected
             : mouse.containsMouse ? Theme.surfaceAlt : Theme.surface
        border.width: cell.selected ? 2 : 1
        border.color: cell.selected ? Theme.accent
                    : mouse.containsMouse ? Theme.alpha(cell.color, 0.55) : Theme.divider
        scale: mouse.pressed ? 0.985 : 1.0
        Behavior on color { ColorAnimation { duration: Theme.dur(110) } }
        Behavior on border.color { ColorAnimation { duration: Theme.dur(110) } }
        Behavior on scale { NumberAnimation { duration: Theme.dur(80) } }

        Tile {
            id: tile
            x: Theme.unit * 0.8
            y: Theme.unit * 0.8
            size: Theme.unit * 3.1
            iconName: cell.iconName
            tileColor: cell.color
            glyphColor: Theme.labelColor(cell.labelDark, cell.labelLight)
            dim: cell.offline
        }

        Column {
            anchors.left: tile.right
            anchors.leftMargin: Theme.unit * 0.7
            anchors.right: parent.right
            anchors.rightMargin: Theme.unit * 0.8
            anchors.top: parent.top
            anchors.topMargin: Theme.unit * 0.8
            spacing: Theme.unit * 0.12
            Text {
                width: parent.width
                text: cell.name
                elide: Text.ElideRight
                color: cell.offline ? Theme.textDim : Theme.text
                font.pixelSize: Theme.fontSizeLg
                font.bold: true
            }
            Text {
                width: parent.width
                text: cell.typeLabel + (cell.edited ? "  ✎" : "")
                elide: Text.ElideRight
                color: Theme.alpha(Theme.labelColor(cell.labelDark, cell.labelLight), cell.offline ? 0.7 : 1.0)
                font.pixelSize: Theme.fontSize
                font.bold: true
            }
            Text {
                width: parent.width
                text: cell.ip
                elide: Text.ElideRight
                color: Theme.textDim
                font.pixelSize: Theme.fontSizeSm
                font.family: "monospace"
            }
        }

        Row {
            anchors.left: parent.left
            anchors.leftMargin: Theme.unit * 0.8
            anchors.right: parent.right
            anchors.rightMargin: Theme.unit * 0.8
            anchors.bottom: parent.bottom
            anchors.bottomMargin: Theme.unit * 0.7
            spacing: Theme.unit * 0.4
            Text {
                width: parent.width - chips.width - (chips.visible ? parent.spacing : 0)
                anchors.verticalCenter: parent.verticalCenter
                text: cell.vendor !== "" ? cell.vendor : cell.os
                elide: Text.ElideRight
                color: Theme.textDim
                font.pixelSize: Theme.fontSizeSm
            }
            Row {
                id: chips
                visible: cell.status !== ""
                anchors.verticalCenter: parent.verticalCenter
                Chip {
                    text: cell.status === "offline" ? "OFFLINE" : cell.status === "returned" ? "BACK" : "NEW"
                    tone: cell.status === "offline" ? "neutral" : "success"
                }
            }
        }

        MouseArea {
            id: mouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: cell.activated()
            onDoubleClicked: cell.opened()
        }
    }
}
