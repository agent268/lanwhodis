import QtQuick

// Theme-aware push button (same role as steamos-fm's FmButton): primary = solid accent, danger = red,
// ghost = borderless, default = raised surface. Optional leading icon. Keyboard focusable.
Rectangle {
    id: btn

    property string text: ""
    property string iconName: ""
    property bool primary: false
    property bool danger: false
    property bool ghost: false
    property string tooltip: ""
    property bool compact: false
    readonly property bool hovered: mouse.containsMouse

    signal clicked()

    readonly property color _base: danger ? Theme.danger
                                 : primary ? Theme.accent
                                 : ghost ? "transparent" : Theme.buttonSurface
    readonly property color _fg: (primary || danger) ? "#ffffff" : Theme.text

    implicitHeight: Theme.unit * (compact ? 1.7 : 2.1)
    implicitWidth: row.implicitWidth + Theme.unit * (compact ? 1.0 : 1.5)
    radius: Theme.radius
    activeFocusOnTab: true
    opacity: enabled ? 1.0 : 0.4
    color: !enabled ? _base
         : mouse.pressed ? Qt.darker(_base === "transparent" ? Theme.buttonSurface : _base, 1.18)
         : mouse.containsMouse ? (ghost ? Theme.alpha(Theme.text, 0.10) : Qt.lighter(_base, 1.14))
         : _base
    border.width: ghost ? 0 : 1
    border.color: activeFocus ? Theme.text
                 : (primary || danger) ? Qt.darker(_base, 1.15) : Theme.buttonBorder
    Behavior on color { ColorAnimation { duration: 90 } }

    Keys.onReturnPressed: btn.clicked()
    Keys.onEnterPressed: btn.clicked()
    Keys.onSpacePressed: btn.clicked()

    Row {
        id: row
        anchors.centerIn: parent
        spacing: Theme.unit * 0.45
        Icon {
            visible: btn.iconName !== ""
            anchors.verticalCenter: parent.verticalCenter
            name: btn.iconName
            tint: btn._fg
            size: Theme.fontSizeLg * 1.1
        }
        Text {
            visible: btn.text !== ""
            anchors.verticalCenter: parent.verticalCenter
            text: btn.text
            color: btn._fg
            font.pixelSize: Theme.fontSize
            font.bold: btn.primary || btn.danger
        }
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
