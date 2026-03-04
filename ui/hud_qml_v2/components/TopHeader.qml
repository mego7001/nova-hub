import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root

    property var theme
    property string objectPrefix: "hudV2"
    property bool compactMode: false
    property string titleText: "Nova Jarvis V3"
    property string statusText: "initializing"
    property string voiceStatusText: "Voice: unavailable"
    property string modeText: "Mode: general"
    property string pendingText: "Pending: no"
    property string capabilitiesText: "Capabilities: Chat | Tools | Attach | Health | History | Voice | Security | Timeline"
    property bool showCapabilities: true

    signal minimizeRequested()
    signal exitRequested()
    signal closeRequested()

    function _chipColor(value) {
        var txt = String(value || "").toLowerCase()
        if (txt.indexOf("error") >= 0 || txt.indexOf("fail") >= 0)
            return root.theme ? root.theme.dangerMuted : "#b65f7b"
        if (txt.indexOf("thinking") >= 0 || txt.indexOf("pending") >= 0 || txt.indexOf("running") >= 0)
            return root.theme ? root.theme.accentSecondary : "#5ca7c8"
        return root.theme ? root.theme.successMuted : "#58cfae"
    }

    radius: root.theme ? root.theme.radiusMd : 12
    color: root.theme ? root.theme.bgGlass : "#0a1222"
    border.width: 1
    border.color: root.theme ? root.theme.borderHard : "#2da7d6"

    Loader {
        anchors.fill: parent
        sourceComponent: root.compactMode ? compactHeader : fullHeader
    }

    Component {
        id: compactHeader

        RowLayout {
            anchors.fill: parent
            anchors.margins: 10
            spacing: 8

            Label {
                Layout.fillWidth: true
                text: root.titleText
                color: root.theme ? root.theme.textPrimary : "#eaf6ff"
                elide: Label.ElideRight
                font.bold: true
                font.pixelSize: 14
            }

            Rectangle {
                radius: 8
                color: root._chipColor(root.statusText)
                opacity: 0.25
                border.width: 1
                border.color: root.theme ? root.theme.borderSoft : "#2d5a7a"
                implicitHeight: 24
                implicitWidth: statusCompact.implicitWidth + 12
                Label {
                    id: statusCompact
                    anchors.centerIn: parent
                    text: "Status: " + root.statusText
                    color: root.theme ? root.theme.textPrimary : "#eaf6ff"
                    font.pixelSize: 11
                    font.bold: true
                }
            }

            Button {
                objectName: root.objectPrefix + "TopMinimizeButton"
                text: "Minimize"
                onClicked: root.minimizeRequested()
            }

            Button {
                objectName: root.objectPrefix + "TopExitButton"
                text: "⏻ Exit"
                onClicked: root.exitRequested()
            }

            Button {
                objectName: root.objectPrefix + "TopCloseButton"
                text: "Close Nova"
                onClicked: root.closeRequested()
            }
        }
    }

    Component {
        id: fullHeader

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 10
            spacing: 6

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Label {
                    Layout.fillWidth: true
                    text: root.titleText
                    color: root.theme ? root.theme.textPrimary : "#eaf6ff"
                    elide: Label.ElideRight
                    font.bold: true
                    font.pixelSize: 16
                }

                Rectangle {
                    radius: 8
                    color: root._chipColor(root.statusText)
                    opacity: 0.25
                    border.width: 1
                    border.color: root.theme ? root.theme.borderSoft : "#2d5a7a"
                    implicitHeight: 24
                    implicitWidth: statusChip.implicitWidth + 12
                    Label {
                        id: statusChip
                        anchors.centerIn: parent
                        text: "Status: " + root.statusText
                        color: root.theme ? root.theme.textPrimary : "#eaf6ff"
                        font.pixelSize: 11
                        font.bold: true
                    }
                }

                Button {
                    objectName: root.objectPrefix + "TopMinimizeButton"
                    text: "Minimize"
                    onClicked: root.minimizeRequested()
                }

                Button {
                    objectName: root.objectPrefix + "TopExitButton"
                    text: "⏻ Exit"
                    onClicked: root.exitRequested()
                }

                Button {
                    objectName: root.objectPrefix + "TopCloseButton"
                    text: "Close Nova"
                    onClicked: root.closeRequested()
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Rectangle {
                    radius: 8
                    color: root.theme ? root.theme.bgSolid : "#060b14"
                    border.width: 1
                    border.color: root.theme ? root.theme.borderSoft : "#2d5a7a"
                    implicitHeight: 24
                    implicitWidth: voiceChip.implicitWidth + 12
                    Label {
                        id: voiceChip
                        anchors.centerIn: parent
                        text: root.voiceStatusText
                        color: root.theme ? root.theme.textMuted : "#7fb5d9"
                        font.pixelSize: 11
                    }
                }

                Rectangle {
                    radius: 8
                    color: root.theme ? root.theme.bgSolid : "#060b14"
                    border.width: 1
                    border.color: root.theme ? root.theme.borderSoft : "#2d5a7a"
                    implicitHeight: 24
                    implicitWidth: modeChip.implicitWidth + 12
                    Label {
                        id: modeChip
                        anchors.centerIn: parent
                        text: root.modeText
                        color: root.theme ? root.theme.textMuted : "#7fb5d9"
                        font.pixelSize: 11
                    }
                }

                Rectangle {
                    radius: 8
                    color: root.theme ? root.theme.bgSolid : "#060b14"
                    border.width: 1
                    border.color: root.theme ? root.theme.borderSoft : "#2d5a7a"
                    implicitHeight: 24
                    implicitWidth: pendingChip.implicitWidth + 12
                    Label {
                        id: pendingChip
                        anchors.centerIn: parent
                        text: root.pendingText
                        color: root.theme ? root.theme.textMuted : "#7fb5d9"
                        font.pixelSize: 11
                    }
                }

                Item { Layout.fillWidth: true }
            }

            Label {
                Layout.fillWidth: true
                text: root.capabilitiesText
                color: root.theme ? root.theme.textMuted : "#7fb5d9"
                font.pixelSize: 11
                elide: Label.ElideRight
                visible: root.showCapabilities
            }
        }
    }
}
