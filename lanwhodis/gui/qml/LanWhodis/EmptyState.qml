import QtQuick

// Centered hero used before the first scan, while the first results arrive, and when filters match nothing.
Item {
    id: root

    property string iconName: "ui_scan"
    property color tint: Theme.accent
    property string title: ""
    property string subtitle: ""
    property string buttonText: ""
    property string buttonIcon: ""
    property bool busy: false
    signal action()

    Column {
        anchors.centerIn: parent
        width: Math.min(parent.width - Theme.unit * 4, Theme.unit * 26)
        spacing: Theme.unit * 0.9

        Item {
            anchors.horizontalCenter: parent.horizontalCenter
            width: Theme.unit * 7.5
            height: width

            Rectangle {                         // soft pulsing halo while busy
                id: halo
                anchors.centerIn: parent
                width: parent.width
                height: width
                radius: width / 2
                color: Theme.alpha(root.tint, 0.10)
                SequentialAnimation on scale {
                    running: root.busy
                    loops: Animation.Infinite
                    NumberAnimation { from: 1.0; to: 1.22; duration: 900; easing.type: Easing.InOutSine }
                    NumberAnimation { from: 1.22; to: 1.0; duration: 900; easing.type: Easing.InOutSine }
                }
            }
            Tile {
                anchors.centerIn: parent
                size: Theme.unit * 5.2
                iconName: root.iconName
                tileColor: root.tint
            }
        }
        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: root.title
            color: Theme.text
            font.pixelSize: Theme.fontSizeXl
            font.bold: true
        }
        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: root.subtitle
            color: Theme.textDim
            font.pixelSize: Theme.fontSize
            lineHeight: 1.15
        }
        LwButton {
            visible: root.buttonText !== ""
            anchors.horizontalCenter: parent.horizontalCenter
            primary: true
            text: root.buttonText
            iconName: root.buttonIcon
            onClicked: root.action()
        }
    }
}
