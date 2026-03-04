import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import QtQuick.Window
import "../../common_ui" as Common
import "../components"
import "../theme"
import "../panels"

Window {
    id: win
    visible: true
    width: 1180
    height: 760
    minimumWidth: 920
    minimumHeight: 560
    color: "transparent"
    title: "Nova Jarvis V3 Compact"

    function _resolveController() {
        if (typeof quickPanelController !== "undefined" && quickPanelController) return quickPanelController
        if (typeof hudController !== "undefined" && hudController) return hudController
        return null
    }

    property var controller: _resolveController()
    property bool controllerReady: controller !== null
    property string uiProfileName: (typeof uiProfile !== "undefined" && uiProfile !== null) ? String(uiProfile) : "compact"
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
    property string statusState: "idle"
    property bool waitingAssistant: false
    property string activeDrawer: "tools"
    property var voiceDevices: ["default"]
    property string voiceDeviceSelected: "default"
    property string memorySearchScope: "general"
    property string memorySearchQuery: ""
    property int memorySearchOffset: 0
    property int memorySearchLimit: 10
    property int memorySearchTotal: 0
    property var memorySearchResults: []
    property string memorySearchStatus: "Memory search ready."
    property bool keepOllamaRunning: true

    function _showToast(text) { toast.showToast(String(text || "Done")) }
    function _recordUiEvent(eventKey, source, value) {
        if (!win.controllerReady)
            return
        try {
            win.controller.recordUiEvent(String(eventKey || ""), String(source || ""), String(value || ""))
        } catch (e) {
        }
    }
    function _appClose() { win.close() }
    function _shutdownNovaAndClose() {
        if (!win.controllerReady) {
            win.close()
            return
        }
        var startedAt = Date.now()
        var response = win.controller.shutdownNova(Boolean(win.keepOllamaRunning), 15, true)
        var ok = response && Boolean(response.ok)
        var errorText = response && response.error ? String(response.error) : ""
        var watchdog = response && response.watchdog ? response.watchdog : ({})
        var verified = watchdog && watchdog.verified_ports_closed ? watchdog.verified_ports_closed : ({})
        if (!ok)
            win._showToast(errorText.length ? ("Shutdown failed: " + errorText) : "Shutdown failed")
        else if (!Boolean(verified.ipc) || !Boolean(verified.events))
            win._showToast("Shutdown requested; core may still be stopping")
        else
            win._showToast("Done: Nova core stopped")
        var elapsed = Date.now() - startedAt
        win._recordUiEvent("ui.command.execute", "shutdown_nova", String(elapsed))
        win.close()
    }
    function _appMinimize() { win.showMinimized() }
    function _markDoneSoon() { statusDoneTimer.restart() }

    function _refreshVoiceDevices() {
        if (!win.controllerReady) {
            win.voiceDevices = ["default"]
            win.voiceDeviceSelected = "default"
            return
        }
        var listed = win.controller.voice_input_devices()
        if (!listed || listed.length <= 0) listed = ["default"]
        win.voiceDevices = listed
        win.voiceDeviceSelected = String(win.controller.voiceCurrentDevice || "default")
    }

    function _openDrawer(name) {
        win.activeDrawer = String(name || "tools").toLowerCase()
        if (win.activeDrawer === "voice") win._refreshVoiceDevices()
        if (win.activeDrawer === "history" && win.controllerReady) win.controller.refresh_timeline()
        win._recordUiEvent("ui.panel.switch", "quick_panel_v2", win.activeDrawer)
    }

    function _trackRuntimeStall(sourceKey, elapsed) {
        var stallMs = Number(elapsed || 0)
        if (stallMs <= 0)
            return
        lastStallMs = Math.floor(stallMs)
        win._recordUiEvent("ui.performance.stall_ms", String(sourceKey || ""), String(lastStallMs))
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
            win._recordUiEvent("ui.effects.profile_transition", String(sourceKey || ""), previousProfile + "->degraded")
            if (!degradedActivationEmitted) {
                degradedActivationEmitted = true
                win._recordUiEvent("ui.effects.degraded_activated", String(sourceKey || ""), String(lastStallMs))
            }
            win._showToast("Visual effects auto-switched to degraded mode")
            return
        }
        if (effectiveEffectsProfile === "high_effects" && stallMs >= stallBalancedThresholdMs && runtimeStallCount >= stallCountToBalanced) {
            effectiveEffectsProfile = "balanced"
            win._recordUiEvent("ui.effects.profile_transition", String(sourceKey || ""), "high_effects->balanced")
            win._showToast("Visual effects switched to balanced mode")
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
            return "quickPanelV2TopMinimizeButton"
        if (region === "nav")
            return "quickPanelV2DrawerToolsButton"
        if (region === "content")
            return "hudV2ComposerInputField"
        if (region === "rail")
            return "quickPanelV2RailDoctorButton"
        return "quickPanelV2TopMinimizeButton"
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
        if (resetOffset) win.memorySearchOffset = 0
        var payload = win.controller.memorySearchPage(q, String(win.memorySearchScope || "general"), Number(win.memorySearchLimit || 10), Number(win.memorySearchOffset || 0))
        if (!payload || String(payload.status || "error") !== "ok") {
            win.memorySearchResults = []
            win.memorySearchTotal = 0
            var msg = payload && payload.message ? String(payload.message) : "unknown error"
            win.memorySearchStatus = "Memory search failed: " + msg
            return
        }
        var hits = payload.hits || []
        win.memorySearchResults = hits
        win.memorySearchTotal = Number(payload.total || hits.length || 0)
        win.memorySearchStatus = hits.length > 0 ? ("Memory search returned " + hits.length + " results.") : "Memory search returned no results."
        var elapsed = Date.now() - startedAt
        win._recordUiEvent("ui.command.execute", "memory_search", String(elapsed))
        if (elapsed > stallMsThreshold)
            win._trackRuntimeStall("memory_search", elapsed)
    }

    function _runPaletteCommand(command) {
        if (!command || !command.actionKind) return
        var startedAt = Date.now()
        var action = String(command.actionKind || "")
        var localOnly = action === "app_minimize" || action === "app_close"
        if (win.controllerReady && !win.controller.isUiActionAllowed(action)) {
            _showToast("Action is not allowed by UI contract: " + action)
            win._recordUiEvent("ui.command.rejected", "palette", action)
            return
        }
        if (!win.controllerReady && !localOnly) { _showToast("Controller not ready"); return }
        if (action === "switch_mode") { if (command.payload && command.payload.mode) win.controller.setTaskMode(command.payload.mode); _showToast("Done: switched mode") }
        else if (action === "open_drawer") { var drawerName = command.payload && command.payload.drawer ? String(command.payload.drawer) : "tools"; win._openDrawer(drawerName); _showToast("Done: opened drawer") }
        else if (action === "run_doctor") { win.controller.refreshHealthStats(); _showToast("Done: health refreshed") }
        else if (action === "apply_queue") { win.controller.queue_apply(); _showToast("Done: apply queued") }
        else if (action === "apply_confirm") { win.controller.confirm_pending(); _showToast("Done: pending confirmed") }
        else if (action === "apply_reject") { win.controller.reject_pending(); _showToast("Done: pending rejected") }
        else if (action === "security_audit") { win.controller.run_security_audit(); _showToast("Done: security audit started") }
        else if (action === "refresh_timeline") { win.controller.refresh_timeline(); win._openDrawer("history"); _showToast("Done: timeline refreshed") }
        else if (action === "voice_toggle") { win.controller.toggle_voice_enabled() }
        else if (action === "voice_mute_toggle") { if (win.controller.voiceMuted) win.controller.voice_unmute(); else win.controller.voice_mute() }
        else if (action === "voice_stop") { win.controller.voice_stop_speaking() }
        else if (action === "voice_replay") { win.controller.voice_replay_last() }
        else if (action === "app_minimize") { _appMinimize() }
        else if (action === "app_close") { _appClose() }

        var elapsed = Date.now() - startedAt
        win._recordUiEvent("ui.command.execute", "palette:" + action, String(elapsed))
        if (elapsed > stallMsThreshold)
            win._trackRuntimeStall("palette:" + action, elapsed)
    }

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
    Shortcut { sequence: "Ctrl+K"; onActivated: commandPalette.togglePalette() }
    Shortcut { sequence: "Esc"; onActivated: { if (commandPalette.visible) commandPalette.closePalette() } }
    Shortcut { sequence: "Ctrl+Q"; onActivated: win._appClose() }
    Shortcut { sequence: "Ctrl+W"; onActivated: win._appClose() }
    Shortcut { sequence: "Alt+1"; onActivated: win._openDrawer("tools") }
    Shortcut { sequence: "Alt+2"; onActivated: win._openDrawer("attach") }
    Shortcut { sequence: "Alt+3"; onActivated: win._openDrawer("health") }
    Shortcut { sequence: "Alt+4"; onActivated: win._openDrawer("history") }
    Shortcut { sequence: "Alt+5"; onActivated: win._openDrawer("voice") }
    Shortcut { sequence: "F6"; onActivated: win._cycleFocusRegion(false) }
    Shortcut { sequence: "Shift+F6"; onActivated: win._cycleFocusRegion(true) }

    Timer {
        id: statusDoneTimer
        interval: 850
        repeat: false
        onTriggered: {
            if (win.waitingAssistant) return
            win.statusState = "done"
        }
    }

    Connections {
        target: win.controllerReady ? win.controller : null
        function onBusyChanged() {
            if (!win.controllerReady) return
            if (win.controller.busy) win.statusState = "thinking"
        }
        function onVoiceChanged() {
            if (!win.controllerReady) return
            if (win.activeDrawer === "voice") win._refreshVoiceDevices()
        }
    }

    Component.onCompleted: {
        effectiveEffectsProfile = visualEffectsProfileName
        if (win.controllerReady)
            win._refreshVoiceDevices()
        win._activateFocusRegion("header")
        win._recordUiEvent("ui.profile.active", "quick_panel_v2", win.uiProfileName)
    }

    Component {
        id: toolsDrawer
        PanelTools {
            theme: theme
            controllerReady: win.controllerReady
            objectPrefix: "quickPanelV2"
            showCatalog: true
            toolsCatalogModel: win.controllerReady ? win.controller.toolsCatalogModel : []
            toolsBadge: win.controllerReady ? win.controller.toolsBadge : "Tools: unavailable"
            confirmationSummary: ""
            toggleToolsText: "Toggle Tools"
            queueApplyText: "Queue Apply"
            confirmPendingText: "Confirm"
            rejectPendingText: "Reject"
            runSecurityText: "Run Security"
            refreshTimelineText: "Refresh Timeline"
            applyEnabled: true
            hasPendingApproval: win.controllerReady ? win.controller.hasPendingApproval : false
            confirmationReadOnly: false
            confirmationLocked: false
            onToggleToolsRequested: if (win.controllerReady) win.controller.toggleToolsMenu()
            onQueueApplyRequested: if (win.controllerReady) win.controller.queue_apply()
            onConfirmPendingRequested: if (win.controllerReady) win.controller.confirm_pending()
            onRejectPendingRequested: if (win.controllerReady) win.controller.reject_pending()
            onRunSecurityRequested: if (win.controllerReady) win.controller.run_security_audit()
            onRefreshTimelineRequested: if (win.controllerReady) { win.controller.refresh_timeline(); win._openDrawer("history") }
        }
    }

    Component {
        id: attachDrawer
        PanelAttach {
            theme: theme
            objectPrefix: "quickPanelV2"
            summaryText: win.controllerReady ? win.controller.attachLastSummary : "No attachments yet."
            summaryModel: win.controllerReady ? win.controller.attachSummaryModel : []
            showSummaryList: true
            onChooseFilesRequested: attachDialog.open()
        }
    }
    Component {
        id: healthDrawer
        PanelHealth {
            theme: theme
            controllerReady: win.controllerReady
            objectPrefix: "quickPanelV2"
            healthStatsSummary: win.controllerReady ? win.controller.healthStatsSummary : "Health stats unavailable."
            ollamaHealthSummary: win.controllerReady ? win.controller.ollamaHealthSummary : "Local LLM status unavailable."
            ollamaAvailableModels: win.controllerReady ? (win.controller.ollamaAvailableModels || []) : []
            ollamaSessionModelOverride: win.controllerReady ? String(win.controller.ollamaSessionModelOverride || "") : ""
            healthStatsModel: win.controllerReady ? win.controller.healthStatsModel : []
            pendingSummary: "UI FX profile: " + win.effectiveEffectsProfile + " | focus region: " + win.focusRegion + " | last stall: " + win.lastStallMs + "ms"
            showPendingSummary: true
            onRefreshRequested: if (win.controllerReady) win.controller.refreshHealthStats()
            onDoctorRequested: if (win.controllerReady) win.controller.refreshHealthStats()
            onRefreshModelsRequested: if (win.controllerReady) win.controller.refreshOllamaModels()
            onOllamaModelRequested: function(selected) {
                if (!win.controllerReady)
                    return
                win.controller.setOllamaSessionModel(selected)
                win._showToast(selected === "default" ? "Done: Ollama model override cleared" : ("Done: Ollama model set to " + selected))
            }
        }
    }

    Component {
        id: historyDrawer
        PanelHistory {
            theme: theme
            objectPrefix: "quickPanelV2"
            timelineSummary: win.controllerReady ? win.controller.timelineSummary : "Timeline unavailable."
            timelineModel: win.controllerReady ? win.controller.timelineModel : []
            showTimelineList: true
            memorySearchQuery: win.memorySearchQuery
            memorySearchScope: win.memorySearchScope
            memorySearchStatus: win.memorySearchStatus
            memorySearchTotal: win.memorySearchTotal
            memorySearchOffset: win.memorySearchOffset
            memorySearchLimit: win.memorySearchLimit
            memorySearchResults: win.memorySearchResults
            onRefreshTimelineRequested: if (win.controllerReady) win.controller.refresh_timeline()
            onMemorySearchRequested: function(resetOffset) { win._runMemorySearch(resetOffset); win._showToast(win.memorySearchStatus) }
            onMemoryQueryEdited: function(query) { win.memorySearchQuery = query }
            onMemoryScopeSelectionChanged: function(scope) { win.memorySearchScope = scope }
            onMemoryPrevRequested: { win.memorySearchOffset = Math.max(0, win.memorySearchOffset - win.memorySearchLimit); win._runMemorySearch(false) }
            onMemoryNextRequested: { win.memorySearchOffset = win.memorySearchOffset + win.memorySearchLimit; win._runMemorySearch(false) }
        }
    }
    Component {
        id: voiceDrawer
        PanelVoice {
            theme: theme
            objectPrefix: "quickPanelV2"
            readinessButtonSuffix: "VoiceReadinessButton"
            voiceStatusLine: win.controllerReady ? win.controller.voiceStatusLine : "Voice: unavailable"
            voiceProviderNames: win.controllerReady ? win.controller.voiceProviderNames : "Providers unavailable."
            voiceReadinessSummary: win.controllerReady ? win.controller.voiceReadinessSummary : "Voice readiness unavailable."
            voicePushToTalk: win.controllerReady ? win.controller.voicePushToTalk : true
            voicePushActive: win.controllerReady ? win.controller.voicePushActive : false
            voiceEnabled: win.controllerReady ? win.controller.voiceEnabled : false
            voiceMuted: win.controllerReady ? win.controller.voiceMuted : false
            voiceDevices: win.voiceDevices
            voiceDeviceSelected: win.voiceDeviceSelected
            voiceLastTranscript: win.controllerReady ? String(win.controller.voiceLastTranscript || "No transcript yet.") : "controller unavailable"
            voiceLastSpokenText: win.controllerReady ? String(win.controller.voiceLastSpokenText || "No spoken output yet.") : "controller unavailable"
            onReadinessRequested: if (win.controllerReady) { win.controller.refreshVoiceReadiness(); win._showToast("Done: voice readiness checked") }
            onMicToggleRequested: if (win.controllerReady) win.controller.toggle_voice_enabled()
            onMicPushStartRequested: if (win.controllerReady && win.controller.voicePushToTalk) win.controller.voicePushStart()
            onMicPushStopRequested: if (win.controllerReady && win.controller.voicePushToTalk) win.controller.voicePushStop()
            onMuteToggleRequested: if (win.controllerReady) { if (win.controller.voiceMuted) win.controller.voice_unmute(); else win.controller.voice_mute() }
            onStopRequested: if (win.controllerReady) win.controller.voice_stop_speaking()
            onReplayRequested: if (win.controllerReady) win.controller.voice_replay_last()
            onDeviceSelected: function(selected) {
                if (!win.controllerReady)
                    return
                win.voiceDeviceSelected = selected
                win.controller.set_voice_device(selected)
                win._showToast("Done: voice device selected")
            }
            onRefreshDevicesRequested: { win._refreshVoiceDevices(); win._showToast("Done: voice devices refreshed") }
        }
    }

    Rectangle {
        anchors.fill: parent
        radius: theme.radiusLg
        color: theme.bgSolid
        border.width: 1
        border.color: theme.borderSoft

        Rectangle {
            anchors.fill: parent
            radius: theme.radiusLg
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
                Layout.preferredHeight: 58
                theme: theme
                objectPrefix: "quickPanelV2"
                compactMode: true
                titleText: "Nova Jarvis V3 Compact | Ctrl+K Palette"
                statusText: win.controllerReady ? win.controller.statusText : "initializing"
                modeText: win.controllerReady ? ("Mode: " + win.controller.currentTaskMode + " | FX: " + win.effectiveEffectsProfile) : ("Mode: n/a | FX: " + win.effectiveEffectsProfile)
                capabilitiesText: "Shortcuts: Ctrl+K, Alt+1..5, F6 | Jarvis UX"
                showCapabilities: true
                onMinimizeRequested: win._appMinimize()
                onExitRequested: exitMenu.popup()
                onCloseRequested: win._appClose()
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 10

                Rectangle {
                    Layout.preferredWidth: 360
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
                            objectPrefix: "quickPanelV2"
                            compactMode: true
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
                            id: quickDrawerLoader
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            sourceComponent: {
                                if (win.activeDrawer === "attach") return attachDrawer
                                if (win.activeDrawer === "health") return healthDrawer
                                if (win.activeDrawer === "history") return historyDrawer
                                if (win.activeDrawer === "voice") return voiceDrawer
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
                    model: win.controllerReady ? win.controller.messagesModel : []
                    busy: win.controllerReady ? win.controller.busy : false
                    currentTaskMode: win.controllerReady ? win.controller.currentTaskMode : "general"
                    taskModesModel: win.controllerReady ? win.controller.taskModesModel : []
                    statusState: win.statusState
                    voiceEnabled: win.controllerReady ? win.controller.voiceEnabled : false
                    voiceMuted: win.controllerReady ? win.controller.voiceMuted : false
                    voiceState: win.controllerReady ? win.controller.voiceState : "disabled"
                    voiceStatusLine: win.controllerReady ? win.controller.voiceStatusLine : "Voice: unavailable"
                    voiceReplayAvailable: win.controllerReady ? String(win.controller.voiceLastSpokenText || "").length > 0 : false
                    voicePushToTalk: win.controllerReady ? win.controller.voicePushToTalk : true
                    voicePushActive: win.controllerReady ? win.controller.voicePushActive : false
                    onSendRequested: function(message) { if (!win.controllerReady) return; win.statusState = "thinking"; win.waitingAssistant = true; win.controller.send_message(message) }
                    onAttachRequested: attachDialog.open()
                    onToolsRequested: { if (win.controllerReady) win.controller.toggleToolsMenu(); win._openDrawer("tools") }
                    onTaskModeChangedRequested: function(modeId) { if (win.controllerReady) win.controller.setTaskMode(modeId) }
                    onVoiceToggleRequested: { if (win.controllerReady) win.controller.toggle_voice_enabled() }
                    onVoicePushStartRequested: { if (win.controllerReady) win.controller.voicePushStart() }
                    onVoicePushStopRequested: { if (win.controllerReady) win.controller.voicePushStop() }
                    onVoiceMuteToggleRequested: { if (!win.controllerReady) return; if (win.controller.voiceMuted) win.controller.voice_unmute(); else win.controller.voice_mute() }
                    onVoiceStopRequested: { if (win.controllerReady) win.controller.voice_stop_speaking() }
                    onVoiceReplayRequested: { if (win.controllerReady) win.controller.voice_replay_last() }
                    onVoicePanelRequested: { win._openDrawer("voice"); win._showToast("Done: opened voice drawer") }
                    onMessageObserved: function(payload) {
                        if (!payload) return
                        var role = String(payload.role || "")
                        if (role !== "assistant") return
                        win.waitingAssistant = false
                        win._markDoneSoon()
                    }
                }

                Rectangle {
                    Layout.preferredWidth: 220
                    Layout.minimumWidth: 190
                    Layout.maximumWidth: 260
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
                            text: "Diagnostics"
                            color: theme.textPrimary
                            font.bold: true
                        }

                        Label {
                            Layout.fillWidth: true
                            text: "FX: " + win.effectiveEffectsProfile
                            color: theme.textMuted
                            wrapMode: Label.Wrap
                        }

                        Label {
                            Layout.fillWidth: true
                            text: "Voice: " + (win.controllerReady ? win.controller.voiceStatusLine : "unavailable")
                            color: theme.textMuted
                            wrapMode: Label.Wrap
                        }

                        Button {
                            objectName: "quickPanelV2RailDoctorButton"
                            Layout.fillWidth: true
                            text: "Doctor"
                            onClicked: {
                                if (!win.controllerReady)
                                    return
                                win.controller.refreshHealthStats()
                                win._openDrawer("health")
                                win._showToast("Done: doctor report refreshed")
                            }
                        }

                        Button {
                            Layout.fillWidth: true
                            text: "Voice"
                            onClicked: win._openDrawer("voice")
                        }

                        Button {
                            Layout.fillWidth: true
                            text: "History"
                            onClicked: win._openDrawer("history")
                        }

                        Item { Layout.fillHeight: true }
                    }
                }
            }
        }
    }

    CommandPalette {
        id: commandPalette
        objectName: "quickPanelV3CommandPalette"
        theme: theme
        onCommandTriggered: function(command) { win._runPaletteCommand(command) }
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
            width: 320
            wrapMode: Label.Wrap
            text: win.keepOllamaRunning
                ? "This will shutdown Nova core and close HUD. Ollama will be left running."
                : "This will shutdown Nova core and close HUD."
            color: theme.textPrimary
        }
        onAccepted: win._shutdownNovaAndClose()
    }

    Toast { id: toast; theme: theme; z: 100 }

    FileDialog {
        id: attachDialog
        title: "Attach Files"
        fileMode: FileDialog.OpenFiles
        onAccepted: {
            if (!win.controllerReady) return
            win.controller.attachFiles(selectedFiles)
            win._showToast("Done: files attached")
        }
    }
}

