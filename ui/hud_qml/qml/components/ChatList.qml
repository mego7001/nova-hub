import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    property var theme
    property var model
    property string currentChatId: ""
    signal chatSelected(string chatId)
    signal newChatRequested()

    function focusList() {
        list.forceActiveFocus()
    }

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

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Label {
                Layout.fillWidth: true
                text: "CONVERSATIONS"
                color: theme.textPrimary
                font.family: theme.titleFont
                font.pixelSize: 11
                font.bold: true
                font.letterSpacing: 1.5
            }
            Button {
                text: "NEW"
                flat: true
                onClicked: root.newChatRequested()
            }
        }

        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: root.model
            spacing: 8
            clip: true
            cacheBuffer: 800
            reuseItems: true

            delegate: Rectangle {
                required property string chat_id
                required property string title
                required property string status
                required property string last_opened
                required property string linked_project_id

                width: ListView.view.width
                height: 56
                radius: 8
                color: chat_id === root.currentChatId ? Qt.rgba(0.0, 0.9, 1.0, 0.12) : Qt.rgba(1.0, 1.0, 1.0, 0.04)
                border.width: 1
                border.color: chat_id === root.currentChatId ? theme.accent : Qt.rgba(1.0, 1.0, 1.0, 0.08)

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 2
                    Label {
                        text: title.toUpperCase()
                        color: chat_id === root.currentChatId ? theme.accent : theme.textPrimary
                        font.family: theme.titleFont
                        font.bold: true
                        font.pixelSize: 11
                        elide: Label.ElideRight
                        Layout.fillWidth: true
                    }
                    Label {
                        text: status === "converted" && linked_project_id.length > 0 ? ("ARCHIVED • " + linked_project_id.toUpperCase()) : "LIVE SESSION"
                        color: theme.textDim
                        font.family: theme.titleFont
                        font.pixelSize: 9
                        font.bold: true
                        elide: Label.ElideRight
                        Layout.fillWidth: true
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: root.chatSelected(chat_id)
                    onEntered: if (chat_id !== root.currentChatId) parent.color = Qt.rgba(1.0, 1.0, 1.0, 0.08)
                    onExited: if (chat_id !== root.currentChatId) parent.color = Qt.rgba(1.0, 1.0, 1.0, 0.04)
                }
            }
        }
    }
}
