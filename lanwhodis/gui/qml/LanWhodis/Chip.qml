import QtQuick

// Small pill label. tone: neutral | accent | success | warning | danger | custom (uses `color`).
Rectangle {
    id: chip

    property string text: ""
    property string iconName: ""
    property string tone: "neutral"
    property color customColor: Theme.textDim

    readonly property color _tone: tone === "accent" ? Theme.accent
                                 : tone === "success" ? Theme.success
                                 : tone === "warning" ? Theme.warning
                                 : tone === "danger" ? Theme.danger
                                 : tone === "custom" ? customColor : Theme.textDim

    implicitHeight: Theme.unit * 1.3
    implicitWidth: content.implicitWidth + Theme.unit * 0.9
    radius: height / 2
    color: Theme.alpha(_tone, 0.16)
    border.width: 1
    border.color: Theme.alpha(_tone, 0.35)

    Row {
        id: content
        anchors.centerIn: parent
        spacing: Theme.unit * 0.25
        Icon {
            visible: chip.iconName !== ""
            anchors.verticalCenter: parent.verticalCenter
            name: chip.iconName
            tint: chip._tone
            size: Theme.fontSizeSm * 1.2
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: chip.text
            color: chip._tone
            font.pixelSize: Theme.fontSizeSm
            font.bold: true
        }
    }
}
