import QtQuick

// Pill-shaped icon toggle group, e.g. grid / list view. options: [{key, icon, tip}]
Rectangle {
    id: seg

    property var options: []
    property string current: ""
    signal picked(string key)

    implicitHeight: Theme.unit * 2.1
    implicitWidth: row.implicitWidth + Theme.unit * 0.4
    radius: Theme.radius
    color: Theme.inputSurface
    border.width: 1
    border.color: Theme.sectionBorder

    Row {
        id: row
        anchors.centerIn: parent
        spacing: Theme.unit * 0.1
        Repeater {
            model: seg.options
            delegate: IconButton {
                required property var modelData
                iconName: modelData.icon
                tooltip: modelData.tip
                active: seg.current === modelData.key
                size: Theme.unit * 1.75
                onClicked: seg.picked(modelData.key)
            }
        }
    }
}
