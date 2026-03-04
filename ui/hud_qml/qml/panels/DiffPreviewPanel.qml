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

        Label {
            text: "PATCH CANDIDATE PREVIEW"
            color: theme.textPrimary
            font.family: theme.titleFont
            font.pixelSize: 11
            font.bold: true
            font.letterSpacing: 1.5
        }

        Label {
            text: controller ? controller.diffStatsText.toUpperCase() : ""
            color: theme.accent
            font.family: theme.titleFont
            font.pixelSize: 9
            font.bold: true
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 12

            // File List
            Rectangle {
                Layout.preferredWidth: 240
                Layout.fillHeight: true
                color: Qt.rgba(1.0, 1.0, 1.0, 0.03)
                border.width: 1
                border.color: Qt.rgba(1.0, 1.0, 1.0, 0.08)
                radius: 10
                clip: true

                ListView {
                    anchors.fill: parent
                    anchors.margins: 10
                    model: controller ? controller.diffFilesModel : null
                    spacing: 6
                    clip: true
                    cacheBuffer: 360
                    reuseItems: true
                    delegate: Item {
                        required property string path
                        required property int added
                        required property int removed
                        width: ListView.view.width
                        height: 32

                        ColumnLayout {
                            anchors.fill: parent
                            spacing: 2
                            Label {
                                text: path.toUpperCase()
                                color: theme.textPrimary
                                font.family: theme.titleFont
                                font.pixelSize: 10
                                font.bold: true
                                elide: Label.ElideMiddle
                                Layout.fillWidth: true
                            }
                            RowLayout {
                                Label { text: "+" + added; color: theme.positive; font.pixelSize: 9; font.bold: true }
                                Label { text: "-" + removed; color: theme.danger; font.pixelSize: 9; font.bold: true }
                            }
                        }
                    }
                }
            }

            // Unified Diff Text
            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true

                TextArea {
                    text: controller ? controller.diffUnifiedText : ""
                    readOnly: true
                    wrapMode: TextEdit.NoWrap
                    color: theme.textPrimary
                    font.family: "Consolas"
                    font.pixelSize: 11
                    background: Rectangle {
                        color: Qt.rgba(0, 0, 0, 0.25)
                        border.width: 1
                        border.color: Qt.rgba(1.0, 1.0, 1.0, 0.08)
                        radius: 10
                    }
                }
            }
        }
    }
}
