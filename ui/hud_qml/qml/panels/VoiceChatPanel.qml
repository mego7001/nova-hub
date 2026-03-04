import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    property var theme
    property var controller
    property var deviceOptions: ["default"]

    color: theme.glassBg
    border.color: theme.glassBorder
    border.width: 1
    radius: 12
    clip: true

    // Inner highlight
    Rectangle {
        anchors.fill: parent
        anchors.margins: 1
        color: "transparent"
        border.color: theme.glassHighlight
        border.width: 1
        radius: parent.radius - 1
    }

    function _refreshDeviceOptions() {
        if (!controller) {
            deviceOptions = ["default"]
            return
        }
        const opts = controller.voice_input_devices()
        if (opts && opts.length > 0)
            deviceOptions = opts
        else
            deviceOptions = ["default"]
        _syncCurrentDevice()
    }

    function _syncCurrentDevice() {
        if (!controller)
            return
        const current = controller.voiceCurrentDevice || "default"
        let idx = -1
        for (let i = 0; i < deviceOptions.length; i++) {
            if (String(deviceOptions[i]) === String(current)) {
                idx = i
                break
            }
        }
        if (idx >= 0)
            deviceCombo.currentIndex = idx
    }

    Component.onCompleted: _refreshDeviceOptions()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Label {
                text: "VOICE INTELLIGENCE"
                color: theme.textPrimary
                font.family: theme.titleFont
                font.pixelSize: 11
                font.bold: true
                font.letterSpacing: 1.5
            }
            Switch {
                id: enabledSwitch
                checked: controller ? controller.voiceEnabled : false
                palette.active.highlight: theme.accent
                onToggled: {
                    if (controller)
                        controller.set_voice_enabled(checked)
                }
            }

            Item { Layout.fillWidth: true }

            Rectangle {
                radius: 6
                color: controller && controller.voiceMuted ? Qt.rgba(1.0, 0.7, 0.3, 0.1) : Qt.rgba(0.0, 0.9, 1.0, 0.08)
                border.width: 1
                border.color: controller && controller.voiceMuted ? theme.warning : theme.accent
                Layout.preferredHeight: 22
                Layout.preferredWidth: 64
                Label {
                    anchors.centerIn: parent
                    text: controller && controller.voiceMuted ? "MUTED" : "LIVE"
                    color: controller && controller.voiceMuted ? theme.warning : theme.accent
                    font.family: theme.titleFont
                    font.bold: true
                    font.pixelSize: 10
                    font.letterSpacing: 1.1
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Label {
                text: "INPUT SOURCE"
                color: theme.textDim
                font.family: theme.titleFont
                font.pixelSize: 9
                font.bold: true
                font.letterSpacing: 1.1
            }
            ComboBox {
                id: deviceCombo
                Layout.fillWidth: true
                model: root.deviceOptions
                enabled: controller ? !controller.voiceEnabled : true
                background: Rectangle {
                    radius: 8
                    color: Qt.rgba(1.0, 1.0, 1.0, 0.04)
                    border.width: 1
                    border.color: theme.glassHighlight
                }
                contentItem: Text {
                    text: deviceCombo.currentText
                    color: theme.textPrimary
                    leftPadding: 10
                    verticalAlignment: Text.AlignVCenter
                    font.family: theme.titleFont
                    font.pixelSize: 10
                    font.bold: true
                }
                onActivated: {
                    if (controller)
                        controller.set_voice_device(currentText)
                }
            }
            Button {
                text: "REFRESH"
                flat: true
                onClicked: root._refreshDeviceOptions()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: theme.glassHighlight
            opacity: 0.3
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4
            Label {
                text: "SYSTEM CHANNEL"
                color: theme.textDim
                font.family: theme.titleFont
                font.pixelSize: 9
                font.bold: true
                font.letterSpacing: 1.1
            }
            Label {
                Layout.fillWidth: true
                text: controller ? (controller.voiceState + " • " + controller.voiceProviderNames).toUpperCase() : "DISCONNECTED"
                color: theme.positive
                font.family: theme.titleFont
                font.pixelSize: 10
                font.bold: true
                font.letterSpacing: 1.1
            }
            Label {
                Layout.fillWidth: true
                text: controller ? controller.voiceStatusLine.toUpperCase() : "SYSTEM OFFLINE"
                color: theme.textDim
                wrapMode: Label.Wrap
                font.family: theme.titleFont
                font.pixelSize: 9
                font.bold: true
                opacity: 0.8
            }
        }

        Label {
            text: "TRANSCRIPT FEED"
            color: theme.accent
            font.family: theme.titleFont
            font.pixelSize: 10
            font.bold: true
            font.letterSpacing: 1.2
            Layout.topMargin: 4
        }
        TextArea {
            Layout.fillWidth: true
            Layout.preferredHeight: 70
            readOnly: true
            selectByMouse: true
            wrapMode: TextEdit.Wrap
            text: controller ? controller.voiceLastTranscript : ""
            color: theme.textPrimary
            font.family: theme.bodyFont
            font.pixelSize: 13
            background: Rectangle {
                color: Qt.rgba(0.0, 0.0, 0.0, 0.25)
                border.width: 1
                border.color: theme.glassHighlight
                radius: 10
            }
        }

        Label {
            text: "REPLY SYNTHESIS"
            color: theme.positive
            font.family: theme.titleFont
            font.pixelSize: 10
            font.bold: true
            font.letterSpacing: 1.2
            Layout.topMargin: 4
        }
        TextArea {
            Layout.fillWidth: true
            Layout.preferredHeight: 70
            readOnly: true
            selectByMouse: true
            wrapMode: TextEdit.Wrap
            text: controller ? controller.voiceLastSpokenText : ""
            color: theme.textPrimary
            font.family: theme.bodyFont
            font.pixelSize: 13
            background: Rectangle {
                color: Qt.rgba(0.0, 0.0, 0.0, 0.25)
                border.width: 1
                border.color: theme.glassHighlight
                radius: 10
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Layout.topMargin: 6

            Button {
                text: controller && controller.voiceMuted ? "UNMUTE" : "MUTE"
                Layout.fillWidth: true
                onClicked: {
                    if (!controller)
                        return
                    if (controller.voiceMuted)
                        controller.voice_unmute()
                    else
                        controller.voice_mute()
                }
            }
            Button {
                text: "STOP"
                Layout.fillWidth: true
                onClicked: if (controller) controller.voice_stop_speaking()
            }
            Button {
                text: "REPLAY"
                Layout.fillWidth: true
                onClicked: if (controller) controller.voice_replay_last()
            }
        }
    }

    Connections {
        target: controller
        function onVoiceChanged() {
            root._syncCurrentDevice()
        }
    }
}
