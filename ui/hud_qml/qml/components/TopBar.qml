import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    property var theme
    property var rootWindow
    property string title: "Nova HUD"
    property string statusText: ""
    property string wiringStatus: "placeholder"
    property bool jarvisMode: true

    signal toggleModeRequested()
    signal refreshRequested()
    signal exitRequested()
    signal closeRequested()
    signal minimizeRequested()

    color: theme.glassBg
    border.color: theme.glassBorder
    border.width: 1
    radius: 12
    implicitHeight: 68

    component HudButton: Button {
        id: control
        property color fillColor: Qt.rgba(1.0, 1.0, 1.0, 0.05)
        property color borderColor: Qt.rgba(1.0, 1.0, 1.0, 0.15)
        property color hoverBorderColor: theme.accent
        
        contentItem: Text {
            text: control.text
            color: control.hovered ? theme.accent : theme.textPrimary
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            font.bold: true
            font.pixelSize: 11
            font.family: theme.titleFont
            font.letterSpacing: 1.1
            Behavior on color { ColorAnimation { duration: 150 } }
        }
        background: Rectangle {
            radius: 8
            color: control.down ? Qt.rgba(1.0, 1.0, 1.0, 0.12) : 
                   (control.hovered ? Qt.rgba(1.0, 1.0, 1.0, 0.08) : control.fillColor)
            border.width: 1
            border.color: control.hovered ? control.hoverBorderColor : control.borderColor
            Behavior on color { ColorAnimation { duration: 150 } }
            Behavior on border.color { ColorAnimation { duration: 150 } }
        }
    }

    // Subtle inner glow and glass reflection
    Rectangle {
        anchors.fill: parent
        anchors.margins: 1
        radius: 11
        color: "transparent"
        border.width: 1
        border.color: theme.glassHighlight
        opacity: 0.6
    }

    RowLayout {
        id: barRow
        anchors.fill: parent
        anchors.leftMargin: 20
        anchors.rightMargin: 12
        spacing: 12

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            Label {
                text: title
                color: theme.textPrimary
                font.family: theme.titleFont
                font.pixelSize: 18
                font.bold: true
                font.letterSpacing: 1.5
            }
            Label {
                text: (statusText + " | " + wiringStatus).toUpperCase()
                color: theme.accent
                font.family: theme.bodyFont
                font.pixelSize: 10
                font.bold: true
                font.letterSpacing: 1.2
                opacity: 0.8
                elide: Label.ElideRight
                Layout.fillWidth: true
            }
        }

        HudButton {
            text: jarvisMode ? "PROTOCOL: JARVIS" : "PROTOCOL: CALM"
            borderColor: jarvisMode ? theme.accent : theme.textMuted
            onClicked: root.toggleModeRequested()
        }
        HudButton {
            text: "SYNC"
            onClicked: root.refreshRequested()
        }
        HudButton {
            text: "EXIT"
            implicitWidth: 52
            onClicked: root.exitRequested()
        }
        HudButton {
            text: "−"
            implicitWidth: 32
            onClicked: root.minimizeRequested()
        }
        HudButton {
            text: "✕"
            implicitWidth: 32
            fillColor: Qt.rgba(1.0, 0.2, 0.3, 0.1)
            borderColor: Qt.rgba(1.0, 0.2, 0.3, 0.3)
            hoverBorderColor: theme.danger
            onClicked: root.closeRequested()
        }
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton
        cursorShape: Qt.SizeAllCursor
        propagateComposedEvents: true
        onPressed: function(mouse) {
            if (mouse.x < barRow.width - 280 && rootWindow && rootWindow.startSystemMove) {
                rootWindow.startSystemMove()
            } else {
                mouse.accepted = false
            }
        }
    }
}
