import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import QtQuick.Window
import "components"
import "panels"

Window {
    id: win
    visible: true
    visibility: Window.Maximized
    width: 1540
    height: 930
    minimumWidth: 1024
    minimumHeight: 680
    color: "transparent"
    title: "Nova HUD QML"
    flags: Qt.Window | Qt.FramelessWindowHint
    property bool diffPoppedOut: false
    property bool timelinePoppedOut: false
    property bool threeDPoppedOut: false
    property var panelTheme: theme
    property bool keepOllamaRunning: true
    readonly property int leftRailWidth: Math.max(220, Math.min(300, Math.round(width * 0.19)))
    readonly property int rightRailWidth: Math.max(300, Math.min(430, Math.round(width * 0.25)))

    function _restorePanel(panelId) {
        if (panelId === "diff.preview") {
            diffPoppedOut = false
            hudController.setPanelPoppedOut(panelId, false)
            if (diffPopout.visible)
                diffPopout.hide()
            return
        }
        if (panelId === "timeline") {
            timelinePoppedOut = false
            hudController.setPanelPoppedOut(panelId, false)
            if (timelinePopout.visible)
                timelinePopout.hide()
            return
        }
        if (panelId === "threed") {
            threeDPoppedOut = false
            hudController.setPanelPoppedOut(panelId, false)
            if (threeDPopout.visible)
                threeDPopout.hide()
            return
        }
    }

    function _popOutPanel(panelId) {
        if (panelId === "diff.preview") {
            if (!diffPoppedOut) {
                diffPoppedOut = true
                hudController.setPanelPoppedOut(panelId, true)
            }
            diffPopout.show()
            diffPopout.raise()
            diffPopout.requestActivate()
            return
        }
        if (panelId === "timeline") {
            if (!timelinePoppedOut) {
                timelinePoppedOut = true
                hudController.setPanelPoppedOut(panelId, true)
            }
            timelinePopout.show()
            timelinePopout.raise()
            timelinePopout.requestActivate()
            return
        }
        if (panelId === "threed") {
            if (!threeDPoppedOut) {
                threeDPoppedOut = true
                hudController.setPanelPoppedOut(panelId, true)
            }
            threeDPopout.show()
            threeDPopout.raise()
            threeDPopout.requestActivate()
        }
    }

    function _shutdownNovaAndClose() {
        hudController.shutdownNova(Boolean(win.keepOllamaRunning), 15, true)
        win.close()
    }

    Component.onCompleted: {
        diffPoppedOut = hudController.isPanelPoppedOut("diff.preview")
        timelinePoppedOut = hudController.isPanelPoppedOut("timeline")
        threeDPoppedOut = hudController.isPanelPoppedOut("threed")
        if (diffPoppedOut)
            diffPopout.show()
        if (timelinePoppedOut)
            timelinePopout.show()
        if (threeDPoppedOut)
            threeDPopout.show()
    }

    Theme {
        id: theme
        jarvisMode: hudController.jarvisMode
    }

    Shortcut {
        sequence: "Ctrl+K"
        onActivated: {
            if (commandPalette.visible)
                commandPalette.closePalette()
            else
                commandPalette.openPalette("")
        }
    }
    Shortcut {
        sequence: "Ctrl+1"
        onActivated: chatListPanel.focusList()
    }
    Shortcut {
        sequence: "Ctrl+2"
        onActivated: commandBarPanel.focusInput()
    }
    Shortcut {
        sequence: "Ctrl+3"
        onActivated: rightColumn.forceActiveFocus()
    }
    Shortcut {
        sequence: "Ctrl+Shift+A"
        onActivated: hudController.queue_apply()
    }
    Shortcut {
        sequence: "Ctrl+Shift+V"
        onActivated: hudController.toggle_voice_enabled()
    }
    Shortcut {
        sequence: "Ctrl+Shift+M"
        onActivated: {
            if (hudController.voiceMuted)
                hudController.voice_unmute()
            else
                hudController.voice_mute()
        }
    }
    Shortcut {
        sequence: "Ctrl+Return"
        enabled: !commandPalette.visible
        onActivated: commandBarPanel.triggerSend()
    }
    Shortcut {
        sequence: "Esc"
        onActivated: {
            if (commandPalette.visible)
                commandPalette.closePalette()
            else if (hudController.confirmationReadOnly)
                hudController.reject_pending()
        }
    }

    Rectangle {
        anchors.fill: parent
        radius: 16
        color: theme.bg
        border.width: 1
        border.color: theme.glassBorder
        clip: true

        // Base sophisticated gradient
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(0.0, 0.6, 0.7, 0.12) }
                GradientStop { position: 0.5; color: Qt.rgba(0.0, 0.1, 0.2, 0.05) }
                GradientStop { position: 1.0; color: "black" }
            }
        }

        // Inner frame glow
        Rectangle {
            anchors.fill: parent
            anchors.margins: 1
            color: "transparent"
            border.width: 1
            border.color: Qt.rgba(0.0, 0.9, 1.0, 0.15)
            radius: 15
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 12

            TopBar {
                id: topBar
                Layout.fillWidth: true
                theme: theme
                rootWindow: win
                title: "NOVA HUB | ENGINE 1.5"
                statusText: hudController.statusText
                wiringStatus: hudController.wiringStatus
                jarvisMode: hudController.jarvisMode
                onToggleModeRequested: hudController.toggleMode()
                onRefreshRequested: {
                    hudController.refresh_projects()
                    hudController.refresh_jobs()
                    hudController.refresh_timeline()
                }
                onExitRequested: exitMenu.popup()
                onCloseRequested: win.close()
                onMinimizeRequested: win.showMinimized()
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Rectangle {
                    Layout.preferredWidth: 270
                    Layout.preferredHeight: 34
                    radius: 8
                    color: theme.bgAlt
                    border.width: 1
                    border.color: theme.border
                    Label {
                        anchors.fill: parent
                        anchors.margins: 8
                        text: hudController.projectBadge
                        color: theme.textPrimary
                        elide: Label.ElideRight
                    }
                }
                Rectangle {
                    Layout.preferredWidth: 180
                    Layout.preferredHeight: 34
                    radius: 8
                    color: theme.bgAlt
                    border.width: 1
                    border.color: theme.border
                    Label {
                        anchors.fill: parent
                        anchors.margins: 8
                        text: "Status: " + hudController.projectStatus
                        color: theme.textPrimary
                        elide: Label.ElideRight
                    }
                }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 34
                    radius: 8
                    color: theme.bgAlt
                    border.width: 1
                    border.color: hudController.applyEnabled ? theme.border : theme.warning
                    Label {
                        anchors.fill: parent
                        anchors.margins: 8
                        text: hudController.toolsBadge
                        color: theme.textPrimary
                        elide: Label.ElideRight
                    }
                }
            }

            Label {
                Layout.fillWidth: true
                text: hudController.capsSummary
                color: theme.textMuted
                font.pixelSize: 11
                elide: Label.ElideRight
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 10

                ColumnLayout {
                    id: leftRail
                    Layout.preferredWidth: win.leftRailWidth
                    Layout.minimumWidth: 260
                    Layout.maximumWidth: 320
                    Layout.fillHeight: true
                    spacing: 8

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 50
                        radius: 10
                        color: theme.panelRaised
                        border.width: 1
                        border.color: theme.border
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 8
                            spacing: 2
                            Label {
                                Layout.fillWidth: true
                                text: "Assistant Rail"
                                color: theme.textPrimary
                                font.bold: true
                                font.pixelSize: 12
                                elide: Label.ElideRight
                            }
                            Label {
                                Layout.fillWidth: true
                                text: "Chats | Projects"
                                color: theme.textMuted
                                font.pixelSize: 11
                                elide: Label.ElideRight
                            }
                        }
                    }

                    ChatList {
                        id: chatListPanel
                        Layout.fillWidth: true
                        Layout.preferredHeight: 180
                        Layout.minimumHeight: 130
                        theme: theme
                        model: hudController.chatsModel
                        currentChatId: hudController.currentChatId
                        onChatSelected: (chatId) => hudController.select_chat(chatId)
                        onNewChatRequested: () => hudController.create_chat()
                    }

                    ProjectList {
                        id: projectListPanel
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.minimumHeight: 120
                        Layout.preferredHeight: 330
                        theme: theme
                        model: hudController.projectsModel
                        currentProjectId: hudController.currentProjectId
                        onProjectSelected: (projectId) => hudController.select_project(projectId)
                    }

                    JobsList {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 170
                        Layout.minimumHeight: 130
                        theme: theme
                        model: hudController.jobsModel
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 84
                        radius: 8
                        color: theme.bgAlt
                        border.width: 1
                        border.color: theme.border

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 8
                            spacing: 4

                            Label {
                                Layout.fillWidth: true
                                text: "Latest Nova Reply"
                                color: theme.accentSoft
                                font.bold: true
                                font.pixelSize: 12
                                elide: Label.ElideRight
                            }
                            Label {
                                Layout.fillWidth: true
                                text: hudController.latestReplyPreview
                                color: theme.textPrimary
                                wrapMode: Label.Wrap
                                maximumLineCount: 2
                                elide: Label.ElideRight
                            }
                        }
                    }
                }

                ColumnLayout {
                    id: centerColumn
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumWidth: 420
                    spacing: 10

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 36
                        radius: 8
                        color: theme.bgAlt
                        border.width: 1
                        border.color: theme.border
                        Label {
                            anchors.fill: parent
                            anchors.margins: 8
                            text: "Conversation - Nova replies appear here"
                            color: theme.textPrimary
                            font.bold: true
                            elide: Label.ElideRight
                        }
                    }

                    ChatView {
                        id: chatViewPanel
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        theme: theme
                        model: hudController.messagesModel
                    }

                    CommandBar {
                        id: commandBarPanel
                        Layout.fillWidth: true
                        Layout.preferredHeight: 92
                        theme: theme
                        busy: hudController.busy
                        applyEnabled: hudController.applyEnabled
                        taskModesModel: hudController.taskModesModel
                        currentTaskMode: hudController.currentTaskMode
                        onSendRequested: (message) => { hudController.send_message(message) }
                        onApplyRequested: () => hudController.queue_apply()
                        onAttachRequested: () => attachDialog.open()
                        onToolsRequested: () => hudController.toggleToolsMenu()
                        onTaskModeChangedRequested: (modeId) => { hudController.setTaskMode(modeId) }
                    }

                    PanelCard {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 240
                        visible: hudController.diffPreviewVisible && !win.diffPoppedOut
                        theme: theme
                        title: "Diff Preview"
                        panelId: "diff.preview"
                        onPopOutRequested: (panelId) => win._popOutPanel(panelId)
                        Loader {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            active: !win.diffPoppedOut
                            sourceComponent: diffPreviewPanelComponent
                        }
                    }

                    ConfirmationStrip {
                        Layout.fillWidth: true
                        active: hudController.hasPendingApproval
                        theme: theme
                        summary: hudController.confirmationSummary
                        readOnly: hudController.confirmationReadOnly
                        locked: hudController.confirmationLocked
                        onConfirmRequested: hudController.confirm_pending()
                        onRejectRequested: hudController.reject_pending()
                    }
                }

                Flickable {
                    id: rightColumn
                    Layout.preferredWidth: win.rightRailWidth
                    Layout.minimumWidth: 300
                    Layout.maximumWidth: 430
                    Layout.fillHeight: true
                    activeFocusOnTab: true
                    contentWidth: width
                    contentHeight: cardsColumn.implicitHeight
                    clip: true

                    ScrollBar.vertical: ScrollBar {}

                    ColumnLayout {
                        id: cardsColumn
                        width: rightColumn.width
                        spacing: 10

                        PanelCard {
                            Layout.fillWidth: true
                            theme: theme
                            glow: hudController.jarvisMode
                            title: "Engineering"
                            Label {
                                Layout.fillWidth: true
                                text: hudController.engineeringSummary
                                color: theme.textMuted
                                wrapMode: Label.Wrap
                            }
                            Label {
                                Layout.fillWidth: true
                                text: hudController.evidenceChip
                                color: theme.textMuted
                                wrapMode: Label.Wrap
                                font.pixelSize: 11
                            }
                            Label {
                                Layout.fillWidth: true
                                text: hudController.actionsChip
                                color: theme.textMuted
                                wrapMode: Label.Wrap
                                font.pixelSize: 11
                            }
                            Label {
                                Layout.fillWidth: true
                                text: hudController.risksChip
                                color: theme.textMuted
                                wrapMode: Label.Wrap
                                font.pixelSize: 11
                            }
                        }

                        PanelCard {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 340
                            theme: theme
                            title: "Voice Chat"
                            Loader {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                sourceComponent: voiceChatPanelComponent
                            }
                        }

                        PanelCard {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 320
                            visible: hudController.toolsMenuVisible
                            theme: theme
                            title: "Tools Menu"
                            Loader {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                sourceComponent: toolsMenuPanelComponent
                            }
                        }

                        PanelCard {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 260
                            theme: theme
                            title: "Attach Summary"
                            Loader {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                sourceComponent: attachSummaryPanelComponent
                            }
                        }

                        PanelCard {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 280
                            theme: theme
                            title: "Health / Stats"
                            Loader {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                sourceComponent: healthStatsPanelComponent
                            }
                        }

                        PanelCard {
                            id: threeDCard
                            visible: !win.threeDPoppedOut
                            Layout.fillWidth: true
                            theme: theme
                            glow: hudController.jarvisMode
                            title: "3D Mind"
                            panelId: "threed"
                            onPopOutRequested: (panelId) => win._popOutPanel(panelId)
                            Loader {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 360
                                active: !win.threeDPoppedOut
                                sourceComponent: threeDPanelComponent
                            }
                        }

                        PanelCard {
                            Layout.fillWidth: true
                            theme: theme
                            title: "Sketch / DXF"
                            Label {
                                Layout.fillWidth: true
                                text: hudController.sketchSummary
                                color: theme.textMuted
                                wrapMode: Label.Wrap
                            }
                        }

                        PanelCard {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 360
                            theme: theme
                            title: "DXF/Clip QA"
                            Loader {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                sourceComponent: qaReportPanelComponent
                            }
                        }

                        PanelCard {
                            Layout.fillWidth: true
                            theme: theme
                            title: "Security Doctor"
                            Label {
                                Layout.fillWidth: true
                                text: hudController.securitySummary
                                color: theme.textMuted
                                wrapMode: Label.Wrap
                            }
                            Button {
                                text: "Run Security Audit"
                                onClicked: hudController.run_security_audit()
                            }
                        }

                        PanelCard {
                            visible: !win.timelinePoppedOut
                            Layout.fillWidth: true
                            theme: theme
                            title: "Timeline"
                            panelId: "timeline"
                            onPopOutRequested: win._popOutPanel(panelId)
                            Label {
                                Layout.fillWidth: true
                                text: hudController.timelineSummary
                                color: theme.textMuted
                                wrapMode: Label.Wrap
                            }
                            Loader {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 220
                                active: !win.timelinePoppedOut
                                sourceComponent: timelinePanelComponent
                            }
                        }
                    }
                }
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 30
                color: "transparent"
                RowLayout {
                    anchors.centerIn: parent
                    spacing: 20
                    Repeater {
                        model: [
                            { key: "Ctrl+K", label: "Palette" },
                            { key: "Ctrl+1/2/3", label: "Focus" },
                            { key: "Ctrl+Ret", label: "Send" },
                            { key: "C+S+A", label: "Apply" }
                        ]
                        Row {
                            spacing: 4
                            Rectangle {
                                width: txtKey.width + 8; height: 18; radius: 4; color: theme.bgAlt; border.width: 1; border.color: theme.border
                                anchors.verticalCenter: parent.verticalCenter
                                Text { id: txtKey; anchors.centerIn: parent; text: modelData.key; color: theme.accent; font.pixelSize: 10; font.bold: true }
                            }
                            Text { text: modelData.label; color: theme.textMuted; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                        }
                    }
                }
            }
        }
    }


    Component {
        id: diffPreviewPanelComponent
        DiffPreviewPanel {
            theme: win.panelTheme
            controller: hudController
        }
    }

    Component {
        id: timelinePanelComponent
        TimelinePanel {
            theme: win.panelTheme
            controller: hudController
        }
    }

    Component {
        id: threeDPanelComponent
        ThreeDPanel {
            theme: win.panelTheme
            controller: hudController
        }
    }

    Component {
        id: voiceChatPanelComponent
        VoiceChatPanel {
            theme: win.panelTheme
            controller: hudController
        }
    }

    Component {
        id: qaReportPanelComponent
        QAReportPanel {
            theme: win.panelTheme
            controller: hudController
        }
    }

    Component {
        id: toolsMenuPanelComponent
        ToolsMenuPanel {
            theme: win.panelTheme
            controller: hudController
        }
    }

    Component {
        id: attachSummaryPanelComponent
        AttachSummaryPanel {
            theme: win.panelTheme
            controller: hudController
        }
    }

    Component {
        id: healthStatsPanelComponent
        HealthStatsPanel {
            theme: win.panelTheme
            controller: hudController
        }
    }

    PopoutWindow {
        id: diffPopout
        theme: theme
        controller: hudController
        titleText: "Diff Preview"
        contentComponent: diffPreviewPanelComponent
        Component.onCompleted: {
            var g = hudController.getPopoutGeometry("diff.preview")
            if (g && g.width > 0 && g.height > 0) {
                x = g.x
                y = g.y
                width = g.width
                height = g.height
            }
        }
        onWindowClosing: win._restorePanel("diff.preview")
        onXChanged: if (visible) hudController.updatePopoutGeometry("diff.preview", x, y, width, height)
        onYChanged: if (visible) hudController.updatePopoutGeometry("diff.preview", x, y, width, height)
        onWidthChanged: if (visible) hudController.updatePopoutGeometry("diff.preview", x, y, width, height)
        onHeightChanged: if (visible) hudController.updatePopoutGeometry("diff.preview", x, y, width, height)
    }

    PopoutWindow {
        id: timelinePopout
        theme: theme
        controller: hudController
        titleText: "Timeline"
        contentComponent: timelinePanelComponent
        Component.onCompleted: {
            var g = hudController.getPopoutGeometry("timeline")
            if (g && g.width > 0 && g.height > 0) {
                x = g.x
                y = g.y
                width = g.width
                height = g.height
            }
        }
        onWindowClosing: win._restorePanel("timeline")
        onXChanged: if (visible) hudController.updatePopoutGeometry("timeline", x, y, width, height)
        onYChanged: if (visible) hudController.updatePopoutGeometry("timeline", x, y, width, height)
        onWidthChanged: if (visible) hudController.updatePopoutGeometry("timeline", x, y, width, height)
        onHeightChanged: if (visible) hudController.updatePopoutGeometry("timeline", x, y, width, height)
    }

    PopoutWindow {
        id: threeDPopout
        theme: theme
        controller: hudController
        titleText: "3D Mind"
        contentComponent: threeDPanelComponent
        Component.onCompleted: {
            var g = hudController.getPopoutGeometry("threed")
            if (g && g.width > 0 && g.height > 0) {
                x = g.x
                y = g.y
                width = g.width
                height = g.height
            }
        }
        onWindowClosing: win._restorePanel("threed")
        onXChanged: if (visible) hudController.updatePopoutGeometry("threed", x, y, width, height)
        onYChanged: if (visible) hudController.updatePopoutGeometry("threed", x, y, width, height)
        onWidthChanged: if (visible) hudController.updatePopoutGeometry("threed", x, y, width, height)
        onHeightChanged: if (visible) hudController.updatePopoutGeometry("threed", x, y, width, height)
    }

    Menu {
        id: exitMenu
        modal: true
        MenuItem {
            text: "Shutdown Nova"
            onTriggered: shutdownConfirmDialog.open()
        }
        MenuItem {
            text: "Exit HUD only"
            onTriggered: win.close()
        }
        MenuSeparator {}
        MenuItem {
            text: "Keep Ollama running"
            checkable: true
            checked: win.keepOllamaRunning
            onToggled: win.keepOllamaRunning = checked
        }
    }

    Dialog {
        id: shutdownConfirmDialog
        modal: true
        title: "Shutdown Nova"
        standardButtons: Dialog.Ok | Dialog.Cancel
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        contentItem: Label {
            width: 340
            wrapMode: Label.Wrap
            text: win.keepOllamaRunning
                ? "This will shutdown Nova core and close HUD. Ollama will be left running."
                : "This will shutdown Nova core and close HUD."
            color: theme.textPrimary
        }
        onAccepted: win._shutdownNovaAndClose()
    }

    CommandPalette {
        id: commandPalette
        theme: theme
        controller: hudController
    }

    FileDialog {
        id: attachDialog
        title: "Attach Files"
        fileMode: FileDialog.OpenFiles
        onAccepted: {
            hudController.attachFiles(selectedFiles)
        }
    }
  }
}
