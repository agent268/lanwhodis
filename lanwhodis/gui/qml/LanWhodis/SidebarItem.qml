import QtQuick

// One row in the sidebar: tinted icon, label, count. `compact` shows the icon only.
Rectangle {
    id: item

    property string label: ""
    property string iconName: ""
    property color iconColor: Theme.textDim
    property int count: -1
    property bool selected: false
    property bool compact: false
    signal clicked()

    height: Theme.unit * 2.0
    radius: Theme.radius
    activeFocusOnTab: true
    color: selected ? Theme.alpha(Theme.accent, 0.20)
         : mouse.containsMouse ? Theme.alpha(Theme.text, 0.08) : "transparent"
    Behavior on color { ColorAnimation { duration: 90 } }
    Keys.onReturnPressed: item.clicked()
    Keys.onSpacePressed: item.clicked()

    Rectangle {                       // selection marker
        visible: item.selected
        width: Theme.unit * 0.18
        height: parent.height * 0.5
        radius: width / 2
        anchors.verticalCenter: parent.verticalCenter
        x: Theme.unit * 0.1
        color: Theme.accent
    }

    Icon {
        id: ic
        x: compact ? (parent.width - width) / 2 : Theme.unit * 0.7
        anchors.verticalCenter: parent.verticalCenter
        name: item.iconName
        tint: item.selected ? Theme.accent : item.iconColor
        size: Theme.fontSizeLg * 1.15
    }
    Text {
        visible: !item.compact
        anchors.left: ic.right
        anchors.leftMargin: Theme.unit * 0.55
        anchors.right: cnt.left
        anchors.rightMargin: Theme.unit * 0.3
        anchors.verticalCenter: parent.verticalCenter
        text: item.label
        elide: Text.ElideRight
        color: item.selected ? Theme.text : Theme.alpha(Theme.text, 0.85)
        font.pixelSize: Theme.fontSize
        font.bold: item.selected
    }
    Text {
        id: cnt
        visible: !item.compact && item.count >= 0
        anchors.right: parent.right
        anchors.rightMargin: Theme.unit * 0.7
        anchors.verticalCenter: parent.verticalCenter
        text: item.count
        color: Theme.textDim
        font.pixelSize: Theme.fontSizeSm
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: item.clicked()
    }
}
