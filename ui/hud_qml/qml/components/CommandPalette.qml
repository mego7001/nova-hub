import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: root
    property var theme
    property var controller
    property var allActions: []
    property var filteredActions: []
    property int selectedIndex: 0
    property var selectedAction: (filteredActions.length > 0 && selectedIndex >= 0 && selectedIndex < filteredActions.length) ? filteredActions[selectedIndex] : null

    width: Math.min(980, Overlay.overlay ? Overlay.overlay.width - 80 : 980)
    height: Math.min(620, Overlay.overlay ? Overlay.overlay.height - 80 : 620)
    modal: true
    focus: true
    closePolicy: Popup.NoAutoClose
    anchors.centerIn: Overlay.overlay
    padding: 0

    background: Rectangle {
        radius: 12
        color: Qt.rgba(0.05, 0.15, 0.25, 0.95) // High opacity glass for palette
        border.width: 1
        border.color: theme.accent
        
        // Inner highlight
        Rectangle {
            anchors.fill: parent
            anchors.margins: 1
            color: "transparent"
            border.color: theme.glassHighlight
            border.width: 1
            radius: parent.radius - 1
        }
    }

    Overlay.modal: Rectangle {
        color: Qt.rgba(0, 0, 0, 0.7)
    }

    function _matches(action, query) {
        if (!query || !query.trim().length)
            return true
        const hay = ((action.title || "") + " " + (action.category || "") + " " + (action.description || "")).toLowerCase()
        const terms = query.toLowerCase().trim().split(/\s+/)
        for (let i = 0; i < terms.length; i++) {
            if (hay.indexOf(terms[i]) < 0)
                return false
        }
        return true
    }

    function _clampIndex() {
        if (filteredActions.length <= 0) {
            selectedIndex = 0
            return
        }
        if (selectedIndex < 0)
            selectedIndex = 0
        if (selectedIndex >= filteredActions.length)
            selectedIndex = filteredActions.length - 1
    }

    function refreshActions() {
        allActions = controller ? controller.getPaletteActions() : []
        applyFilter()
    }

    function applyFilter() {
        const out = []
        for (let i = 0; i < allActions.length; i++) {
            const item = allActions[i]
            if (_matches(item, searchField.text))
                out.push(item)
        }
        filteredActions = out
        _clampIndex()
    }

    function openPalette(seedText) {
        refreshActions()
        searchField.text = seedText || ""
        applyFilter()
        selectedIndex = 0
        open()
        searchField.forceActiveFocus()
    }

    function closePalette() {
        close()
    }

    function executeSelected() {
        if (filteredActions.length <= 0)
            return
        const action = filteredActions[selectedIndex]
        if (!action || !action.id)
            return
        if (action.enabled === false)
            return
        if (controller)
            controller.runPaletteAction(action.id, searchField.text)
        closePalette()
    }

    function queueApplyFromPalette() {
        if (controller)
            controller.queue_apply()
        closePalette()
    }

    onOpened: {
        refreshActions()
        searchField.forceActiveFocus()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 16

        TextField {
            id: searchField
            Layout.fillWidth: true
            placeholderText: "COMMAND OR PROJECT SEARCH..."
            color: theme.textPrimary
            font.family: theme.titleFont
            font.pixelSize: 14
            font.bold: true
            font.letterSpacing: 1.1
            selectByMouse: true
            background: Rectangle {
                color: Qt.rgba(1.0, 1.0, 1.0, 0.05)
                border.color: theme.glassHighlight
                radius: 8
            }
            onTextChanged: root.applyFilter()
            Keys.onPressed: (event) => {
                if (event.key === Qt.Key_Down) {
                    root.selectedIndex = Math.min(root.selectedIndex + 1, root.filteredActions.length - 1)
                    event.accepted = true
                } else if (event.key === Qt.Key_Up) {
                    root.selectedIndex = Math.max(root.selectedIndex - 1, 0)
                    event.accepted = true
                } else if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && (event.modifiers & Qt.ControlModifier)) {
                    root.queueApplyFromPalette()
                    event.accepted = true
                } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                    root.executeSelected()
                    event.accepted = true
                } else if (event.key === Qt.Key_Escape) {
                    root.closePalette()
                    event.accepted = true
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 20

            // Action List
            Rectangle {
                Layout.preferredWidth: 520
                Layout.fillHeight: true
                radius: 10
                color: Qt.rgba(1.0, 1.0, 1.0, 0.03)
                border.width: 1
                border.color: Qt.rgba(1.0, 1.0, 1.0, 0.08)

                ListView {
                    id: listView
                    anchors.fill: parent
                    anchors.margins: 10
                    model: root.filteredActions
                    spacing: 8
                    clip: true
                    cacheBuffer: 500
                    reuseItems: true
                    currentIndex: root.selectedIndex
                    onCurrentIndexChanged: root.selectedIndex = currentIndex

                    delegate: Rectangle {
                        required property var modelData
                        width: ListView.view.width
                        height: 52
                        radius: 8
                        color: ListView.isCurrentItem ? Qt.rgba(0.0, 0.9, 1.0, 0.12) : "transparent"
                        border.width: 1
                        border.color: ListView.isCurrentItem ? theme.accent : "transparent"

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 12

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 1
                                Label {
                                    text: (modelData.title || "").toUpperCase()
                                    color: modelData.enabled === false ? theme.textDim : (ListView.isCurrentItem ? theme.accent : theme.textPrimary)
                                    font.family: theme.titleFont
                                    font.bold: true
                                    font.pixelSize: 11
                                    elide: Label.ElideRight
                                }
                                Label {
                                    text: (modelData.category || "").toUpperCase() + (modelData.hotkey ? " • " + modelData.hotkey : "")
                                    color: theme.textDim
                                    font.family: theme.titleFont
                                    font.pixelSize: 8
                                    font.bold: true
                                    elide: Label.ElideRight
                                }
                            }

                            Rectangle {
                                Layout.preferredWidth: 160
                                Layout.preferredHeight: 22
                                radius: 4
                                color: (modelData.badge || "").indexOf("OK") === 0 ? Qt.rgba(0.0, 1.0, 0.75, 0.1) : Qt.rgba(1.0, 0.84, 0.0, 0.1)
                                border.width: 1
                                border.color: (modelData.badge || "").indexOf("OK") === 0 ? theme.positive : theme.warning
                                opacity: modelData.badge ? 1.0 : 0.0
                                
                                Label {
                                    anchors.centerIn: parent
                                    text: (modelData.badge || "").toUpperCase()
                                    color: theme.textPrimary
                                    font.family: theme.titleFont
                                    font.pixelSize: 9
                                    font.bold: true
                                }
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: {
                                root.selectedIndex = index
                                listView.currentIndex = index
                            }
                            onDoubleClicked: root.executeSelected()
                        }
                    }
                }
            }

            // Detail Panel
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 10
                color: Qt.rgba(0, 0, 0, 0.2)
                border.width: 1
                border.color: theme.glassHighlight

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 12

                    Label {
                        text: root.selectedAction ? root.selectedAction.title.toUpperCase() : "NO ACTION SELECTED"
                        color: theme.textPrimary
                        font.family: theme.titleFont
                        font.pixelSize: 12
                        font.bold: true
                        wrapMode: Label.Wrap
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        height: 1
                        color: theme.accent
                        opacity: 0.3
                    }
                    Label {
                        text: root.selectedAction ? (root.selectedAction.description || "") : ""
                        color: theme.textMuted
                        font.family: theme.bodyFont
                        font.pixelSize: 12
                        wrapMode: Label.Wrap
                        Layout.fillWidth: true
                    }
                    
                    Item { Layout.fillHeight: true }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 32
                            radius: 6
                            color: Qt.rgba(1.0, 1.0, 1.0, 0.03)
                            border.width: 1
                            border.color: theme.glassHighlight
                            
                            Label {
                                anchors.centerIn: parent
                                text: root.selectedAction ? ("ID: " + root.selectedAction.id + (root.selectedAction.hotkey ? " • HOTKEY: " + root.selectedAction.hotkey : "")) : ""
                                color: theme.accent
                                font.family: theme.titleFont
                                font.pixelSize: 9
                                font.bold: true
                            }
                        }

                        Label {
                            text: "↵ EXECUTE | ⌃↵ PLAN | ⎋ CLOSE"
                            color: theme.textDim
                            font.family: theme.titleFont
                            font.pixelSize: 9
                            font.bold: true
                            font.letterSpacing: 1.1
                            horizontalAlignment: Text.AlignHCenter
                            Layout.fillWidth: true
                        }
                    }
                }
            }
        }
    }
}
