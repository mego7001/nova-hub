import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property var theme
    property bool busy: false
    property var taskModesModel: []
    property string currentTaskMode: "general"
    property bool voiceEnabled: false
    property bool voiceMuted: false
    property string voiceState: "disabled"
    property string voiceStatusLine: "Voice: disabled"
    property bool voiceReplayAvailable: false
    property bool pushToTalkEnabled: true
    property bool pushToTalkActive: false

    signal sendRequested(string message)
    signal attachRequested()
    signal toolsRequested()
    signal taskModeChangedRequested(string modeId)
    signal voiceToggleRequested()
    signal voicePushStartRequested()
    signal voicePushStopRequested()
    signal voiceMuteToggleRequested()
    signal voiceStopRequested()
    signal voiceReplayRequested()
    signal voicePanelRequested()

    function _syncTaskMode() {
        var wanted = String(root.currentTaskMode || "general")
        if (!modeCombo.model || modeCombo.model.length <= 0)
            return
        for (var i = 0; i < modeCombo.model.length; i++) {
            var row = modeCombo.model[i]
            var idValue = row && row.id ? String(row.id) : "general"
            if (idValue === wanted) {
                modeCombo.currentIndex = i
                return
            }
        }
        modeCombo.currentIndex = 0
    }

    function sendNow() {
        var message = String(input.text || "").trim()
        if (!message.length)
            return
        root.sendRequested(message)
        input.clear()
    }

    onTaskModesModelChanged: _syncTaskMode()
    onCurrentTaskModeChanged: _syncTaskMode()
    Component.onCompleted: _syncTaskMode()

    radius: root.theme.radiusMd
    color: root.theme.bgGlass
    border.width: 1
    border.color: root.theme.borderSoft

    RowLayout {
        anchors.fill: parent
        anchors.margins: 9
        spacing: 7

        Button {
            objectName: "hudV2ComposerAttachButton"
            text: "Attach"
            onClicked: root.attachRequested()
            background: Rectangle {
                radius: root.theme.radiusSm
                color: root.theme.bgSolid
                border.width: 1
                border.color: root.theme.borderSoft
            }
            contentItem: Text {
                text: parent.text
                color: root.theme.textSecondary
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.pixelSize: 12
                font.bold: true
            }
        }

        ComboBox {
            id: modeCombo
            objectName: "hudV2ComposerTaskModeCombo"
            Layout.preferredWidth: 156
            model: root.taskModesModel
            textRole: "title"
            onActivated: {
                if (!model || currentIndex < 0 || currentIndex >= model.length)
                    return
                var row = model[currentIndex]
                var modeId = row && row.id ? String(row.id) : "general"
                root.taskModeChangedRequested(modeId)
            }
            background: Rectangle {
                radius: root.theme.radiusSm
                color: root.theme.bgSolid
                border.width: 1
                border.color: root.theme.borderSoft
            }
            contentItem: Text {
                text: modeCombo.displayText
                color: root.theme.textSecondary
                leftPadding: 8
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
                font.pixelSize: 12
            }
        }

        Button {
            objectName: "hudV2ComposerToolsButton"
            text: "Tools"
            onClicked: root.toolsRequested()
            background: Rectangle {
                radius: root.theme.radiusSm
                color: root.theme.bgSolid
                border.width: 1
                border.color: root.theme.borderSoft
            }
            contentItem: Text {
                text: parent.text
                color: root.theme.textSecondary
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.pixelSize: 12
                font.bold: true
            }
        }

        Button {
            objectName: "hudV2ComposerMicButton"
            text: root.pushToTalkEnabled ? (root.pushToTalkActive ? "Mic On" : "Mic Off") : (root.voiceEnabled ? "Mic On" : "Mic Off")
            onPressed: {
                if (root.pushToTalkEnabled)
                    root.voicePushStartRequested()
            }
            onReleased: {
                if (root.pushToTalkEnabled)
                    root.voicePushStopRequested()
            }
            onCanceled: {
                if (root.pushToTalkEnabled)
                    root.voicePushStopRequested()
            }
            onClicked: {
                if (!root.pushToTalkEnabled)
                    root.voiceToggleRequested()
            }
            background: Rectangle {
                radius: root.theme.radiusSm
                color: (root.pushToTalkEnabled ? root.pushToTalkActive : root.voiceEnabled) ? root.theme.glowSoft : root.theme.bgSolid
                border.width: 1
                border.color: (root.pushToTalkEnabled ? root.pushToTalkActive : root.voiceEnabled) ? root.theme.borderHard : root.theme.borderSoft
            }
            contentItem: Text {
                text: parent.text
                color: root.theme.textSecondary
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.pixelSize: 12
                font.bold: true
            }
        }

        Button {
            objectName: "hudV2ComposerMuteButton"
            text: root.voiceMuted ? "Unmute" : "Mute"
            enabled: root.voiceEnabled
            onClicked: root.voiceMuteToggleRequested()
            background: Rectangle {
                radius: root.theme.radiusSm
                color: root.theme.bgSolid
                border.width: 1
                border.color: root.theme.borderSoft
            }
            contentItem: Text {
                text: parent.text
                color: root.theme.textSecondary
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.pixelSize: 12
                font.bold: true
            }
        }

        Button {
            objectName: "hudV2ComposerStopVoiceButton"
            text: "Stop Voice"
            enabled: root.voiceEnabled
            onClicked: root.voiceStopRequested()
            background: Rectangle {
                radius: root.theme.radiusSm
                color: root.theme.bgSolid
                border.width: 1
                border.color: root.theme.borderSoft
            }
            contentItem: Text {
                text: parent.text
                color: root.theme.textSecondary
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.pixelSize: 12
            }
        }

        Button {
            objectName: "hudV2ComposerReplayButton"
            text: "Replay"
            enabled: root.voiceEnabled && root.voiceReplayAvailable
            onClicked: root.voiceReplayRequested()
            background: Rectangle {
                radius: root.theme.radiusSm
                color: root.theme.bgSolid
                border.width: 1
                border.color: root.theme.borderSoft
            }
            contentItem: Text {
                text: parent.text
                color: root.theme.textSecondary
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.pixelSize: 12
            }
        }

        Button {
            objectName: "hudV2ComposerVoicePanelButton"
            text: "Voice"
            onClicked: root.voicePanelRequested()
            background: Rectangle {
                radius: root.theme.radiusSm
                color: root.theme.bgSolid
                border.width: 1
                border.color: root.theme.borderSoft
            }
            contentItem: Text {
                text: parent.text
                color: root.theme.textSecondary
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.pixelSize: 12
                font.bold: true
            }
        }

        TextField {
            id: input
            objectName: "hudV2ComposerInputField"
            Layout.fillWidth: true
            placeholderText: "Type a message"
            color: root.theme.textPrimary
            placeholderTextColor: root.theme.textMuted
            selectionColor: root.theme.accentSoft
            selectedTextColor: root.theme.bgSolid
            selectByMouse: true
            background: Rectangle {
                radius: root.theme.radiusSm
                color: root.theme.bgSolid
                border.width: 1
                border.color: root.theme.borderSoft
            }
            onAccepted: root.sendNow()
        }

        Button {
            objectName: "hudV2ComposerSendButton"
            text: root.busy ? "..." : "Send"
            enabled: !root.busy
            onClicked: root.sendNow()
            background: Rectangle {
                radius: root.theme.radiusSm
                color: root.theme.bgSolid
                border.width: 1
                border.color: root.theme.borderHard
            }
            contentItem: Text {
                text: parent.text
                color: root.theme.textPrimary
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.pixelSize: 12
                font.bold: true
            }
        }
    }
}
