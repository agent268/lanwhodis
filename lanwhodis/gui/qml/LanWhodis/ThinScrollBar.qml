import QtQuick
import QtQuick.Controls

// Slim, themed scrollbar (the stock one ignores Theme, same reason steamos-fm has FmScrollBar).
ScrollBar {
    id: bar
    policy: ScrollBar.AsNeeded
    minimumSize: 0.08
    padding: 2
    implicitWidth: Theme.unit * 0.5

    contentItem: Rectangle {
        implicitWidth: Theme.unit * 0.32
        radius: width / 2
        color: Theme.alpha(Theme.textDim, bar.pressed ? 0.85 : bar.hovered ? 0.65 : 0.4)
    }
    background: Item {}
}
