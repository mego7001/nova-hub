import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import QtQuick.Window
import "../components"
import "../panels"
import "../../common_ui" as Common
import "../theme"

Window {
    id: win

    visible: true
    visibility: Window.Maximized
    width: 1440
    height: 900
    minimumWidth: 980
    minimumHeight: 640
    color: "transparent"
    title: "Nova Jarvis V3"
    flags: Qt.Window | Qt.FramelessWindowHint

    property string statusState: "idle"
    property bool waitingAssistant: false
    property string activeDrawer: "tools"
    property bool showIpcHint: false
    property var voiceDevices: ["default"]
    property string voiceDeviceSelected: "default"
    property bool controllerReady: hudController !== null && hudController !== undefined
    property string uiProfileName: (typeof uiProfile !== "undefined" && uiProfile !== null) ? String(uiProfile) : "full"
    property string themeVariantName: (typeof uiThemeVariant !== "undefined" && uiThemeVariant !== null) ? String(uiThemeVariant) : "jarvis_cyan"
    property string motionIntensityName: (typeof uiMotionIntensity !== "undefined" && uiMotionIntensity !== null) ? String(uiMotionIntensity) : "cinematic"
    property string visualEffectsProfileName: (typeof visualEffectsProfile !== "undefined" && visualEffectsProfile !== null) ? String(visualEffectsProfile) : "balanced"
    property bool effectsProfileForced: (typeof visualEffectsProfileForced !== "undefined") ? Boolean(visualEffectsProfileForced) : false
    property string effectiveEffectsProfile: visualEffectsProfileName
    property int runtimeStallCount: 0
    property int lastStallMs: 0
    property double lastStallAtMs: 0
    property int stallMsThreshold: effectsPolicy.stallDegradedThresholdMs
    property int stallBalancedThresholdMs: effectsPolicy.stallBalancedThresholdMs
    property int stallCountToBalanced: effectsPolicy.stallCountToBalanced
    property int stallCountToDegrade: effectsPolicy.stallCountToDegraded
    property int stallWindowMs: effectsPolicy.stallWindowMs
    property bool degradedActivationEmitted: false
    property string focusRegion: "header"
    property string memorySearchScope: "general"
    property string memorySearchQuery: ""
    property int memorySearchOffset: 0
    property int memorySearchLimit: 10
    property int memorySearchTotal: 0
    property var memorySearchResults: []
    property string memorySearchStatus: "Memory search ready."
    property bool keepOllamaRunning: true
    property string _lastToastText: ""
    property double _lastToastAtMs: 0

    Common.Theme {
        id: theme
        variantName: win.themeVariantName
    }
    DesignTokens {
        id: tokens
        themeVariant: win.themeVariantName
        motionIntensity: win.motionIntensityName
    }
    MotionSystemV3 {
        id: motionSystem
        intensity: win.motionIntensityName
    }
    EffectsPolicyV3 {
        id: effectsPolicy
    }

    function _recordUiEvent(eventKey, source, value) {
        if (!win.controllerReady)
            return
        try {
            hudController.recordUiEvent(String(eventKey || ""), String(source || ""), String(value || ""))
        } catch (e) {
        }
    }

    function _ipcDisabled() {
        if (!win.controllerReady)
            return true
        var summary = String(hudController.healthStatsSummary || "").toLowerCase()
        return summary.indexOf("ipc disabled") >= 0
    }

    function _containsToolTrace(text) {
        var message = String(text || "").toLowerCase()
        return message.indexOf("patch.plan") >= 0 ||
            message.indexOf("patch.apply") >= 0 ||
            message.indexOf("verify") >= 0 ||
            message.indexOf("tool") >= 0
    }

    function _markDoneSoon() {
        statusState = "done"
        doneTimer.restart()
    }

    function _showToast(text) {
        var msg = String(text || "").trim()
        if (!msg)
            return
        var nowMs = Date.now()
        if (msg === win._lastToastText && (nowMs - win._lastToastAtMs) < 1200)
            return
        win._lastToastText = msg
        win._lastToastAtMs = nowMs
        toast.showToast(msg)
    }

    function _appMinimize() {
        win.showMinimized()
        _showToast("Done: Nova minimized")
    }

    function _appClose() {
        win.close()
    }

    function _shutdownNovaAndClose() {
        if (!win.controllerReady) {
            win.close()
            return
        }
        var startedAt = Date.now()
        var response = hudController.shutdownNova(Boolean(win.keepOllamaRunning), 15, true)
        var ok = response && Boolean(response.ok)
        var errorText = response && response.error ? String(response.error) : ""
        var watchdog = response && response.watchdog ? response.watchdog : ({})
        var verified = watchdog && watchdog.verified_ports_closed ? watchdog.verified_ports_closed : ({})
        if (!ok) {
            _showToast(errorText.length ? ("Shutdown failed: " + errorText) : "Shutdown failed")
        } else if (!Boolean(verified.ipc) || !Boolean(verified.events)) {
            _showToast("Shutdown requested; core may still be stopping")
        } else {
            _showToast("Done: Nova core stopped")
        }
        var elapsed = Date.now() - startedAt
        _recordUiEvent("ui.command.execute", "shutdown_nova", String(elapsed))
        win.close()
    }

    function _refreshVoiceDevices() {
        if (!win.controllerReady) {
            voiceDevices = ["default"]
            voiceDeviceSelected = "default"
            return
        }
        var listed = hudController.voice_input_devices()
        if (!listed || listed.length <= 0)
            listed = ["default"]
        voiceDevices = listed
        voiceDeviceSelected = String(hudController.voiceCurrentDevice || "default")
    }

    function _openDrawer(name) {
        activeDrawer = String(name || "tools").toLowerCase()
        if (activeDrawer === "voice")
            _refreshVoiceDevices()
        if (activeDrawer === "history" && win.controllerReady)
            hudController.refresh_timeline()
        _recordUiEvent("ui.panel.switch", "hud_v2", activeDrawer)
    }

    function _trackRuntimeStall(sourceKey, elapsed) {
        var stallMs = Number(elapsed || 0)
        if (stallMs <= 0)
            return
        lastStallMs = Math.floor(stallMs)
        _recordUiEvent("ui.performance.stall_ms", String(sourceKey || ""), String(lastStallMs))
        if (effectsProfileForced || effectiveEffectsProfile === "degraded")
            return
        var nowMs = Date.now()
        if ((nowMs - lastStallAtMs) > stallWindowMs)
            runtimeStallCount = 0
        runtimeStallCount = runtimeStallCount + 1
        lastStallAtMs = nowMs
        if (stallMs >= stallMsThreshold && runtimeStallCount >= stallCountToDegrade) {
            var previousProfile = String(effectiveEffectsProfile || "balanced")
            effectiveEffectsProfile = "degraded"
            runtimeStallCount = 0
            _recordUiEvent("ui.effects.profile_transition", String(sourceKey || ""), previousProfile + "->degraded")
            if (!degradedActivationEmitted) {
                degradedActivationEmitted = true
                _recordUiEvent("ui.effects.degraded_activated", String(sourceKey || ""), String(lastStallMs))
            }
            _showToast("Visual effects auto-switched to degraded mode")
            return
        }
        if (effectiveEffectsProfile === "high_effects" && stallMs >= stallBalancedThresholdMs && runtimeStallCount >= stallCountToBalanced) {
            effectiveEffectsProfile = "balanced"
            _recordUiEvent("ui.effects.profile_transition", String(sourceKey || ""), "high_effects->balanced")
            _showToast("Visual effects switched to balanced mode")
        }
    }

    function _focusObjectByName(name) {
        try {
            if (win.contentItem) {
                var child = win.contentItem.findChild(name)
                if (child && child.forceActiveFocus) {
                    child.forceActiveFocus()
                    return true
                }
            }
        } catch (e) {
        }
        return false
    }

    function _focusRegionTarget(regionName) {
        var region = String(regionName || "").toLowerCase()
        if (region === "header")
            return "hudV2TopMinimizeButton"
        if (region === "nav")
            return "hudV2DrawerTab_tools"
        if (region === "content")
            return "hudV2ComposerInputField"
        if (region === "rail")
            return "hudV2RailDoctorButton"
        return "hudV2TopMinimizeButton"
    }

    function _activateFocusRegion(regionName) {
        focusRegion = String(regionName || "header").toLowerCase()
        _focusObjectByName(_focusRegionTarget(focusRegion))
    }

    function _cycleFocusRegion(reverse) {
        var order = ["header", "nav", "content", "rail"]
        var idx = order.indexOf(String(focusRegion || "header"))
        if (idx < 0)
            idx = 0
        if (Boolean(reverse))
            idx = (idx + order.length - 1) % order.length
        else
            idx = (idx + 1) % order.length
        _activateFocusRegion(order[idx])
    }

    function _runMemorySearch(resetOffset) {
        var startedAt = Date.now()
        if (!win.controllerReady) {
            win.memorySearchStatus = "Memory search unavailable (controller not ready)."
            return
        }
        var q = String(win.memorySearchQuery || "").trim()
        if (!q.length) {
            win.memorySearchResults = []
            win.memorySearchTotal = 0
            win.memorySearchOffset = 0
            win.memorySearchStatus = "Memory search returned no results."
            return
        }
        if (resetOffset)
            win.memorySearchOffset = 0
        var payload = hudController.memorySearchPage(
            q,
            String(win.memorySearchScope || "general"),
            Number(win.memorySearchLimit || 10),
            Number(win.memorySearchOffset || 0)
        )
        if (!payload || String(payload.status || "error") !== "ok") {
            win.memorySearchResults = []
            win.memorySearchTotal = 0
            var msg = payload && payload.message ? String(payload.message) : "unknown error"
            win.memorySearchStatus = "Memory search failed: " + msg
            win._showToast(win.memorySearchStatus)
            return
        }
        var hits = payload.hits || []
        win.memorySearchResults = hits
        win.memorySearchTotal = Number(payload.total || hits.length || 0)
        win.memorySearchStatus = hits.length > 0 ? ("Memory search returned " + hits.length + " results.") : "Memory search returned no results."
        var elapsed = Date.now() - startedAt
        _recordUiEvent("ui.command.execute", "memory_search", String(elapsed))
        if (elapsed > stallMsThreshold)
            _trackRuntimeStall("memory_search", elapsed)
    }

    function _runPaletteCommand(command) {
        if (!command || !command.actionKind)
            return
        var startedAt = Date.now()
        var action = String(command.actionKind || "")
        var isLocalUiOnly = action === "toggle_ipc_hint" || action === "app_minimize" || action === "app_close"
        if (win.controllerReady && !hudController.isUiActionAllowed(action)) {
            _showToast("Action is not allowed by UI contract: " + action)
            _recordUiEvent("ui.command.rejected", "palette", action)
            return
        }
        if (!win.controllerReady && !isLocalUiOnly) {
            _showToast("Controller not ready")
            return
        }

        if (action === "switch_mode") {
            if (hudController && command.payload && command.payload.mode)
                hudController.setTaskMode(command.payload.mode)
            _showToast("Done: switched mode")
            return
        }

        if (action === "open_drawer") {
            var drawerName = command.payload && command.payload.drawer ? command.payload.drawer : "tools"
            _openDrawer(drawerName)
            _showToast("Done: opened drawer")
            return
        }

        if (action === "run_doctor") {
            if (_ipcDisabled()) {
                _showToast("IPC disabled")
                return
            }
            hudController.refreshHealthStats()
            _showToast("Done: doctor report requested")
            return
        }

        if (action === "apply_queue") {
            hudController.queue_apply()
            _showToast("Done: apply candidate queued")
            return
        }

        if (action === "apply_confirm") {
            hudController.confirm_pending()
            _showToast("Done: apply confirm requested")
            return
        }

        if (action === "apply_reject") {
            hudController.reject_pending()
            _showToast("Done: apply rejection requested")
            return
        }

        if (action === "security_audit") {
            hudController.run_security_audit()
            _showToast("Done: security audit started")
            return
        }

        if (action === "refresh_timeline") {
            hudController.refresh_timeline()
            _showToast("Done: timeline refreshed")
            return
        }

        if (action === "voice_toggle") {
            hudController.toggle_voice_enabled()
            _showToast("Done: voice toggled")
            return
        }

        if (action === "voice_mute_toggle") {
            if (hudController.voiceMuted)
                hudController.voice_unmute()
            else
                hudController.voice_mute()
            _showToast("Done: voice mute toggled")
            return
        }

        if (action === "voice_stop") {
            hudController.voice_stop_speaking()
            _showToast("Done: voice output stopped")
            return
        }

        if (action === "voice_replay") {
            hudController.voice_replay_last()
            _showToast("Done: replay requested")
            return
        }

        if (action === "toggle_ipc_hint") {
            showIpcHint = !showIpcHint
            _showToast(showIpcHint ? "Done: IPC hint visible" : "Done: IPC hint hidden")
            return
        }

        if (action === "app_minimize") {
            _appMinimize()
            return
        }

        if (action === "app_close") {
            _showToast("Done: closing Nova")
            _appClose()
        }
        var elapsed = Date.now() - startedAt
        _recordUiEvent("ui.command.execute", "palette:" + action, String(elapsed))
        if (elapsed > stallMsThreshold)
            _trackRuntimeStall("palette:" + action, elapsed)
    }

    Shortcut {
        sequence: "Ctrl+K"
        onActivated: commandPalette.togglePalette()
    }

    Shortcut {
        sequence: "Esc"
        onActivated: {
            if (commandPalette.visible)
                commandPalette.closePalette()
        }
    }

    Shortcut {
        sequence: "Ctrl+Q"
        onActivated: win._appClose()
    }

    Shortcut {
        sequence: "Ctrl+W"
        onActivated: win._appClose()
    }

    Shortcut {
        sequence: "Alt+1"
        onActivated: win._openDrawer("tools")
    }

    Shortcut {
        sequence: "Alt+2"
        onActivated: win._openDrawer("attach")
    }

    Shortcut {
        sequence: "Alt+3"
        onActivated: win._openDrawer("health")
    }

    Shortcut {
        sequence: "Alt+4"
        onActivated: win._openDrawer("history")
    }

    Shortcut {
        sequence: "Alt+5"
        onActivated: win._openDrawer("voice")
    }

    Shortcut {
        sequence: "F6"
        onActivated: win._cycleFocusRegion(false)
    }

    Shortcut {
        sequence: "Shift+F6"
        onActivated: win._cycleFocusRegion(true)
    }

    Timer {
        id: runningTimer
        interval: 420
        onTriggered: win._markDoneSoon()
    }

    Timer {
        id: doneTimer
        interval: 1000
        onTriggered: win.statusState = "idle"
    }

    Timer {
        id: errorTimer
        interval: 2000
        onTriggered: win.statusState = "idle"
    }

    Connections {
        target: win.controllerReady ? hudController : null
        ignoreUnknownSignals: true

        function onStatusTextChanged() {
            if (!win.waitingAssistant)
                return
            if (!win.controllerReady)
                return
            var status = String(hudController.statusText || "").toLowerCase()
            if (status.indexOf("fail") >= 0 || status.indexOf("error") >= 0) {
                win.statusState = "error"
                win.waitingAssistant = false
                errorTimer.restart()
            }
        }

        function onVoiceChanged() {
            if (win.activeDrawer === "voice")
                win._refreshVoiceDevices()
        }
    }

    Component.onCompleted: {
        effectiveEffectsProfile = visualEffectsProfileName
        if (win.controllerReady)
            win._refreshVoiceDevices()
        win._activateFocusRegion("header")
        _recordUiEvent("ui.profile.active", "hud_v2", uiProfileName)
    }

    Rectangle {
        anchors.fill: parent
        radius: theme.radiusLg
        color: theme.bgSolid
        border.width: 1
        border.color: theme.borderSoft
        clip: true

        Rectangle {
            anchors.fill: parent
            color: theme.glowSoft
            opacity: win.effectiveEffectsProfile === "degraded" ? 0.12 : (win.effectiveEffectsProfile === "high_effects" ? 0.28 : 0.2)
            Behavior on opacity {
                NumberAnimation {
                    duration: motionSystem.fadeMs
                    easing.type: Easing.InOutQuad
                }
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 10

            TopHeader {
                Layout.fillWidth: true
                Layout.preferredHeight: 92
                theme: theme
                objectPrefix: "hudV2"
                compactMode: false
                titleText: "Nova Jarvis V3 | " + (win.controllerReady ? hudController.projectBadge : "starting...")
                statusText: win.controllerReady ? hudController.statusText : "initializing"
                voiceStatusText: win.controllerReady ? hudController.voiceStatusLine : "Voice: unavailable"
                modeText: "Mode: " + (win.controllerReady ? hudController.currentTaskMode : "general") + " | FX: " + win.effectiveEffectsProfile
                pendingText: (win.controllerReady && hudController.hasPendingApproval) ? "Pending: yes" : "Pending: no"
                capabilitiesText: "Capabilities: Chat | Tools | Attach | Health | History | Voice | Security | Timeline | Jarvis UX | Shortcuts: Ctrl+K, Alt+1..5, F6"
                showCapabilities: true
                onMinimizeRequested: win._appMinimize()
                onExitRequested: exitMenu.popup()
                onCloseRequested: win._appClose()
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: showIpcHint ? 30 : 0
                visible: showIpcHint
                radius: theme.radiusSm
                color: theme.bgGlass
                border.width: 1
                border.color: theme.borderSoft

                Label {
                    anchors.fill: parent
                    anchors.margins: 8
                    text: win._ipcDisabled() ? "IPC: disabled" : "IPC: enabled"
                    color: theme.textMuted
                    elide: Label.ElideRight
                    verticalAlignment: Text.AlignVCenter
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 10

                Rectangle {
                    Layout.preferredWidth: 280
                    Layout.minimumWidth: 240
                    Layout.maximumWidth: 320
                    Layout.fillHeight: true
                    radius: theme.radiusMd
                    color: theme.bgGlass
                    border.width: 1
                    border.color: theme.borderSoft

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 8

                        DrawerSelector {
                            Layout.fillWidth: true
                            theme: theme
                            objectPrefix: "hudV2"
                            compactMode: false
                            activeDrawer: win.activeDrawer
                            drawers: [
                                { id: "tools", title: "Tools" },
                                { id: "attach", title: "Attach" },
                                { id: "health", title: "Health" },
                                { id: "history", title: "History" },
                                { id: "voice", title: "Voice" }
                            ]
                            onDrawerRequested: function(drawerId) {
                                win._openDrawer(drawerId)
                            }
                        }

                        Loader {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            sourceComponent: {
                                if (win.activeDrawer === "attach")
                                    return attachDrawer
                                if (win.activeDrawer === "health")
                                    return healthDrawer
                                if (win.activeDrawer === "history")
                                    return historyDrawer
                                if (win.activeDrawer === "voice")
                                    return voiceDrawer
                                return toolsDrawer
                            }
                        }
                    }
                }

                PanelChatMain {
                    id: chatPane
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    theme: theme
                    model: win.controllerReady ? hudController.messagesModel : []
                    busy: win.controllerReady ? hudController.busy : false
                    currentTaskMode: win.controllerReady ? hudController.currentTaskMode : "general"
                    taskModesModel: win.controllerReady ? hudController.taskModesModel : []
                    statusState: win.statusState
                    voiceEnabled: win.controllerReady ? hudController.voiceEnabled : false
                    voiceMuted: win.controllerReady ? hudController.voiceMuted : false
                    voiceState: win.controllerReady ? hudController.voiceState : "idle"
                    voiceStatusLine: win.controllerReady ? hudController.voiceStatusLine : "Voice: unavailable"
                    voiceReplayAvailable: win.controllerReady ? String(hudController.voiceLastSpokenText || "").length > 0 : false
                    voicePushToTalk: win.controllerReady ? hudController.voicePushToTalk : true
                    voicePushActive: win.controllerReady ? hudController.voicePushActive : false
                    onSendRequested: function(message) {
                        if (!win.controllerReady)
                            return
                        win.statusState = "thinking"
                        win.waitingAssistant = true
                        hudController.send_message(message)
                    }
                    onAttachRequested: attachDialog.open()
                    onToolsRequested: {
                        if (win.controllerReady)
                            hudController.toggleToolsMenu()
                    }
                    onTaskModeChangedRequested: function(modeId) {
                        if (win.controllerReady)
                            hudController.setTaskMode(modeId)
                    }
                    onVoiceToggleRequested: {
                        if (win.controllerReady)
                            hudController.toggle_voice_enabled()
                    }
                    onVoicePushStartRequested: {
                        if (win.controllerReady)
                            hudController.voicePushStart()
                    }
                    onVoicePushStopRequested: {
                        if (win.controllerReady)
                            hudController.voicePushStop()
                    }
                    onVoiceMuteToggleRequested: {
                        if (!win.controllerReady)
                            return
                        if (hudController.voiceMuted)
                            hudController.voice_unmute()
                        else
                            hudController.voice_mute()
                    }
                    onVoiceStopRequested: {
                        if (win.controllerReady)
                            hudController.voice_stop_speaking()
                    }
                    onVoiceReplayRequested: {
                        if (win.controllerReady)
                            hudController.voice_replay_last()
                    }
                    onVoicePanelRequested: {
                        win._openDrawer("voice")
                        win._showToast("Done: voice panel opened")
                    }
                    onMessageObserved: function(payload) {
                        if (!payload)
                            return
                        var role = String(payload.role || "")
                        if (role !== "assistant")
                            return

                        win.waitingAssistant = false
                        var text = String(payload.text || "")
                        if (win._containsToolTrace(text)) {
                            win.statusState = "running"
                            runningTimer.restart()
                        } else {
                            win._markDoneSoon()
                        }
                    }
                }

                Rectangle {
                    Layout.preferredWidth: 260
                    Layout.minimumWidth: 220
                    Layout.maximumWidth: 300
                    Layout.fillHeight: true
                    radius: theme.radiusMd
                    color: theme.bgGlass
                    border.width: 1
                    border.color: theme.borderSoft

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 8

                        Label {
                            Layout.fillWidth: true
                            text: "Diagnostics Rail"
                            color: theme.textPrimary
                            font.bold: true
                        }

                        Label {
                            Layout.fillWidth: true
                            text: win.controllerReady ? hudController.statusText : "Core status unavailable"
                            color: theme.textSecondary
                            wrapMode: Label.Wrap
                        }

                        Label {
                            Layout.fillWidth: true
                            text: "Mode: " + (win.controllerReady ? hudController.currentTaskMode : "n/a")
                            color: theme.textMuted
                        }

                        Label {
                            Layout.fillWidth: true
                            text: "Voice: " + (win.controllerReady ? hudController.voiceStatusLine : "unavailable")
                            color: theme.textMuted
                            wrapMode: Label.Wrap
                        }

                        Label {
                            Layout.fillWidth: true
                            text: "Effects: " + win.effectiveEffectsProfile
                            color: theme.textMuted
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 1
                            color: theme.borderSoft
                            opacity: 0.6
                        }

                        Button {
                            objectName: "hudV2RailDoctorButton"
                            Layout.fillWidth: true
                            text: "Doctor Report"
                            onClicked: {
                                if (!win.controllerReady)
                                    return
                                hudController.refreshHealthStats()
                                win._openDrawer("health")
                                win._showToast("Done: doctor report refreshed")
                            }
                        }

                        Button {
                            Layout.fillWidth: true
                            text: "Open Tools"
                            onClicked: win._openDrawer("tools")
                        }

                        Button {
                            Layout.fillWidth: true
                            text: "Open History"
                            onClicked: win._openDrawer("history")
                        }

                        Button {
                            Layout.fillWidth: true
                            text: "Open Voice"
                            onClicked: win._openDrawer("voice")
                        }

                        Item {
                            Layout.fillHeight: true
                        }
                    }
                }
            }
        }
    }

    CommandPalette {
        id: commandPalette
        objectName: "hudV3CommandPalette"
        theme: theme
        onCommandTriggered: function(command) {
            win._runPaletteCommand(command)
        }
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
            onTriggered: win._appClose()
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
            width: 360
            wrapMode: Label.Wrap
            text: win.keepOllamaRunning
                ? "This will shutdown Nova core and close HUD. Ollama will be left running."
                : "This will shutdown Nova core and close HUD."
            color: theme.textPrimary
        }
        onAccepted: win._shutdownNovaAndClose()
    }

    Toast {
        id: toast
        theme: theme
        z: 100
    }

    FileDialog {
        id: attachDialog
        title: "Attach Files"
        fileMode: FileDialog.OpenFiles
        onAccepted: {
            if (!win.controllerReady)
                return
            hudController.attachFiles(selectedFiles)
            win._showToast("Done: files attached")
        }
    }

    Component {
        id: toolsDrawer

        PanelTools {
            theme: theme
            controllerReady: win.controllerReady
            objectPrefix: "hudV2"
            toolsBadge: win.controllerReady ? hudController.toolsBadge : "Tools: unavailable"
            confirmationSummary: win.controllerReady ? hudController.confirmationSummary : ""
            evidenceChip: win.controllerReady ? hudController.evidenceChip : "Evidence: n/a"
            actionsChip: win.controllerReady ? hudController.actionsChip : "Actions: n/a"
            risksChip: win.controllerReady ? hudController.risksChip : "Risks: n/a"
            applyEnabled: win.controllerReady ? hudController.applyEnabled : false
            hasPendingApproval: win.controllerReady ? hudController.hasPendingApproval : false
            confirmationReadOnly: win.controllerReady ? hudController.confirmationReadOnly : true
            confirmationLocked: win.controllerReady ? hudController.confirmationLocked : false
            onToggleToolsRequested: {
                if (!win.controllerReady)
                    return
                hudController.toggleToolsMenu()
                win._showToast("Done: tools menu toggled")
            }
            onQueueApplyRequested: {
                if (!win.controllerReady)
                    return
                hudController.queue_apply()
                win._showToast("Done: apply candidate queued")
            }
            onConfirmPendingRequested: {
                if (!win.controllerReady)
                    return
                hudController.confirm_pending()
                win._showToast("Done: pending confirmation sent")
            }
            onRejectPendingRequested: {
                if (!win.controllerReady)
                    return
                hudController.reject_pending()
                win._showToast("Done: pending rejection sent")
            }
            onRunSecurityRequested: {
                if (!win.controllerReady)
                    return
                hudController.run_security_audit()
                win._showToast("Done: security audit started")
            }
            onRefreshTimelineRequested: {
                if (!win.controllerReady)
                    return
                hudController.refresh_timeline()
                win._showToast("Done: timeline refreshed")
            }
        }
    }

    Component {
        id: attachDrawer

        PanelAttach {
            theme: theme
            objectPrefix: "hudV2"
            summaryText: win.controllerReady ? hudController.attachLastSummary : "No attachments yet."
            showSummaryList: false
            onChooseFilesRequested: {
                attachDialog.open()
                win._showToast("Done: attach dialog opened")
            }
        }
    }

    Component {
        id: healthDrawer

        PanelHealth {
            theme: theme
            controllerReady: win.controllerReady
            objectPrefix: "hudV2"
            healthStatsSummary: win.controllerReady ? hudController.healthStatsSummary : "Health unavailable."
            ollamaHealthSummary: win.controllerReady ? hudController.ollamaHealthSummary : "Ollama status unavailable."
            ollamaAvailableModels: win.controllerReady ? (hudController.ollamaAvailableModels || []) : []
            ollamaSessionModelOverride: win.controllerReady ? String(hudController.ollamaSessionModelOverride || "") : ""
            healthStatsModel: win.controllerReady ? hudController.healthStatsModel : []
            pendingSummary: "UI FX profile: " + win.effectiveEffectsProfile + " | focus region: " + win.focusRegion + " | last stall: " + win.lastStallMs + "ms"
            showPendingSummary: true
            onRefreshRequested: {
                if (!win.controllerReady)
                    return
                hudController.refreshHealthStats()
                win._showToast("Done: health stats refreshed")
            }
            onDoctorRequested: {
                if (win._ipcDisabled()) {
                    win._showToast("IPC disabled")
                    return
                }
                if (!win.controllerReady)
                    return
                hudController.refreshHealthStats()
                win._showToast("Done: doctor report requested")
            }
            onRefreshModelsRequested: {
                if (!win.controllerReady)
                    return
                hudController.refreshOllamaModels()
                win._showToast("Done: Ollama models refreshed")
            }
            onOllamaModelRequested: function(selected) {
                if (!win.controllerReady)
                    return
                hudController.setOllamaSessionModel(selected)
                win._showToast(selected === "default" ? "Done: Ollama model override cleared" : ("Done: Ollama model set to " + selected))
            }
        }
    }

    Component {
        id: historyDrawer

        PanelHistory {
            theme: theme
            objectPrefix: "hudV2"
            timelineSummary: win.controllerReady ? hudController.timelineSummary : "No timeline events."
            timelineModel: win.controllerReady ? hudController.timelineModel : []
            showTimelineList: true
            memorySearchQuery: win.memorySearchQuery
            memorySearchScope: win.memorySearchScope
            memorySearchStatus: win.memorySearchStatus
            memorySearchTotal: win.memorySearchTotal
            memorySearchOffset: win.memorySearchOffset
            memorySearchLimit: win.memorySearchLimit
            memorySearchResults: win.memorySearchResults
            onRefreshTimelineRequested: {
                if (!win.controllerReady)
                    return
                hudController.refresh_timeline()
                win._showToast("Done: timeline refreshed")
            }
            onMemorySearchRequested: function(resetOffset) {
                win._runMemorySearch(resetOffset)
                win._showToast(win.memorySearchStatus)
            }
            onMemoryQueryEdited: function(query) {
                win.memorySearchQuery = query
            }
            onMemoryScopeSelectionChanged: function(scope) {
                win.memorySearchScope = scope
            }
            onMemoryPrevRequested: {
                win.memorySearchOffset = Math.max(0, win.memorySearchOffset - win.memorySearchLimit)
                win._runMemorySearch(false)
            }
            onMemoryNextRequested: {
                win.memorySearchOffset = win.memorySearchOffset + win.memorySearchLimit
                win._runMemorySearch(false)
            }
        }
    }

    Component {
        id: voiceDrawer

        PanelVoice {
            theme: theme
            objectPrefix: "hudV2"
            voiceStatusLine: win.controllerReady ? hudController.voiceStatusLine : "Voice: unavailable"
            voiceProviderNames: win.controllerReady ? ("Providers: " + hudController.voiceProviderNames) : "Providers: n/a"
            voiceReadinessSummary: win.controllerReady ? hudController.voiceReadinessSummary : "Voice readiness unavailable."
            voicePushToTalk: win.controllerReady ? hudController.voicePushToTalk : true
            voicePushActive: win.controllerReady ? hudController.voicePushActive : false
            voiceEnabled: win.controllerReady ? hudController.voiceEnabled : false
            voiceMuted: win.controllerReady ? hudController.voiceMuted : false
            voiceDevices: win.voiceDevices
            voiceDeviceSelected: win.voiceDeviceSelected
            voiceLastTranscript: win.controllerReady ? String(hudController.voiceLastTranscript || "No transcript yet.") : "Voice controller unavailable."
            voiceLastSpokenText: win.controllerReady ? String(hudController.voiceLastSpokenText || "No spoken output yet.") : "No spoken output yet."
            onReadinessRequested: {
                if (!win.controllerReady)
                    return
                hudController.refreshVoiceReadiness()
                win._showToast("Done: voice readiness checked")
            }
            onMicToggleRequested: {
                if (!win.controllerReady)
                    return
                hudController.toggle_voice_enabled()
                win._showToast("Done: voice toggled")
            }
            onMicPushStartRequested: {
                if (win.controllerReady)
                    hudController.voicePushStart()
            }
            onMicPushStopRequested: {
                if (win.controllerReady)
                    hudController.voicePushStop()
            }
            onMuteToggleRequested: {
                if (!win.controllerReady)
                    return
                if (hudController.voiceMuted)
                    hudController.voice_unmute()
                else
                    hudController.voice_mute()
                win._showToast("Done: voice mute toggled")
            }
            onStopRequested: {
                if (!win.controllerReady)
                    return
                hudController.voice_stop_speaking()
                win._showToast("Done: voice output stopped")
            }
            onReplayRequested: {
                if (!win.controllerReady)
                    return
                hudController.voice_replay_last()
                win._showToast("Done: voice replay requested")
            }
            onDeviceSelected: function(selected) {
                win.voiceDeviceSelected = selected
                if (win.controllerReady)
                    hudController.set_voice_device(selected)
                win._showToast("Done: voice input device updated")
            }
            onRefreshDevicesRequested: {
                win._refreshVoiceDevices()
                win._showToast("Done: voice devices refreshed")
            }
        }
    }
}

