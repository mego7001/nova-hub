import QtQuick
import QtQuick.Controls

Item {
    id: root

    property var theme
    property string status: "idle"

    implicitHeight: 26
    implicitWidth: pillLabel.implicitWidth + 20

    function _normalizedStatus() {
        var value = String(root.status || "idle").toLowerCase()
        if (value === "thinking" || value === "running" || value === "done" || value === "error")
            return value
        return "idle"
    }

    function _statusLabel() {
        var value = _normalizedStatus()
        if (value === "thinking")
            return "Thinking"
        if (value === "running")
            return "Running"
        if (value === "done")
            return "Done"
        if (value === "error")
            return "Error"
        return "Idle"
    }

    function _borderColor() {
        var value = _normalizedStatus()
        if (value === "error")
            return root.theme.dangerMuted
        if (value === "done")
            return root.theme.successMuted
        return root.theme.borderHard
    }

    function _fillColor() {
        var value = _normalizedStatus()
        if (value === "error")
            return root.theme.bgSolid
        if (value === "done")
            return root.theme.bgGlass
        return root.theme.bgGlass
    }

    function _textColor() {
        var value = _normalizedStatus()
        if (value === "error")
            return root.theme.textSecondary
        return root.theme.textSecondary
    }

    readonly property bool _glowActive: _normalizedStatus() === "thinking" || _normalizedStatus() === "running"

    Rectangle {
        anchors.fill: parent
        radius: root.theme.radiusLg
        color: root.theme.glowSoft
        visible: root._glowActive
        opacity: root._glowActive ? 1 : 0

        Behavior on opacity {
            NumberAnimation {
                duration: root.theme.animFastMs
            }
        }
    }

    Rectangle {
        id: pill
        anchors.fill: parent
        radius: root.theme.radiusLg
        color: root._fillColor()
        border.width: 1
        border.color: root._borderColor()

        Label {
            id: pillLabel
            anchors.centerIn: parent
            text: root._statusLabel()
            color: root._textColor()
            font.pixelSize: 11
            font.bold: true
        }
    }
}