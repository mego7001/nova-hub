import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: root

    property var theme
    property var commands: [
        { id: "mode.general", label: "Switch Mode: general", shortcut: "", actionKind: "switch_mode", group: "mode", rank: 200, requiresApproval: false, unavailableReason: "", payload: { mode: "general" } },
        { id: "mode.3d", label: "Switch Mode: gen_3d_step", shortcut: "", actionKind: "switch_mode", group: "mode", rank: 195, requiresApproval: false, unavailableReason: "", payload: { mode: "gen_3d_step" } },
        { id: "mode.2d", label: "Switch Mode: gen_2d_dxf", shortcut: "", actionKind: "switch_mode", group: "mode", rank: 195, requiresApproval: false, unavailableReason: "", payload: { mode: "gen_2d_dxf" } },
        { id: "drawer.tools", label: "Open Drawer: Tools", shortcut: "", actionKind: "open_drawer", group: "navigation", rank: 210, requiresApproval: false, unavailableReason: "", payload: { drawer: "tools" } },
        { id: "drawer.attach", label: "Open Drawer: Attach", shortcut: "", actionKind: "open_drawer", group: "navigation", rank: 205, requiresApproval: false, unavailableReason: "", payload: { drawer: "attach" } },
        { id: "drawer.health", label: "Open Drawer: Health", shortcut: "", actionKind: "open_drawer", group: "navigation", rank: 205, requiresApproval: false, unavailableReason: "", payload: { drawer: "health" } },
        { id: "drawer.history", label: "Open Drawer: History", shortcut: "", actionKind: "open_drawer", group: "navigation", rank: 205, requiresApproval: false, unavailableReason: "", payload: { drawer: "history" } },
        { id: "drawer.voice", label: "Open Drawer: Voice", shortcut: "", actionKind: "open_drawer", group: "navigation", rank: 205, requiresApproval: false, unavailableReason: "", payload: { drawer: "voice" } },
        { id: "doctor.report", label: "Run Doctor Report", shortcut: "", actionKind: "run_doctor", group: "health", rank: 190, requiresApproval: false, unavailableReason: "", payload: ({}) },
        { id: "apply.queue", label: "Queue Apply Candidate", shortcut: "", actionKind: "apply_queue", group: "approvals", rank: 188, requiresApproval: true, unavailableReason: "", payload: ({}) },
        { id: "apply.confirm", label: "Confirm Pending Candidate", shortcut: "", actionKind: "apply_confirm", group: "approvals", rank: 188, requiresApproval: true, unavailableReason: "", payload: ({}) },
        { id: "apply.reject", label: "Reject Pending Candidate", shortcut: "", actionKind: "apply_reject", group: "approvals", rank: 188, requiresApproval: true, unavailableReason: "", payload: ({}) },
        { id: "security.audit", label: "Run Security Audit", shortcut: "", actionKind: "security_audit", group: "security", rank: 182, requiresApproval: false, unavailableReason: "", payload: ({}) },
        { id: "timeline.refresh", label: "Refresh Timeline", shortcut: "", actionKind: "refresh_timeline", group: "timeline", rank: 180, requiresApproval: false, unavailableReason: "", payload: ({}) },
        { id: "voice.toggle", label: "Voice: Toggle Mic", shortcut: "", actionKind: "voice_toggle", group: "voice", rank: 178, requiresApproval: false, unavailableReason: "", payload: ({}) },
        { id: "voice.mute", label: "Voice: Toggle Mute", shortcut: "", actionKind: "voice_mute_toggle", group: "voice", rank: 176, requiresApproval: false, unavailableReason: "", payload: ({}) },
        { id: "voice.stop", label: "Voice: Stop Speaking", shortcut: "", actionKind: "voice_stop", group: "voice", rank: 176, requiresApproval: false, unavailableReason: "", payload: ({}) },
        { id: "voice.replay", label: "Voice: Replay Last", shortcut: "", actionKind: "voice_replay", group: "voice", rank: 176, requiresApproval: false, unavailableReason: "", payload: ({}) },
        { id: "app.minimize", label: "Window: Minimize Nova", shortcut: "", actionKind: "app_minimize", group: "window", rank: 160, requiresApproval: false, unavailableReason: "", payload: ({}) },
        { id: "app.close", label: "Window: Close Nova", shortcut: "", actionKind: "app_close", group: "window", rank: 160, requiresApproval: false, unavailableReason: "", payload: ({}) }
    ]
    property var filteredCommands: []
    property int selectedIndex: 0

    signal commandTriggered(var command)

    modal: true
    focus: true
    closePolicy: Popup.NoAutoClose
    width: Math.min(800, Overlay.overlay ? Overlay.overlay.width - 40 : 800)
    height: Math.min(560, Overlay.overlay ? Overlay.overlay.height - 40 : 560)
    anchors.centerIn: Overlay.overlay
    padding: 0

    Overlay.modal: Rectangle {
        color: root.theme.bgSolid
        opacity: 0.78
    }

    background: Rectangle {
        radius: root.theme.radiusLg
        color: root.theme.bgGlass
        border.width: 1
        border.color: root.theme.borderHard
    }

    function _matches(command, queryText) {
        var query = String(queryText || "").toLowerCase().trim()
        if (!query.length)
            return true
        var hay = (
            String(command.label || "") + " " +
            String(command.actionKind || "") + " " +
            String(command.group || "") + " " +
            String(command.unavailableReason || "")
        ).toLowerCase()
        var terms = query.split(/\s+/)
        for (var i = 0; i < terms.length; i++) {
            if (hay.indexOf(terms[i]) < 0)
                return false
        }
        return true
    }

    function _score(command, queryText) {
        var base = Number(command.rank || 0)
        if (!queryText || String(queryText).trim().length <= 0)
            return base
        var q = String(queryText).toLowerCase()
        var label = String(command.label || "").toLowerCase()
        if (label.indexOf(q) === 0)
            return base + 100
        if (label.indexOf(q) >= 0)
            return base + 40
        return base
    }

    function _clampIndex() {
        if (filteredCommands.length <= 0) {
            selectedIndex = 0
            return
        }
        if (selectedIndex < 0)
            selectedIndex = 0
        if (selectedIndex >= filteredCommands.length)
            selectedIndex = filteredCommands.length - 1
    }

    function applyFilter() {
        var out = []
        var query = String(searchField.text || "")
        for (var i = 0; i < commands.length; i++) {
            var command = commands[i]
            if (!_matches(command, query))
                continue
            var withScore = {}
            withScore.id = command.id
            withScore.label = command.label
            withScore.shortcut = command.shortcut
            withScore.actionKind = command.actionKind
            withScore.group = command.group
            withScore.requiresApproval = Boolean(command.requiresApproval)
            withScore.unavailableReason = String(command.unavailableReason || "")
            withScore.payload = command.payload
            withScore._score = _score(command, query)
            out.push(withScore)
        }
        out.sort(function(a, b) {
            return Number(b._score || 0) - Number(a._score || 0)
        })
        filteredCommands = out
        _clampIndex()
    }

    function openPalette(seedText) {
        searchField.text = String(seedText || "")
        applyFilter()
        selectedIndex = 0
        open()
        searchField.forceActiveFocus()
    }

    function closePalette() {
        close()
    }

    function togglePalette() {
        if (visible)
            closePalette()
        else
            openPalette("")
    }

    function executeSelected() {
        if (filteredCommands.length <= 0)
            return
        var command = filteredCommands[selectedIndex]
        if (!command)
            return
        root.commandTriggered(command)
        closePalette()
    }

    onOpened: {
        applyFilter()
        searchField.forceActiveFocus()
    }

    Shortcut {
        sequence: "Esc"
        enabled: root.visible
        onActivated: root.closePalette()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        Label {
            Layout.fillWidth: true
            text: "Command Palette | ranked"
            color: root.theme.textPrimary
            font.bold: true
            font.pixelSize: 14
        }

        TextField {
            id: searchField
            Layout.fillWidth: true
            placeholderText: "Search commands, tools, or drawer"
            color: root.theme.textPrimary
            placeholderTextColor: root.theme.textMuted
            selectionColor: root.theme.accentSoft
            selectedTextColor: root.theme.bgSolid
            background: Rectangle {
                radius: root.theme.radiusMd
                color: root.theme.bgSolid
                border.width: 1
                border.color: root.theme.borderSoft
            }
            onTextChanged: root.applyFilter()
            Keys.onPressed: (event) => {
                if (event.key === Qt.Key_Down) {
                    root.selectedIndex = Math.min(root.selectedIndex + 1, root.filteredCommands.length - 1)
                    commandList.currentIndex = root.selectedIndex
                    event.accepted = true
                } else if (event.key === Qt.Key_Up) {
                    root.selectedIndex = Math.max(root.selectedIndex - 1, 0)
                    commandList.currentIndex = root.selectedIndex
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

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: root.theme.radiusMd
            color: root.theme.bgSolid
            border.width: 1
            border.color: root.theme.borderSoft

            ListView {
                id: commandList
                anchors.fill: parent
                anchors.margins: 6
                clip: true
                spacing: 6
                model: root.filteredCommands
                currentIndex: root.selectedIndex
                onCurrentIndexChanged: root.selectedIndex = currentIndex

                delegate: Rectangle {
                    required property int index
                    required property var modelData

                    width: ListView.view.width
                    height: 62
                    radius: root.theme.radiusSm
                    color: ListView.isCurrentItem ? root.theme.glowSoft : root.theme.bgGlass
                    border.width: 1
                    border.color: ListView.isCurrentItem ? root.theme.borderHard : root.theme.borderSoft

                    Column {
                        anchors.fill: parent
                        anchors.margins: 8
                        spacing: 2

                        Label {
                            width: parent.width
                            text: modelData.label
                            color: root.theme.textPrimary
                            elide: Label.ElideRight
                            font.bold: true
                        }

                        Label {
                            width: parent.width
                            text: String(modelData.group || "") + " | " +
                                String(modelData.actionKind || "") +
                                (modelData.requiresApproval ? " | requires approval" : "") +
                                (String(modelData.unavailableReason || "").length > 0 ? (" | " + modelData.unavailableReason) : "")
                            color: root.theme.textMuted
                            elide: Label.ElideRight
                            font.pixelSize: 11
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: {
                            root.selectedIndex = index
                            commandList.currentIndex = index
                        }
                        onDoubleClicked: root.executeSelected()
                    }
                }
            }
        }

        Label {
            Layout.fillWidth: true
            text: "Enter execute | Esc close | Ctrl+K open"
            color: root.theme.textMuted
            font.pixelSize: 11
            horizontalAlignment: Text.AlignRight
        }
    }
}
