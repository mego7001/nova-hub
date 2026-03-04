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
            Layout.fillWidth: true
            text: "CURATED ADVANCED TOOLS"
            color: theme.textPrimary
            font.family: theme.titleFont
            font.pixelSize: 11
            font.bold: true
            font.letterSpacing: 1.5
        }

        Label {
            Layout.fillWidth: true
            text: "SYSTEM REGISTRY BACKED | APPROVAL REQUIRED FOR HIGH-RISK OPERATIONS"
            color: theme.positive
            font.family: theme.titleFont
            font.pixelSize: 9
            font.bold: true
            font.letterSpacing: 1.1
            opacity: 0.8
            wrapMode: Label.Wrap
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
            model: controller ? controller.toolsCatalogModel : null
            clip: true
            spacing: 6

            delegate: Rectangle {
                width: ListView.view.width
                radius: 8
                color: Qt.rgba(1.0, 1.0, 1.0, 0.03)
                border.width: 1
                border.color: Qt.rgba(1.0, 1.0, 1.0, 0.08)
                implicitHeight: itemCol.implicitHeight + 12

                ColumnLayout {
                    id: itemCol
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 4

                    RowLayout {
                        Layout.fillWidth: true
                        Label {
                            text: (section ? section.toUpperCase() + " | " : "") + id.toUpperCase()
                            color: theme.accent
                            font.family: theme.titleFont
                            font.pixelSize: 11
                            font.bold: true
                            Layout.fillWidth: true
                        }
                        Rectangle {
                            radius: 4
                            color: badge === "available" ? Qt.rgba(0.0, 0.9, 1.0, 0.1) : Qt.rgba(1.0, 0.6, 0.2, 0.1)
                            border.width: 1
                            border.color: badge === "available" ? theme.positive : theme.warning
                            Layout.preferredHeight: 18
                            Layout.preferredWidth: 60
                            Label {
                                anchors.centerIn: parent
                                text: badge.toUpperCase()
                                color: badge === "available" ? theme.positive : theme.warning
                                font.family: theme.titleFont
                                font.pixelSize: 8
                                font.bold: true
                            }
                        }
                    }

                    Label {
                        Layout.fillWidth: true
                        text: "GROUP ID: " + group.toUpperCase()
                        color: theme.textDim
                        font.family: theme.titleFont
                        font.pixelSize: 9
                        font.bold: true
                    }

                    Label {
                        Layout.fillWidth: true
                        text: description
                        color: theme.textMuted
                        wrapMode: Label.Wrap
                        font.family: theme.bodyFont
                        font.pixelSize: 11
                        lineHeight: 1.2
                    }
                }
            }
        }
    }
}
