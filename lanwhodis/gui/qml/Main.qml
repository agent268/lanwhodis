import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import QtCore
import LanWhodis 1.0

ApplicationWindow {
    id: win
    width: 1380
    height: 860
    minimumWidth: 900
    minimumHeight: 580
    visible: true
    title: "LanWhodis"
    color: Theme.bg

    Binding { target: Theme; property: "mode"; value: backend.theme }
    Binding { target: Theme; property: "zoom"; value: backend.zoom }
    Binding { target: Theme; property: "reduceMotion"; value: backend.reduceMotion }

    readonly property bool compactSide: width < 1120
    readonly property bool narrow: width < 1000
    readonly property var themeIcons: ({ "dark": "ui_moon", "light": "ui_sun", "deck": "ui_theme" })
    readonly property var statusCounts: backend.statusCounts

    // ── shortcuts (plain letters are ignored while a text field has focus) ─────────
    Shortcut { sequences: ["F5", "Ctrl+R"]; onActivated: backend.toggleScan() }
    Shortcut { sequence: "Ctrl+F"; onActivated: search.focusField() }
    Shortcut { sequence: "Ctrl+E"; onActivated: if (backend.hasDevices) exportMenu.open() }
    Shortcut { sequence: "Ctrl+T"; onActivated: backend.cycleTheme() }
    Shortcut { sequences: ["Ctrl+=", "Ctrl++"]; onActivated: backend.zoom = backend.zoom + 0.1 }
    Shortcut { sequence: "Ctrl+-"; onActivated: backend.zoom = backend.zoom - 0.1 }
    Shortcut { sequence: "Ctrl+0"; onActivated: backend.zoom = 1.0 }
    Shortcut { sequence: "O"; enabled: !editDlg.visible; onActivated: if (backend.current.webUrl) backend.openUrl(backend.current.webUrl) }
    Shortcut { sequence: "E"; enabled: !editDlg.visible; onActivated: backend.requestEdit() }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── header ────────────────────────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: Theme.unit * 3.6
            color: Theme.surface

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Theme.unit * 0.9
                anchors.rightMargin: Theme.unit * 0.9
                spacing: Theme.unit * 0.6

                Tile { size: Theme.unit * 2.4; iconName: "ui_scan"; tileColor: Theme.accent }
                Column {
                    visible: !win.narrow
                    Text { text: "LanWhodis"; color: Theme.text; font.pixelSize: Theme.fontSizeLg; font.bold: true }
                    Text { text: "who's on your network?"; color: Theme.textDim; font.pixelSize: Theme.fontSizeSm }
                }

                // network picker
                Rectangle {
                    id: netPill
                    Accessible.role: Accessible.ComboBox
                    Accessible.name: "Network to scan: " + (backend.interfaceLabels.length ? backend.interfaceLabels[backend.interfaceIndex] : "none")
                    Layout.leftMargin: Theme.unit * 0.6
                    Layout.maximumWidth: Theme.unit * 17
                    implicitHeight: Theme.unit * 2.1
                    implicitWidth: pillRow.implicitWidth + Theme.unit * 1.2
                    radius: height / 2
                    color: pillMouse.containsMouse ? Theme.alpha(Theme.text, 0.10) : Theme.alpha(Theme.text, 0.06)
                    border.width: 1
                    border.color: Theme.alpha(Theme.text, 0.18)
                    Row {
                        id: pillRow
                        anchors.centerIn: parent
                        spacing: Theme.unit * 0.4
                        Icon { name: "ui_wifi"; tint: Theme.accent; size: Theme.fontSizeLg; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            width: Math.min(implicitWidth, Theme.unit * 12.5)
                            elide: Text.ElideRight
                            text: backend.interfaceLabels.length ? backend.interfaceLabels[backend.interfaceIndex] : "No network"
                            color: Theme.text
                            font.pixelSize: Theme.fontSizeSm
                        }
                        Icon {
                            visible: backend.interfaceLabels.length > 1
                            name: "ui_chevron_down"; tint: Theme.textDim; size: Theme.fontSizeSm * 1.3
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    MouseArea {
                        id: pillMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        enabled: backend.interfaceLabels.length > 1 && !backend.scanning
                        cursorShape: Qt.PointingHandCursor
                        onClicked: ifaceMenu.open()
                    }
                    PopupMenu {
                        id: ifaceMenu
                        y: netPill.height + Theme.unit * 0.3
                        items: backend.interfaceLabels.map(function (l) { return { label: l, icon: "ui_wifi" } })
                        currentIndex: backend.interfaceIndex
                        onChosen: function (i) { backend.interfaceIndex = i }
                    }
                }

                Item { Layout.fillWidth: true }

                SearchField {
                    id: search
                    Layout.preferredWidth: Theme.unit * (win.narrow ? 11 : 17)
                    onEdited: function (t) { backend.setSearch(t) }
                }
                Segmented {
                    options: [{ key: "grid", icon: "ui_grid", tip: "Cards" }, { key: "list", icon: "ui_list", tip: "List" }]
                    current: backend.view
                    onPicked: function (k) { backend.view = k }
                }
                IconButton {
                    iconName: "ui_export"
                    tooltip: "Export results"
                    enabled: backend.hasDevices
                    onClicked: exportMenu.open()
                    PopupMenu {
                        id: exportMenu
                        y: parent.height + Theme.unit * 0.3
                        x: parent.width - width
                        items: backend.exportFormats().map(function (f) { return { label: f.label, icon: "ui_export" } })
                        onChosen: function (i) {
                            var f = backend.exportFormats()[i]
                            saveDlg.fmt = f.fmt
                            saveDlg.fmtLabel = f.label
                            saveDlg.open()
                        }
                    }
                }
                IconButton {
                    iconName: win.themeIcons[backend.theme]
                    tooltip: "Theme: " + backend.theme + " (click to change)"
                    onClicked: backend.cycleTheme()
                }
                LwButton {
                    primary: !backend.scanning
                    danger: backend.scanning
                    text: backend.scanning ? "Stop" : "Scan network"
                    iconName: backend.scanning ? "ui_stop" : "ui_scan"
                    onClicked: backend.toggleScan()
                }
            }
        }

        // progress line
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 2
            color: Theme.divider
            Rectangle {
                visible: backend.scanning
                height: parent.height
                color: Theme.accent
                width: Math.max(parent.width * backend.progress, parent.width * 0.06)
                Behavior on width { NumberAnimation { duration: Theme.dur(300) } }
                SequentialAnimation on opacity {
                    running: backend.scanning && !Theme.reduceMotion
                    loops: Animation.Infinite
                    NumberAnimation { from: 1.0; to: 0.45; duration: Theme.dur(700) }
                    NumberAnimation { from: 0.45; to: 1.0; duration: Theme.dur(700) }
                }
            }
        }

        // ── body ──────────────────────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // sidebar
            Rectangle {
                Layout.preferredWidth: win.compactSide ? Theme.unit * 3.6 : Theme.unit * 11.5
                Layout.fillHeight: true
                color: Theme.bg
                Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Theme.divider }

                Flickable {
                    anchors.fill: parent
                    anchors.margins: Theme.unit * 0.5
                    contentHeight: side.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds

                    Column {
                        id: side
                        width: parent.width
                        spacing: Theme.unit * 0.12

                        Text {
                            visible: !win.compactSide
                            leftPadding: Theme.unit * 0.5
                            bottomPadding: Theme.unit * 0.2
                            text: "BROWSE"
                            color: Theme.textDim
                            font.pixelSize: Theme.fontSizeSm
                            font.bold: true
                            font.letterSpacing: Theme.unit * 0.08
                        }
                        Repeater {
                            model: backend.categories
                            delegate: SidebarItem {
                                required property var modelData
                                width: side.width
                                compact: win.compactSide
                                label: modelData.label
                                iconName: modelData.icon
                                iconColor: modelData.color !== "" ? Theme.labelColor(modelData.labelDark, modelData.labelLight) : Theme.textDim
                                count: modelData.count
                                selected: backend.category === modelData.key
                                onClicked: backend.setCategory(modelData.key)
                            }
                        }

                        Item { width: 1; height: Theme.unit * 0.6 }
                        Text {
                            visible: !win.compactSide
                            leftPadding: Theme.unit * 0.5
                            bottomPadding: Theme.unit * 0.2
                            text: "FILTERS"
                            color: Theme.textDim
                            font.pixelSize: Theme.fontSizeSm
                            font.bold: true
                            font.letterSpacing: Theme.unit * 0.08
                        }
                        SidebarItem {
                            width: side.width
                            compact: win.compactSide
                            label: "New or back"
                            iconName: "ui_star"
                            iconColor: Theme.success
                            count: win.statusCounts.new
                            selected: backend.statusFilter === "new"
                            onClicked: backend.setStatusFilter("new")
                        }
                        SidebarItem {
                            width: side.width
                            compact: win.compactSide
                            label: "Offline"
                            iconName: "ui_history"
                            iconColor: Theme.textDim
                            count: win.statusCounts.offline
                            selected: backend.statusFilter === "offline"
                            onClicked: backend.setStatusFilter("offline")
                        }
                        SidebarItem {
                            width: side.width
                            compact: win.compactSide
                            label: backend.showOffline ? "Hide offline" : "Show offline"
                            iconName: backend.showOffline ? "ui_eye_off" : "ui_eye"
                            iconColor: Theme.textDim
                            onClicked: backend.setShowOffline(!backend.showOffline)
                        }
                    }
                }
            }

            // content
            Item {
                id: content
                Layout.fillWidth: true
                Layout.fillHeight: true
                readonly property int shown: backend.view === "grid" ? grid.count : list.count

                EmptyState {
                    anchors.fill: parent
                    visible: !backend.hasDevices && !backend.scanning
                    iconName: "ui_scan"
                    title: "Find out who's on your network"
                    subtitle: "LanWhodis looks for every phone, TV, camera, plug and printer around you, and works out what each one is. It only looks - nothing is changed or logged in to."
                    buttonText: "Scan network"
                    buttonIcon: "ui_scan"
                    onAction: backend.startScan()
                }
                EmptyState {
                    anchors.fill: parent
                    visible: !backend.hasDevices && backend.scanning
                    busy: true
                    iconName: "ui_scan"
                    title: "Looking around…"
                    subtitle: backend.status
                }
                EmptyState {
                    anchors.fill: parent
                    visible: backend.hasDevices && content.shown === 0
                    iconName: "ui_filter"
                    tint: Theme.textDim
                    title: "Nothing matches"
                    subtitle: "No device fits the current search and filters."
                    buttonText: "Clear filters"
                    onAction: { search.text = ""; backend.setCategory(""); if (backend.statusFilter !== "") backend.setStatusFilter(backend.statusFilter) }
                }

                GridView {
                    id: grid
                    anchors.fill: parent
                    anchors.margins: Theme.unit * 0.5
                    visible: backend.hasDevices && backend.view === "grid"
                    readonly property int cols: Math.max(1, Math.floor(width / (Theme.unit * 14)))
                    cellWidth: Math.floor(width / cols)
                    cellHeight: Theme.unit * 6.4
                    clip: true
                    model: backend.devices
                    keyNavigationEnabled: true
                    currentIndex: -1
                    highlightFollowsCurrentItem: false
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ThinScrollBar {}
                    onCurrentIndexChanged: if (currentItem) backend.select(currentItem.sid)
                    delegate: DeviceCard {
                        width: grid.cellWidth
                        height: grid.cellHeight
                        selected: backend.current.sid === sid
                        onActivated: { grid.currentIndex = index; backend.select(sid) }
                        onOpened: { backend.select(sid); if (backend.current.webUrl) backend.openUrl(backend.current.webUrl) }
                    }
                }

                ListView {
                    id: list
                    anchors.fill: parent
                    anchors.margins: Theme.unit * 0.5
                    visible: backend.hasDevices && backend.view === "list"
                    clip: true
                    model: backend.devices
                    keyNavigationEnabled: true
                    currentIndex: -1
                    highlightFollowsCurrentItem: false
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ThinScrollBar {}
                    header: Item {
                        width: list.width
                        height: Theme.unit * 1.8
                        Row {
                            x: Theme.unit * 0.6 + Theme.unit * 2.1 + Theme.unit * 0.8
                            width: parent.width - x - Theme.unit * 0.8
                            spacing: Theme.unit * 0.6
                            readonly property real w: width - spacing * 4
                            Repeater {
                                model: [["DEVICE", 0.30], ["TYPE", 0.16], ["ADDRESS", 0.14], ["VENDOR", 0.22], ["OS", 0.18]]
                                delegate: Text {
                                    required property var modelData
                                    width: parent.w * modelData[1]
                                    text: modelData[0]
                                    color: Theme.textDim
                                    font.pixelSize: Theme.fontSizeSm
                                    font.bold: true
                                    font.letterSpacing: Theme.unit * 0.08
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                        }
                    }
                    onCurrentIndexChanged: if (currentItem) backend.select(currentItem.sid)
                    delegate: DeviceRow {
                        width: list.width
                        selected: backend.current.sid === sid
                        onActivated: { list.currentIndex = index; backend.select(sid) }
                        onOpened: { backend.select(sid); if (backend.current.webUrl) backend.openUrl(backend.current.webUrl) }
                    }
                }
            }

            // detail
            DetailPanel {
                Layout.preferredWidth: win.narrow ? Theme.unit * 16 : Theme.unit * 21
                Layout.fillHeight: true
                cur: backend.current
                onEditRequested: backend.requestEdit()
                onOpenWeb: function (url) { backend.openUrl(url) }
                onCopyRequested: function (t) { backend.copyText(t) }
            }
        }

        HintBar {
            Layout.fillWidth: true
            message: backend.status
            compact: win.narrow
            hints: [{ key: "←↑↓→", label: "Navigate" }, { key: "O", label: "Open web UI" },
                    { key: "E", label: "Edit" }, { key: "Ctrl+F", label: "Search" }, { key: "F5", label: "Scan" },
                    { key: "Ctrl+E", label: "Export" }]
        }
    }

    // ── overlays ──────────────────────────────────────────────────────────────────
    EditDialog {
        id: editDlg
        anchors.fill: parent
        onSaved: function (sid, name, typeKey, notes) { backend.saveEdit(sid, name, typeKey, notes) }
        onReset: function (sid) { backend.resetEdit(sid) }
    }

    Rectangle {
        id: toast
        z: 200
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Theme.unit * 3.2
        radius: Theme.radius
        color: Theme.dialogSurface
        border.color: Theme.dialogBorder
        implicitWidth: toastText.implicitWidth + Theme.unit * 1.6
        implicitHeight: toastText.implicitHeight + Theme.unit * 1.0
        opacity: 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: Theme.dur(160) } }
        Text { id: toastText; anchors.centerIn: parent; color: Theme.text; font.pixelSize: Theme.fontSize }
        Timer { id: toastTimer; interval: 2600; onTriggered: toast.opacity = 0 }
    }
    Connections {
        target: backend
        function onEditRequested() { editDlg.openFor(backend.current) }
        function onToast(message) { toastText.text = message; toast.opacity = 1; toastTimer.restart() }
    }

    FileDialog {
        id: saveDlg
        property string fmt: "json"
        property string fmtLabel: "JSON"
        title: "Export results"
        fileMode: FileDialog.SaveFile
        defaultSuffix: fmt
        currentFolder: StandardPaths.writableLocation(StandardPaths.DocumentsLocation)
        nameFilters: [fmtLabel + " (*." + fmt + ")"]
        onAccepted: backend.exportTo(selectedFile.toString(), fmt)
    }
}
