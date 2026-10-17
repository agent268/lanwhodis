import QtQuick
import QtQuick.Controls

// Modal editor for what LanWhodis thinks a device is. Corrections are remembered by MAC.
Item {
    id: dlg

    property var cur: ({})
    property string chosenType: ""          // "" = keep auto-detected
    signal saved(string sid, string name, string typeKey, string notes)
    signal reset(string sid)

    visible: false
    z: 100

    function openFor(current) {
        cur = current
        nameField.text = current.userName || ""
        notesField.text = current.notes || ""
        chosenType = current.userType || ""
        visible = true
        nameField.forceActiveFocus()
    }
    function close() { visible = false }

    // scrim (also swallows clicks so nothing behind the dialog is reachable)
    Rectangle {
        anchors.fill: parent
        color: Theme.scrim
        MouseArea { anchors.fill: parent; onClicked: dlg.close() }
    }

    Rectangle {
        id: box
        anchors.centerIn: parent
        width: Math.min(Theme.unit * 38, dlg.width - Theme.unit * 3)
        height: Math.min(col.implicitHeight + Theme.unit * 2.4, dlg.height - Theme.unit * 3)
        radius: Theme.radiusLg
        color: Theme.dialogSurface
        border.color: Theme.dialogBorder
        border.width: 1

        MouseArea { anchors.fill: parent }          // clicks inside must not reach the scrim

        Keys.onEscapePressed: dlg.close()
        focus: dlg.visible

        Flickable {
            anchors.fill: parent
            anchors.margins: Theme.unit * 1.1
            contentHeight: col.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ThinScrollBar {}

            Column {
                id: col
                width: parent.width - Theme.unit * 0.4
                spacing: Theme.unit * 0.9

                Row {
                    spacing: Theme.unit * 0.8
                    Tile { size: Theme.unit * 3; iconName: dlg.cur.iconName || ""; tileColor: dlg.cur.color || Theme.accent }
                    Column {
                        anchors.verticalCenter: parent.verticalCenter
                        Text { text: "Edit device"; color: Theme.text; font.pixelSize: Theme.fontSizeXl; font.bold: true }
                        Text {
                            text: (dlg.cur.ip || "") + "   " + (dlg.cur.mac || "no MAC")
                            color: Theme.textDim
                            font.pixelSize: Theme.fontSizeSm
                        }
                    }
                }

                Text { text: "NAME"; color: Theme.textDim; font.pixelSize: Theme.fontSizeSm; font.bold: true; font.letterSpacing: Theme.unit * 0.08 }
                Rectangle {
                    width: parent.width
                    height: Theme.unit * 2.2
                    radius: Theme.radius
                    color: Theme.inputSurface
                    border.width: 1
                    border.color: nameField.activeFocus ? Theme.accent : Theme.sectionBorder
                    TextInput {
                        id: nameField
                        anchors.fill: parent
                        anchors.leftMargin: Theme.unit * 0.7
                        anchors.rightMargin: Theme.unit * 0.7
                        verticalAlignment: TextInput.AlignVCenter
                        color: Theme.text
                        selectionColor: Theme.accent
                        font.pixelSize: Theme.fontSize
                        clip: true
                        selectByMouse: true
                        Text {
                            visible: nameField.text === "" && !nameField.activeFocus
                            anchors.verticalCenter: parent.verticalCenter
                            text: dlg.cur.name || "Name"
                            color: Theme.textDim
                            font.pixelSize: Theme.fontSize
                        }
                    }
                }

                Text { text: "TYPE"; color: Theme.textDim; font.pixelSize: Theme.fontSizeSm; font.bold: true; font.letterSpacing: Theme.unit * 0.08 }
                Flow {
                    width: parent.width
                    spacing: Theme.unit * 0.4
                    // first option: keep what the scanner says
                    Rectangle {
                        height: Theme.unit * 1.8
                        width: autoRow.implicitWidth + Theme.unit * 1.1
                        radius: height / 2
                        color: dlg.chosenType === "" ? Theme.alpha(Theme.accent, 0.25) : Theme.alpha(Theme.text, 0.06)
                        border.width: 1
                        border.color: dlg.chosenType === "" ? Theme.accent : Theme.alpha(Theme.text, 0.15)
                        Row {
                            id: autoRow
                            anchors.centerIn: parent
                            spacing: Theme.unit * 0.3
                            Icon { name: "ui_sync"; tint: Theme.text; size: Theme.fontSize * 1.2; anchors.verticalCenter: parent.verticalCenter }
                            Text { text: "Auto-detected"; color: Theme.text; font.pixelSize: Theme.fontSizeSm; anchors.verticalCenter: parent.verticalCenter }
                        }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: dlg.chosenType = "" }
                    }
                    Repeater {
                        model: backend.deviceTypes
                        delegate: Rectangle {
                            required property var modelData
                            height: Theme.unit * 1.8
                            width: tRow.implicitWidth + Theme.unit * 1.1
                            radius: height / 2
                            readonly property bool on: dlg.chosenType === modelData.key
                            color: on ? Theme.alpha(modelData.color, 0.28) : Theme.alpha(Theme.text, 0.06)
                            border.width: 1
                            border.color: on ? modelData.color : Theme.alpha(Theme.text, 0.15)
                            Row {
                                id: tRow
                                anchors.centerIn: parent
                                spacing: Theme.unit * 0.3
                                Icon { name: modelData.icon; tint: modelData.color; size: Theme.fontSize * 1.2; anchors.verticalCenter: parent.verticalCenter }
                                Text { text: modelData.label; color: Theme.text; font.pixelSize: Theme.fontSizeSm; anchors.verticalCenter: parent.verticalCenter }
                            }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: dlg.chosenType = modelData.key }
                        }
                    }
                }

                Text { text: "NOTES"; color: Theme.textDim; font.pixelSize: Theme.fontSizeSm; font.bold: true; font.letterSpacing: Theme.unit * 0.08 }
                Rectangle {
                    width: parent.width
                    height: Theme.unit * 4.6
                    radius: Theme.radius
                    color: Theme.inputSurface
                    border.width: 1
                    border.color: notesField.activeFocus ? Theme.accent : Theme.sectionBorder
                    TextEdit {
                        id: notesField
                        anchors.fill: parent
                        anchors.margins: Theme.unit * 0.6
                        color: Theme.text
                        selectionColor: Theme.accent
                        font.pixelSize: Theme.fontSize
                        wrapMode: TextEdit.Wrap
                        selectByMouse: true
                        clip: true
                        Text {
                            visible: notesField.text === "" && !notesField.activeFocus
                            text: "Location, owner, what it controls…"
                            color: Theme.textDim
                            font.pixelSize: Theme.fontSize
                        }
                    }
                }

                Row {
                    width: parent.width
                    spacing: Theme.unit * 0.5
                    LwButton {
                        visible: !!dlg.cur.userType || !!dlg.cur.userName || !!dlg.cur.notes
                        text: "Reset to auto-detected"
                        danger: false
                        iconName: "ui_arrow_sync"
                        onClicked: { dlg.reset(dlg.cur.sid); dlg.close() }
                    }
                    Item { width: Math.max(0, parent.width - actions.width - (parent.children[0].visible ? parent.children[0].width + parent.spacing : 0) - parent.spacing); height: 1 }
                    Row {
                        id: actions
                        spacing: Theme.unit * 0.5
                        LwButton { text: "Cancel"; ghost: true; onClicked: dlg.close() }
                        LwButton {
                            text: "Save"
                            primary: true
                            iconName: "ui_check"
                            onClicked: { dlg.saved(dlg.cur.sid, nameField.text, dlg.chosenType, notesField.text); dlg.close() }
                        }
                    }
                }
            }
        }
    }
}
