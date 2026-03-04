import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    property var theme
    property string summary: ""
    property bool active: false
    property bool readOnly: false
    property bool locked: false
    signal confirmRequested()
    signal rejectRequested()

    color: Qt.rgba(0.0, 0.4, 0.5, 0.85) // Specialized alert glass
    border.color: theme.accent
    border.width: 1
    radius: 12
    clip: true
    visible: active
    opacity: active ? 1.0 : 0.0
    implicitHeight: active ? row.implicitHeight + 20 : 0
    height: implicitHeight

    // Inner highlight for alert intensity
    Rectangle {
        anchors.fill: parent
        anchors.margins: 1
        color: "transparent"
        border.color: theme.glassHighlight
        border.width: 1
        radius: parent.radius - 1
    }

    Behavior on opacity { NumberAnimation { duration: 150 } }
    Behavior on height { NumberAnimation { duration: 250; easing.type: Easing.OutBack } }

    RowLayout {
        id: row
        anchors.fill: parent
        anchors.margins: 12
        spacing: 16

        Label {
            text: summary.toUpperCase()
            color: theme.textPrimary
            font.family: theme.titleFont
            font.pixelSize: 10
            font.bold: true
            font.letterSpacing: 1.1
            wrapMode: Label.Wrap
            Layout.fillWidth: true
        }
        
        RowLayout {
            spacing: 8
            visible: !root.readOnly
            
            Button {
                text: "EXECUTE"
                enabled: !root.locked
                onClicked: root.confirmRequested()
            }
            Button {
                text: "ABORT"
                enabled: !root.locked
                flat: true
                onClicked: root.rejectRequested()
            }
        }
        
        Button {
            text: "DISMISS"
            visible: root.readOnly
            onClicked: root.rejectRequested()
        }
    }
}
