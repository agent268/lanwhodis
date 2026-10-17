import QtQuick

// Rounded search box with a leading icon and a clear button.
Rectangle {
    id: field

    property alias text: input.text
    property string placeholder: "Search devices"
    signal edited(string text)

    Accessible.role: Accessible.EditableText
    Accessible.name: field.placeholder

    function focusField() { input.forceActiveFocus(); input.selectAll() }

    implicitHeight: Theme.unit * 2.1
    implicitWidth: Theme.unit * 16
    radius: height / 2
    color: Theme.inputSurface
    border.width: 1
    border.color: input.activeFocus ? Theme.accent : Theme.sectionBorder
    Behavior on border.color { ColorAnimation { duration: Theme.dur(100) } }

    Icon {
        id: lead
        anchors.left: parent.left
        anchors.leftMargin: Theme.unit * 0.7
        anchors.verticalCenter: parent.verticalCenter
        name: "ui_search"
        tint: Theme.textDim
        size: Theme.fontSizeLg
    }

    TextInput {
        id: input
        anchors.left: lead.right
        anchors.leftMargin: Theme.unit * 0.5
        anchors.right: clear.left
        anchors.rightMargin: Theme.unit * 0.3
        anchors.verticalCenter: parent.verticalCenter
        color: Theme.text
        selectionColor: Theme.accent
        selectedTextColor: "#ffffff"
        font.pixelSize: Theme.fontSize
        clip: true
        selectByMouse: true
        onTextChanged: field.edited(text)
        Keys.onEscapePressed: { text = ""; focus = false }

        Text {
            visible: input.text === "" && !input.activeFocus
            anchors.verticalCenter: parent.verticalCenter
            text: field.placeholder
            color: Theme.textDim
            font.pixelSize: Theme.fontSize
        }
    }

    Item {
        id: clear
        anchors.right: parent.right
        anchors.rightMargin: Theme.unit * 0.5
        anchors.verticalCenter: parent.verticalCenter
        width: Theme.unit * 1.2
        height: width
        visible: input.text !== ""
        Icon { anchors.centerIn: parent; name: "ui_close"; tint: Theme.textDim; size: Theme.fontSize }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: input.text = "" }
    }
}
