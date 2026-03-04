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

        Label {
            text: "ACTIVE MISSION QUEUE"
            color: theme.textPrimary
            font.family: theme.titleFont
            font.pixelSize: 11
            font.bold: true
            font.letterSpacing: 1.5
        }

        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: root.model
            spacing: 8
            clip: true
            cacheBuffer: 700
            reuseItems: true

            delegate: Rectangle {
                required property string title
                required property string status
                required property string steps
                required property string waiting_reason
                required property string current_step_label

                width: ListView.view.width
                height: 80
                radius: 10
                color: Qt.rgba(1.0, 1.0, 1.0, 0.03)
                border.width: 1
                border.color: waiting_reason === "confirm_apply" ? theme.warning : Qt.rgba(1.0, 1.0, 1.0, 0.08)

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 4
                    RowLayout {
                        Layout.fillWidth: true
                        Label {
                            text: title.toUpperCase()
                            color: waiting_reason === "confirm_apply" ? theme.warning : theme.textPrimary
                            font.family: theme.titleFont
                            font.bold: true
                            font.pixelSize: 11
                            font.letterSpacing: 1.1
                            Layout.fillWidth: true
                        }
                        Label {
                            text: status.toUpperCase()
                            color: status.toLowerCase() === "running" ? theme.positive : theme.textDim
                            font.family: theme.titleFont
                            font.pixelSize: 9
                            font.bold: true
                        }
                    }
                    Label {
                        text: "STEPS: " + steps
                        color: theme.accent
                        font.family: theme.titleFont
                        font.pixelSize: 9
                        font.bold: true
                        font.letterSpacing: 1.0
                    }
                    Label {
                        text: current_step_label.toUpperCase()
                        color: theme.textDim
                        font.family: theme.bodyFont
                        font.pixelSize: 10
                        elide: Label.ElideRight
                        Layout.fillWidth: true
                    }
                }

                // Alert glow if waiting (Alert: moved out of ColumnLayout to avoid warnings)
                Rectangle {
                    anchors.fill: parent
                    radius: parent.radius
                    color: "transparent"
                    border.width: 2
                    border.color: theme.warning
                    visible: waiting_reason === "confirm_apply"
                    opacity: 0.3
                }
            }
        }
    }
}
