import QtQuick
import QtQuick.Controls

// Right-hand panel: who/what the selected device is, quick actions, then boxed sections.
Rectangle {
    id: panel

    property var cur: ({})          // backend.current
    readonly property bool has: cur.sid !== undefined && cur.sid !== ""
    signal editRequested()
    signal openWeb(string url)
    signal copyRequested(string text)

    color: Theme.surface
    Rectangle { width: 1; height: parent.height; color: Theme.divider }

    // ── empty placeholder ─────────────────────────────────────────
    Column {
        visible: !panel.has
        anchors.centerIn: parent
        width: parent.width - Theme.unit * 3
        spacing: Theme.unit * 0.8
        Tile {
            anchors.horizontalCenter: parent.horizontalCenter
            size: Theme.unit * 4.2
            iconName: "ui_info"
            tileColor: Theme.textDim
        }
        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: "Select a device to see what it is, why LanWhodis thinks so, and what it offers."
            color: Theme.textDim
            font.pixelSize: Theme.fontSize
            lineHeight: 1.15
        }
    }

    Flickable {
        id: flick
        visible: panel.has
        anchors.fill: parent
        anchors.leftMargin: 1
        contentWidth: width
        contentHeight: panelColumn.implicitHeight + Theme.unit * 1.6
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ThinScrollBar {}

        Column {
            id: panelColumn      // not `content`: SectionBox has a default property of that name
            
            x: Theme.unit * 0.9
            y: Theme.unit * 0.9
            width: flick.width - Theme.unit * 1.8 - (flick.ScrollBar.vertical.visible ? Theme.unit * 0.4 : 0)
            spacing: Theme.unit * 0.8

            // header: tile + name + type + confidence
            Row {
                width: parent.width
                spacing: Theme.unit * 0.8
                Tile {
                    id: bigTile
                    size: Theme.unit * 4.4
                    iconName: panel.cur.iconName || ""
                    tileColor: panel.cur.color || Theme.accent
                    dim: !!panel.cur.offline
                }
                Column {
                    width: parent.width - bigTile.width - parent.spacing
                    anchors.verticalCenter: bigTile.verticalCenter
                    spacing: Theme.unit * 0.25
                    Text {
                        width: parent.width
                        text: panel.cur.name || ""
                        wrapMode: Text.Wrap
                        maximumLineCount: 2
                        elide: Text.ElideRight
                        color: Theme.text
                        font.pixelSize: Theme.fontSizeXl * 0.92
                        font.bold: true
                    }
                    Flow {
                        width: parent.width
                        spacing: Theme.unit * 0.35
                        Chip { text: panel.cur.typeLabel || ""; tone: "custom"; customColor: panel.cur.color || Theme.accent }
                        Chip {
                            visible: !panel.cur.offline
                            text: Math.round((panel.cur.confidence || 0) * 100) + "% sure"
                            tone: (panel.cur.confidence || 0) >= 0.8 ? "success" : (panel.cur.confidence || 0) >= 0.5 ? "warning" : "danger"
                        }
                        Chip { visible: !!panel.cur.offline; text: "OFFLINE" }
                        Chip { visible: panel.cur.status === "new"; text: "NEW"; tone: "success" }
                        Chip { visible: panel.cur.status === "returned"; text: "BACK"; tone: "success" }
                    }
                }
            }

            // actions
            Flow {
                width: parent.width
                spacing: Theme.unit * 0.45
                LwButton {
                    visible: (panel.cur.webUrl || "") !== ""
                    primary: true
                    text: "Open web UI"
                    iconName: "ui_open"
                    onClicked: panel.openWeb(panel.cur.webUrl)
                }
                LwButton {
                    visible: !!panel.cur.editable
                    text: "Edit"
                    iconName: "ui_edit"
                    onClicked: panel.editRequested()
                }
                LwButton {
                    text: "Copy IP"
                    iconName: "ui_copy"
                    onClicked: panel.copyRequested(panel.cur.ip)
                }
                LwButton {
                    visible: (panel.cur.mac || "") !== ""
                    text: "Copy MAC"
                    iconName: "ui_copy"
                    ghost: true
                    onClicked: panel.copyRequested(panel.cur.mac)
                }
            }

            // history / corrections banners
            Rectangle {
                visible: (panel.cur.history || "") !== ""
                width: parent.width
                implicitHeight: histText.implicitHeight + Theme.pad * 1.6
                radius: Theme.radius
                color: Theme.alpha(Theme.accent, 0.10)
                border.color: Theme.alpha(Theme.accent, 0.30)
                Row {
                    x: Theme.pad
                    y: Theme.pad * 0.8
                    width: parent.width - Theme.pad * 2
                    spacing: Theme.unit * 0.5
                    Icon { name: "ui_history"; tint: Theme.accent; size: Theme.fontSizeLg }
                    Text {
                        id: histText
                        width: parent.width - Theme.fontSizeLg - parent.spacing
                        text: panel.cur.history || ""
                        wrapMode: Text.Wrap
                        color: Theme.text
                        font.pixelSize: Theme.fontSizeSm
                    }
                }
            }
            Rectangle {
                visible: (panel.cur.autoLine || "") !== "" || (panel.cur.notes || "") !== ""
                width: parent.width
                implicitHeight: edText.implicitHeight + Theme.pad * 1.6
                radius: Theme.radius
                color: Theme.alpha(Theme.warning, 0.10)
                border.color: Theme.alpha(Theme.warning, 0.30)
                Text {
                    id: edText
                    x: Theme.pad
                    y: Theme.pad * 0.8
                    width: parent.width - Theme.pad * 2
                    wrapMode: Text.Wrap
                    text: [panel.cur.autoLine, panel.cur.notes ? "Notes: " + panel.cur.notes : ""].filter(Boolean).join("\n")
                    color: Theme.text
                    font.pixelSize: Theme.fontSizeSm
                }
            }

            // sections
            Repeater {
                model: panel.cur.sections || []
                delegate: SectionBox {
                    required property var modelData
                    width: panelColumn.width
                    title: modelData.title

                    // key / value rows
                    Repeater {
                        model: modelData.rows || []
                        delegate: Item {
                            required property var modelData
                            width: parent.width
                            height: Math.max(kText.implicitHeight, vText.implicitHeight)
                            Text {
                                id: kText
                                width: parent.width * 0.34
                                text: modelData.k
                                color: Theme.textDim
                                font.pixelSize: Theme.fontSizeSm
                                wrapMode: Text.Wrap
                            }
                            TextEdit {
                                id: vText
                                x: parent.width * 0.36
                                width: parent.width * 0.64
                                text: modelData.v
                                readOnly: true
                                selectByMouse: true
                                wrapMode: TextEdit.Wrap
                                color: Theme.text
                                selectionColor: Theme.accent
                                font.pixelSize: Theme.fontSizeSm
                            }
                        }
                    }
                    // grouped service lists
                    Repeater {
                        model: modelData.groups || []
                        delegate: Column {
                            required property var modelData
                            width: parent.width
                            spacing: Theme.unit * 0.15
                            Text {
                                text: modelData.title
                                color: Theme.accent
                                font.pixelSize: Theme.fontSizeSm
                                font.bold: true
                            }
                            Repeater {
                                model: modelData.items
                                delegate: Text {
                                    required property string modelData
                                    width: parent.width
                                    leftPadding: Theme.unit * 0.6
                                    text: modelData
                                    wrapMode: Text.WrapAnywhere
                                    color: Theme.text
                                    font.pixelSize: Theme.fontSizeSm
                                }
                            }
                        }
                    }
                    // evidence with a weight bar
                    Repeater {
                        model: modelData.evidence || []
                        delegate: Item {
                            required property var modelData
                            width: parent.width
                            height: evText.implicitHeight + Theme.unit * 0.5
                            Text {
                                id: evText
                                width: parent.width - barBg.width - Theme.unit * 0.6
                                text: modelData.source + " → " + modelData.text
                                wrapMode: Text.Wrap
                                color: Theme.text
                                font.pixelSize: Theme.fontSizeSm
                            }
                            Rectangle {
                                id: barBg
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.topMargin: Theme.unit * 0.25
                                width: Theme.unit * 3
                                height: Theme.unit * 0.4
                                radius: height / 2
                                color: Theme.alpha(Theme.text, 0.10)
                                Rectangle {
                                    width: parent.width * Math.max(0.05, Math.min(1, modelData.weight))
                                    height: parent.height
                                    radius: height / 2
                                    color: Theme.accent
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
