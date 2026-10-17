import QtQuick

// A device as a dense row in the list view. Used as a ListView delegate (roles are required properties).
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

    height: Theme.unit * 2.9

    Rectangle {
        anchors.fill: parent
        anchors.topMargin: 1
        anchors.bottomMargin: 1
        radius: Theme.radius
        color: cell.selected ? Theme.selected
             : mouse.containsMouse ? Theme.surfaceAlt : (cell.index % 2 === 0 ? "transparent" : Theme.alpha(Theme.surface, 0.5))
        border.width: cell.selected ? 1 : 0
        border.color: Theme.accent
        Behavior on color { ColorAnimation { duration: Theme.dur(90) } }

        Tile {
            id: tile
            x: Theme.unit * 0.6
            anchors.verticalCenter: parent.verticalCenter
            size: Theme.unit * 2.1
            iconName: cell.iconName
            tileColor: cell.color
            glyphColor: Theme.labelColor(cell.labelDark, cell.labelLight)
            dim: cell.offline
        }

        Row {
            anchors.left: tile.right
            anchors.leftMargin: Theme.unit * 0.8
            anchors.right: parent.right
            anchors.rightMargin: Theme.unit * 0.8
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.unit * 0.6

            readonly property real w: width - spacing * 4
            Text {
                width: parent.w * 0.30
                text: cell.name
                elide: Text.ElideRight
                color: cell.offline ? Theme.textDim : Theme.text
                font.pixelSize: Theme.fontSize
                font.bold: true
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                width: parent.w * 0.16
                text: cell.typeLabel + (cell.edited ? " ✎" : "")
                elide: Text.ElideRight
                color: Theme.alpha(Theme.labelColor(cell.labelDark, cell.labelLight), cell.offline ? 0.7 : 1.0)
                font.pixelSize: Theme.fontSize
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                width: parent.w * 0.14
                text: cell.ip
                elide: Text.ElideRight
                color: Theme.textDim
                font.pixelSize: Theme.fontSizeSm
                font.family: "monospace"
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                width: parent.w * 0.22
                text: cell.vendor
                elide: Text.ElideRight
                color: Theme.textDim
                font.pixelSize: Theme.fontSizeSm
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                width: parent.w * 0.18 - (chip.visible ? chip.width + parent.spacing : 0)
                text: cell.os
                elide: Text.ElideRight
                color: Theme.textDim
                font.pixelSize: Theme.fontSizeSm
                anchors.verticalCenter: parent.verticalCenter
            }
            Chip {
                id: chip
                visible: cell.status !== ""
                anchors.verticalCenter: parent.verticalCenter
                text: cell.status === "offline" ? "OFFLINE" : cell.status === "returned" ? "BACK" : "NEW"
                tone: cell.status === "offline" ? "neutral" : "success"
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
