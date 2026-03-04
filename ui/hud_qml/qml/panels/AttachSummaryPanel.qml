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

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            Label {
                text: "ATTACHMENT INTELLIGENCE"
                color: theme.textPrimary
                font.family: theme.titleFont
                font.pixelSize: 11
                font.bold: true
                font.letterSpacing: 1.5
            }
            Label {
                text: controller ? controller.attachLastSummary.toUpperCase() : "NO ATTACHMENTS DETECTED"
                color: theme.textMuted
                font.pixelSize: 9
                font.bold: true
                wrapMode: Label.Wrap
                Layout.fillWidth: true
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 140
            color: Qt.rgba(1.0, 1.0, 1.0, 0.03)
            border.width: 1
            border.color: Qt.rgba(1.0, 1.0, 1.0, 0.08)
            radius: 10
            clip: true

            ListView {
                id: attachView
                anchors.fill: parent
                anchors.margins: 12
                model: controller ? controller.attachSummaryModel : null
                spacing: 8
                clip: true
                cacheBuffer: 500
                reuseItems: true

                delegate: Item {
                    required property string path
                    required property string status
                    required property string reason
                    required property string type
                    required property string size
                    width: attachView.width
                    height: 48

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 2
                        RowLayout {
                            Label {
                                text: status.toUpperCase() + " • " + path.toUpperCase()
                                color: status.toLowerCase() === "ok" ? theme.positive : theme.danger
                                font.family: theme.titleFont
                                font.pixelSize: 10
                                font.bold: true
                                elide: Label.ElideMiddle
                                Layout.fillWidth: true
                            }
                        }
                        Label {
                            text: reason ? reason : (type ? ("TYPE: " + type + " • SIZE: " + size) : "PROCESSING...")
                            color: theme.textDim
                            font.pixelSize: 9
                            font.bold: true
                            elide: Label.ElideRight
                            Layout.fillWidth: true
                        }
                        Rectangle {
                            Layout.fillWidth: true
                            height: 1
                            color: theme.glassHighlight
                            opacity: 0.3
                        }
                    }
                }
            }
        }

        // Conversion Action
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 80
            color: Qt.rgba(0, 0, 0, 0.2)
            radius: 10
            border.width: 1
            border.color: theme.glassHighlight

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 8
                
                TextField {
                    id: projectNameField
                    Layout.fillWidth: true
                    placeholderText: "CONVERT GENERAL CHAT TO PROJECT..."
                    color: theme.textPrimary
                    font.pixelSize: 11
                    background: Rectangle {
                        color: Qt.rgba(1.0, 1.0, 1.0, 0.04)
                        radius: 6
                    }
                    onAccepted: {
                        if (controller && text.length > 0) 
                            controller.migrateGeneralToProject(text)
                    }
                }

                Button {
                    Layout.fillWidth: true
                    text: "EXECUTE CONVERSION"
                    onClicked: {
                        if (controller && projectNameField.text.length > 0)
                            controller.migrateGeneralToProject(projectNameField.text)
                    }
                }
            }
        }
    }
}
