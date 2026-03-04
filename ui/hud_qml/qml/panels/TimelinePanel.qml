import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    property var theme
    property var controller

    color: theme.glassBg
    border.color: theme.glassBorder
    border.width: 1
    radius: 12
    clip: true

    // Inner highlight for depth
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
            text: "PROJECT TIMELINE"
            color: theme.textPrimary
            font.family: theme.titleFont
            font.pixelSize: 11
            font.bold: true
            font.letterSpacing: 1.5
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Qt.rgba(1.0, 1.0, 1.0, 0.03)
            border.width: 1
            border.color: Qt.rgba(1.0, 1.0, 1.0, 0.08)
            radius: 10
            clip: true

            ListView {
                id: timelineView
                anchors.fill: parent
                anchors.margins: 12
                model: controller ? controller.timelineModel : null
                spacing: 12
                clip: true
                cacheBuffer: 500
                reuseItems: true

                delegate: Item {
                    required property string event_type
                    required property string recorded_at
                    required property string detail
                    width: timelineView.width
                    height: 52

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 2
                        RowLayout {
                            Label {
                                text: event_type.toUpperCase()
                                color: theme.accent
                                font.family: theme.titleFont
                                font.pixelSize: 10
                                font.bold: true
                            }
                            Item { Layout.fillWidth: true }
                            Label {
                                text: recorded_at
                                color: theme.textDim
                                font.pixelSize: 9
                            }
                        }
                        Label {
                            text: detail
                            color: theme.textPrimary
                            font.pixelSize: 11
                            elide: Label.ElideRight
                            Layout.fillWidth: true
                        }
                        Rectangle {
                            Layout.fillWidth: true
                            height: 1
                            color: theme.glassHighlight
                            opacity: 0.5
                        }
                    }
                }
            }
        }
    }
}
