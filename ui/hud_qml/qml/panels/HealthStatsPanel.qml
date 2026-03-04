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
            spacing: 10

            Label {
                Layout.fillWidth: true
                text: "PROVIDER HEALTH SCOREBOARD"
                color: theme.textPrimary
                font.family: theme.titleFont
                font.pixelSize: 11
                font.bold: true
                font.letterSpacing: 1.2
            }

            Button {
                text: "REFRESH"
                contentItem: Text {
                    text: parent.text
                    color: theme.accent
                    font.family: theme.titleFont
                    font.pixelSize: 9
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                }
                background: Rectangle {
                    radius: 6
                    color: parent.hovered ? Qt.rgba(1.0, 1.0, 1.0, 0.05) : "transparent"
                    border.width: 1
                    border.color: Qt.rgba(1.0, 1.0, 1.0, 0.1)
                }
                onClicked: {
                    if (controller)
                        controller.refreshHealthStats()
                }
            }
        }

        Label {
            Layout.fillWidth: true
            text: controller ? (controller.healthStatsSummary).toUpperCase() : "NO HEALTH DATA AVAILABLE"
            color: theme.positive
            font.family: theme.titleFont
            font.pixelSize: 9
            font.bold: true
            font.letterSpacing: 1.1
            opacity: 0.8
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: theme.glassBorder
            opacity: 0.2
        }

        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: controller ? controller.healthStatsModel : null
            clip: true
            spacing: 6

            delegate: Rectangle {
                width: ListView.view.width
                radius: 8
                color: Qt.rgba(1.0, 1.0, 1.0, 0.03)
                border.width: 1
                border.color: Qt.rgba(1.0, 1.0, 1.0, 0.08)
                implicitHeight: rowCol.implicitHeight + 12

                ColumnLayout {
                    id: rowCol
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 4

                    RowLayout {
                        Layout.fillWidth: true
                        Label {
                            text: provider.toUpperCase()
                            color: theme.textPrimary
                            font.family: theme.titleFont
                            font.pixelSize: 11
                            font.bold: true
                            Layout.fillWidth: true
                        }
                        Label {
                            text: Number(success_rate * 100.0).toFixed(0) + "% SUCCESS"
                            color: success_rate > 0.9 ? theme.positive : (success_rate > 0.7 ? theme.warning : theme.danger)
                            font.family: theme.titleFont
                            font.pixelSize: 9
                            font.bold: true
                        }
                    }
                    
                    Label {
                        Layout.fillWidth: true
                        text: "LATENCY: " + avg_latency_ms + "MS | CALLS: " + calls + " | LAST: " + (last_used ? last_used : "N/A")
                        color: theme.textDim
                        font.family: theme.bodyFont
                        font.pixelSize: 10
                        elide: Label.ElideRight
                    }
                    
                    Label {
                        Layout.fillWidth: true
                        text: last_error ? ("LAST ERROR: " + last_error).toUpperCase() : "LAST ERROR: NONE"
                        color: last_error ? theme.danger : theme.textDim
                        wrapMode: Label.Wrap
                        font.family: theme.bodyFont
                        font.pixelSize: 9
                        opacity: last_error ? 1.0 : 0.6
                    }
                }
            }
        }
    }
}
