import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: panel
    property var theme
    property string objectPrefix: "hudV2"
    property string readinessButtonSuffix: "VoiceDrawerReadinessButton"
    property string voiceStatusLine: "Voice: unavailable"
    property string voiceProviderNames: "Providers unavailable."
    property string voiceReadinessSummary: "Voice readiness unavailable."
    property bool voicePushToTalk: true
    property bool voicePushActive: false
    property bool voiceEnabled: false
    property bool voiceMuted: false
    property var voiceDevices: ["default"]
    property string voiceDeviceSelected: "default"
    property string voiceLastTranscript: "No transcript yet."
    property string voiceLastSpokenText: "No spoken output yet."

    signal readinessRequested()
    signal micToggleRequested()
    signal micPushStartRequested()
    signal micPushStopRequested()
    signal muteToggleRequested()
    signal stopRequested()
    signal replayRequested()
    signal deviceSelected(string deviceName)
    signal refreshDevicesRequested()

    spacing: 8

    Label {
        Layout.fillWidth: true
        text: panel.voiceStatusLine
        color: panel.theme ? panel.theme.textSecondary : "#d9ac63"
        wrapMode: Label.Wrap
    }

    Label {
        Layout.fillWidth: true
        text: panel.voiceProviderNames
        color: panel.theme ? panel.theme.textMuted : "#b68d57"
        wrapMode: Label.Wrap
    }

    Label {
        Layout.fillWidth: true
        text: panel.voiceReadinessSummary
        color: panel.theme ? panel.theme.textSecondary : "#d9ac63"
        wrapMode: Label.Wrap
    }

    Label {
        Layout.fillWidth: true
        text: panel.voicePushToTalk ? "Voice mode: push-to-talk (hold Mic)" : "Voice mode: always-listen"
        color: panel.theme ? panel.theme.textMuted : "#b68d57"
        wrapMode: Label.Wrap
    }

    Button {
        objectName: panel.objectPrefix + panel.readinessButtonSuffix
        Layout.fillWidth: true
        text: "Check Voice Readiness"
        onClicked: panel.readinessRequested()
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 6

        Button {
            objectName: panel.objectPrefix + "VoiceDrawerMicButton"
            Layout.fillWidth: true
            text: panel.voicePushToTalk ? (panel.voicePushActive ? "Mic On" : "Mic Off") : (panel.voiceEnabled ? "Mic On" : "Mic Off")
            onPressed: {
                if (panel.voicePushToTalk)
                    panel.micPushStartRequested()
            }
            onReleased: {
                if (panel.voicePushToTalk)
                    panel.micPushStopRequested()
            }
            onCanceled: {
                if (panel.voicePushToTalk)
                    panel.micPushStopRequested()
            }
            onClicked: {
                if (!panel.voicePushToTalk)
                    panel.micToggleRequested()
            }
        }

        Button {
            objectName: panel.objectPrefix + "VoiceDrawerMuteButton"
            Layout.fillWidth: true
            text: panel.voiceMuted ? "Unmute" : "Mute"
            enabled: panel.voiceEnabled
            onClicked: panel.muteToggleRequested()
        }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 6

        Button {
            objectName: panel.objectPrefix + "VoiceDrawerStopButton"
            Layout.fillWidth: true
            text: "Stop Voice"
            enabled: panel.voiceEnabled
            onClicked: panel.stopRequested()
        }

        Button {
            objectName: panel.objectPrefix + "VoiceDrawerReplayButton"
            Layout.fillWidth: true
            text: "Replay Last"
            enabled: panel.voiceEnabled && String(panel.voiceLastSpokenText || "").length > 0
            onClicked: panel.replayRequested()
        }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 6

        ComboBox {
            id: voiceDeviceCombo
            objectName: panel.objectPrefix + "VoiceDeviceCombo"
            Layout.fillWidth: true
            model: panel.voiceDevices
            currentIndex: {
                if (!model || model.length <= 0)
                    return -1
                var wanted = String(panel.voiceDeviceSelected || "default")
                for (var i = 0; i < model.length; i++) {
                    if (String(model[i]) === wanted)
                        return i
                }
                return 0
            }
            onActivated: {
                if (!model || currentIndex < 0 || currentIndex >= model.length)
                    return
                panel.deviceSelected(String(model[currentIndex] || "default"))
            }
        }

        Button {
            objectName: panel.objectPrefix + "VoiceRefreshDevicesButton"
            text: "Refresh Devices"
            onClicked: panel.refreshDevicesRequested()
        }
    }

    Label {
        Layout.fillWidth: true
        text: "Last Transcript: " + panel.voiceLastTranscript
        color: panel.theme ? panel.theme.textMuted : "#b68d57"
        wrapMode: Label.Wrap
    }

    Label {
        Layout.fillWidth: true
        text: "Last Spoken Output: " + panel.voiceLastSpokenText
        color: panel.theme ? panel.theme.textMuted : "#b68d57"
        wrapMode: Label.Wrap
    }
}
