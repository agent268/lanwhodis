import QtQuick

// Footer: status message on the left, keyboard hints on the right (the same idea as steamos-fm's
// ButtonLegend, with key caps instead of gamepad glyphs).
Rectangle {
    id: bar

    property string message: ""
    property var hints: []          // [{key, label}]
    property bool compact: false

    implicitHeight: Theme.unit * 1.9
    color: Theme.alpha(Theme.bg, 0.6)

    Rectangle { width: parent.width; height: 1; color: Theme.divider }

    Text {
        anchors.left: parent.left
        anchors.leftMargin: Theme.unit * 0.9
        anchors.right: legend.left
        anchors.rightMargin: Theme.unit
        anchors.verticalCenter: parent.verticalCenter
        text: bar.message
        elide: Text.ElideRight
        color: Theme.textDim
        font.pixelSize: Theme.fontSizeSm
    }

    Row {
        id: legend
        visible: !bar.compact
        anchors.right: parent.right
        anchors.rightMargin: Theme.unit * 0.9
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.unit * 1.1
        Repeater {
            model: bar.hints
            delegate: Row {
                required property var modelData
                spacing: Theme.unit * 0.35
                anchors.verticalCenter: parent.verticalCenter
                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    implicitWidth: Math.max(Theme.unit * 1.2, keyText.implicitWidth + Theme.unit * 0.6)
                    width: implicitWidth
                    height: Theme.unit * 1.2
                    radius: Theme.radius * 0.5
                    color: Theme.alpha(Theme.text, 0.08)
                    border.width: 1
                    border.color: Theme.alpha(Theme.text, 0.22)
                    Text {
                        id: keyText
                        anchors.centerIn: parent
                        text: modelData.key
                        color: Theme.text
                        font.pixelSize: Theme.fontSizeSm * 0.92
                        font.bold: true
                    }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: modelData.label
                    color: Theme.textDim
                    font.pixelSize: Theme.fontSizeSm
                }
            }
        }
    }
}
