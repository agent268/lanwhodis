import QtQuick

// Square icon-only button with a hover tooltip. `active` shows a toggled/selected state.
Rectangle {
    id: btn

    property string iconName: ""
    property string tooltip: ""
    property bool active: false
    property real size: Theme.unit * 2.1
    readonly property bool hovered: mouse.containsMouse

    signal clicked()

    implicitWidth: size
    implicitHeight: size
    radius: Theme.radius
    activeFocusOnTab: true
    opacity: enabled ? 1.0 : 0.4
    color: active ? Theme.alpha(Theme.accent, 0.22)
         : mouse.pressed ? Theme.alpha(Theme.text, 0.16)
         : mouse.containsMouse ? Theme.alpha(Theme.text, 0.10) : "transparent"
    border.width: activeFocus ? 1 : 0
    border.color: Theme.text
    Behavior on color { ColorAnimation { duration: 90 } }

    Keys.onReturnPressed: btn.clicked()
    Keys.onSpacePressed: btn.clicked()

    Icon {
        anchors.centerIn: parent
        name: btn.iconName
        tint: btn.active ? Theme.accent : Theme.text
        size: btn.size * 0.55
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: btn.clicked()
    }

    Rectangle {
        visible: btn.tooltip !== "" && mouse.containsMouse
        z: 1000
        anchors.top: parent.bottom
        anchors.topMargin: Theme.pad * 0.5
        anchors.horizontalCenter: parent.horizontalCenter
        radius: Theme.radius * 0.6
        color: Theme.dialogSurface
        border.color: Theme.dialogBorder
        implicitWidth: tipText.implicitWidth + Theme.pad * 1.6
        implicitHeight: tipText.implicitHeight + Theme.pad
        Text {
            id: tipText
            anchors.centerIn: parent
            text: btn.tooltip
            color: Theme.text
            font.pixelSize: Theme.fontSizeSm
        }
    }
}
