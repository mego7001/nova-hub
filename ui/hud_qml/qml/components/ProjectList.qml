import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    property var theme
    property var model
    property string currentProjectId: ""
    signal projectSelected(string projectId)

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

        Label {
            text: "PROJECT ARCHIVE"
            color: theme.textPrimary
            font.family: theme.titleFont
            font.pixelSize: 11
            font.bold: true
            font.letterSpacing: 1.5
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
                id: itemRect
                required property string project_id
                required property string name
                required property string status
                required property string working_path

                width: ListView.view.width
                height: 76
                radius: 10
                color: project_id === root.currentProjectId ? Qt.rgba(0.0, 0.9, 1.0, 0.12) : Qt.rgba(1.0, 1.0, 1.0, 0.03)
                border.width: 1
                border.color: project_id === root.currentProjectId ? theme.accent : Qt.rgba(1.0, 1.0, 1.0, 0.08)

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 2
                    RowLayout {
                        Layout.fillWidth: true
                        Label {
                            text: name.toUpperCase()
                            color: project_id === root.currentProjectId ? theme.accent : theme.textPrimary
                            font.family: theme.titleFont
                            font.bold: true
                            font.pixelSize: 12
                            font.letterSpacing: 1.1
                            Layout.fillWidth: true
                        }
                        Label {
                            text: status.toUpperCase()
                            color: status.toLowerCase() === "active" ? theme.positive : theme.textDim
                            font.family: theme.titleFont
                            font.pixelSize: 9
                            font.bold: true
                        }
                    }
                    Label {
                        text: working_path
                        color: theme.textDim
                        font.family: theme.bodyFont
                        font.pixelSize: 11
                        elide: Label.ElideMiddle
                        Layout.fillWidth: true
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: root.projectSelected(project_id)
                }

                Rectangle {
                    anchors.fill: parent
                    radius: parent.radius
                    color: "white"
                    opacity: itemRect.ListView.isCurrentItem || itemRect.containsMouse ? 0.03 : 0.0
                    visible: project_id !== root.currentProjectId
                }
            }
        }
    }
}
