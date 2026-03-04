import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property var theme
    property var model
    property bool busy: false
    property string currentTaskMode: "general"
    property var taskModesModel: []
    property string statusState: "idle"
    property bool voiceEnabled: false
    property bool voiceMuted: false
    property string voiceState: "disabled"
    property string voiceStatusLine: "Voice: disabled"
    property bool voiceReplayAvailable: false
    property bool voicePushToTalk: true
    property bool voicePushActive: false

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
    signal messageObserved(var message)

    property int _lastCount: 0

    radius: root.theme.radiusLg
    color: root.theme.bgGlass
    border.width: 1
    border.color: root.theme.borderSoft

    function _emitNewMessages() {
        if (!root.model)
            return
        var count = Number(listView.count || 0)
        if (count < root._lastCount)
            root._lastCount = 0
        for (var i = root._lastCount; i < count; i++) {
            if (root.model.get) {
                var row = root.model.get(i)
                root.messageObserved(row)
            }
        }
        root._lastCount = count
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 34
            radius: root.theme.radiusMd
            color: root.theme.bgSolid
            border.width: 1
            border.color: root.theme.borderSoft

            Label {
                anchors.fill: parent
                anchors.margins: 8
                text: "Iron-Assistant Chat"
                color: root.theme.textPrimary
                font.bold: true
                elide: Label.ElideRight
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
                id: listView
                anchors.fill: parent
                anchors.margins: 8
                model: root.model
                spacing: 8
                clip: true
                cacheBuffer: 900
                reuseItems: true

                onCountChanged: {
                    positionViewAtEnd()
                    root._emitNewMessages()
                }

                delegate: MessageBubble {
                    required property string role
                    required property string text
                    required property string timestamp
                    property string msgRole: role
                    property string msgText: text
                    property string msgTimestamp: timestamp

                    width: ListView.view.width
                    theme: root.theme
                    role: msgRole
                    text: msgText
                    timestamp: msgTimestamp
                    currentMode: root.currentTaskMode
                    meta: model && model.meta !== undefined ? model.meta : ({})
                }
            }

            Column {
                anchors.centerIn: parent
                spacing: 5
                visible: listView.count === 0

                Label {
                    text: "No conversation yet"
                    color: root.theme.textPrimary
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                }
                Label {
                    text: "Send a prompt to start"
                    color: root.theme.textMuted
                    horizontalAlignment: Text.AlignHCenter
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            StatusPill {
                id: statusPill
                theme: root.theme
                status: root.statusState
            }

            Item {
                Layout.fillWidth: true
            }

            Label {
                text: root.voiceStatusLine
                color: root.theme.textMuted
                font.pixelSize: 11
                elide: Label.ElideRight
            }
        }

        Composer {
            Layout.fillWidth: true
            Layout.preferredHeight: 58
            theme: root.theme
            busy: root.busy
            currentTaskMode: root.currentTaskMode
            taskModesModel: root.taskModesModel
            voiceEnabled: root.voiceEnabled
            voiceMuted: root.voiceMuted
            voiceState: root.voiceState
            voiceStatusLine: root.voiceStatusLine
            voiceReplayAvailable: root.voiceReplayAvailable
            pushToTalkEnabled: root.voicePushToTalk
            pushToTalkActive: root.voicePushActive
            onSendRequested: function(message) {
                root.sendRequested(message)
            }
            onAttachRequested: root.attachRequested()
            onToolsRequested: root.toolsRequested()
            onTaskModeChangedRequested: function(modeId) {
                root.taskModeChangedRequested(modeId)
            }
            onVoiceToggleRequested: root.voiceToggleRequested()
            onVoicePushStartRequested: root.voicePushStartRequested()
            onVoicePushStopRequested: root.voicePushStopRequested()
            onVoiceMuteToggleRequested: root.voiceMuteToggleRequested()
            onVoiceStopRequested: root.voiceStopRequested()
            onVoiceReplayRequested: root.voiceReplayRequested()
            onVoicePanelRequested: root.voicePanelRequested()
        }
    }
}
