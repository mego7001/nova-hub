import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    property var theme
    property var model

    color: theme.glassBg
    border.color: theme.glassBorder
    border.width: 1
    radius: 12
    clip: true

    ListView {
        id: list
        anchors.fill: parent
        anchors.margins: 14
        model: root.model
        spacing: 12
        clip: true
        cacheBuffer: 1000
        reuseItems: true

        onCountChanged: positionViewAtEnd()

        delegate: Item {
            id: delegateRoot
            required property string role
            required property string text
            required property string timestamp
            width: ListView.view.width
            height: bubble.implicitHeight + 6

            Rectangle {
                id: bubble
                anchors.right: role === "user" ? parent.right : undefined
                anchors.left: role === "user" ? undefined : parent.left
                width: Math.min(parent.width * 0.88, body.implicitWidth + 24)
                radius: 12
                color: role === "user" ? Qt.rgba(0.0, 0.9, 1.0, 0.1) : Qt.rgba(1.0, 1.0, 1.0, 0.04)
                border.width: 1
                border.color: role === "user" ? theme.accent : theme.glassBorder
                implicitHeight: body.implicitHeight + 20
                opacity: 0.0
                y: 10

                Behavior on opacity { NumberAnimation { duration: 250 } }
                Behavior on y { NumberAnimation { duration: 300; easing.type: Easing.OutQuart } }

                Component.onCompleted: {
                    opacity = 1.0
                    y = 0
                }

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
                    id: body
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 4

                    RowLayout {
                        spacing: 6
                        Label {
                            text: (role === "user" ? "Protocol: Operator" : "Protocol: Nova").toUpperCase()
                            color: role === "user" ? theme.accent : theme.positive
                            font.family: theme.titleFont
                            font.bold: true
                            font.pixelSize: 10
                            font.letterSpacing: 1.1
                        }
                    }

                    Text {
                        width: parent.width
                        text: delegateRoot.text
                        color: theme.textPrimary
                        wrapMode: Text.Wrap
                        font.family: theme.bodyFont
                        font.pixelSize: 14
                        lineHeight: 1.2
                        elide: Text.ElideNone
                    }

                    Label {
                        text: timestamp
                        color: theme.textDim
                        font.pixelSize: 9
                        font.family: theme.bodyFont
                        Layout.alignment: Qt.AlignRight
                    }
                }
            }
        }
    }

    Column {
        anchors.centerIn: parent
        spacing: 8
        visible: list.count === 0

        Label {
            text: "SYSTEM READY | CONVERSATION FEED EMPTY"
            color: theme.textDim
            font.family: theme.titleFont
            font.bold: true
            font.pixelSize: 11
            font.letterSpacing: 1.5
            anchors.horizontalCenter: parent.horizontalCenter
        }
        Label {
            text: "Awaiting operator command sequence..."
            color: theme.textDim
            font.family: theme.bodyFont
            font.pixelSize: 10
            font.italic: true
            opacity: 0.6
            anchors.horizontalCenter: parent.horizontalCenter
        }
    }
}
