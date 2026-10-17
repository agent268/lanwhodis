import QtQuick

// Boxed section with a letter-spaced uppercase title (the Properties-dialog look from steamos-fm).
Rectangle {
    id: box

    property string title: ""
    default property alias content: body.data

    implicitHeight: col.implicitHeight + Theme.pad * 2
    color: Theme.sectionSurface
    border.color: Theme.sectionBorder
    border.width: 1
    radius: Theme.radius

    Column {
        id: col
        x: Theme.pad * 1.3
        y: Theme.pad
        width: parent.width - Theme.pad * 2.6
        spacing: Theme.pad * 0.7

        Text {
            visible: box.title !== ""
            text: box.title
            color: Theme.textDim
            font.pixelSize: Theme.fontSizeSm
            font.bold: true
            font.letterSpacing: Theme.unit * 0.08
        }
        Column {
            id: body
            width: parent.width
            spacing: Theme.pad * 0.5
        }
    }
}
