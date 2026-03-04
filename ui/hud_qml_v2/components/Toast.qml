import QtQuick
import QtQuick.Controls

Item {
    id: root

    property var theme
    property string message: ""
    property bool showing: false

    anchors.horizontalCenter: parent.horizontalCenter
    y: showing ? 16 : 4
    opacity: showing ? 1 : 0
    visible: opacity > 0
    implicitWidth: toastLabel.implicitWidth + 24
    implicitHeight: 34

    function showToast(text) {
        root.message = String(text || "")
        if (!root.message.length)
            return
        root.showing = true
        hideTimer.restart()
    }

    Behavior on opacity {
        NumberAnimation {
            duration: root.theme.animFastMs
        }
    }

    Behavior on y {
        NumberAnimation {
            duration: root.theme.animMedMs
        }
    }

    Timer {
        id: hideTimer
        interval: 1800
        onTriggered: root.showing = false
    }

    Rectangle {
        anchors.fill: parent
        radius: root.theme.radiusMd
        color: root.theme.bgGlass
        border.width: 1
        border.color: root.theme.borderHard

        Label {
            id: toastLabel
            anchors.centerIn: parent
            text: root.message
            color: root.theme.textPrimary
            font.pixelSize: 12
            elide: Label.ElideRight
        }
    }
}