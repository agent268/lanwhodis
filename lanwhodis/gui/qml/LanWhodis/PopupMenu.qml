import QtQuick
import QtQuick.Controls

// Themed dropdown list. items: [{label, icon?, detail?}] (or plain strings). Emits chosen(index).
Popup {
    id: menu

    property var items: []
    property int currentIndex: -1
    property real minWidth: Theme.unit * 12
    signal chosen(int index)

    padding: Theme.unit * 0.35
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    width: Math.max(minWidth, list.widest + padding * 2)

    background: Rectangle {
        color: Theme.dialogSurface
        border.color: Theme.dialogBorder
        border.width: 1
        radius: Theme.radius
    }

    contentItem: Column {
        id: list
        spacing: 2
        readonly property real widest: {
            var w = 0
            for (var i = 0; i < children.length; ++i)
                w = Math.max(w, children[i].implicitWidth || 0)
            return w
        }
        Repeater {
            model: menu.items
            delegate: Rectangle {
                id: item
                required property var modelData
                required property int index
                readonly property string label: typeof modelData === "string" ? modelData : modelData.label
                readonly property string icon: typeof modelData === "string" ? "" : (modelData.icon || "")
                Accessible.role: Accessible.MenuItem
                Accessible.name: label
                Accessible.checkable: true
                Accessible.checked: menu.currentIndex === index
                Accessible.onPressAction: { menu.chosen(item.index); menu.close() }
                implicitWidth: rowItem.implicitWidth + Theme.unit * 1.2
                width: list.width
                height: Theme.unit * 1.9
                radius: Theme.radius * 0.7
                color: ma.containsMouse ? Theme.alpha(Theme.text, 0.10)
                     : menu.currentIndex === index ? Theme.alpha(Theme.accent, 0.18) : "transparent"
                Row {
                    id: rowItem
                    x: Theme.unit * 0.6
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Theme.unit * 0.5
                    Icon {
                        visible: item.icon !== ""
                        anchors.verticalCenter: parent.verticalCenter
                        name: item.icon; tint: Theme.textDim; size: Theme.fontSizeLg
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: item.label
                        color: Theme.text
                        font.pixelSize: Theme.fontSize
                    }
                }
                MouseArea {
                    id: ma
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: { menu.chosen(item.index); menu.close() }
                }
            }
        }
    }
}
