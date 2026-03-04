import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    property var theme
    property string role: "assistant"
    property string text: ""
    property string timestamp: ""
    property var meta: ({})
    property string currentMode: ""

    readonly property bool _isUser: String(role || "") === "user"

    implicitHeight: bubble.implicitHeight + 4
    implicitWidth: parent ? parent.width : bubble.implicitWidth

    Rectangle {
        id: bubble
        anchors.right: root._isUser ? parent.right : undefined
        anchors.left: root._isUser ? undefined : parent.left
        width: Math.min(root.width * 0.88, body.implicitWidth + 22)
        radius: root.theme.radiusMd
        color: root._isUser ? root.theme.bgSolid : root.theme.bgGlass
        border.width: 1
        border.color: root._isUser ? root.theme.borderHard : root.theme.borderSoft
        implicitHeight: body.implicitHeight + 18
        opacity: 0
        y: 6

        Behavior on opacity {
            NumberAnimation {
                duration: root.theme.animFastMs
            }
        }

        Behavior on y {
            NumberAnimation {
                duration: root.theme.animMedMs
                easing.type: Easing.OutCubic
            }
        }

        Component.onCompleted: {
            opacity = 1
            y = 0
        }

        ColumnLayout {
            id: body
            anchors.fill: parent
            anchors.margins: 9
            spacing: 6

            Label {
                Layout.fillWidth: true
                text: root._isUser ? "Operator" : "Nova"
                color: root.theme.accentSoft
                font.pixelSize: 12
                font.bold: true
                elide: Label.ElideRight
            }

            Text {
                Layout.fillWidth: true
                text: root.text
                color: root.theme.textPrimary
                wrapMode: Text.Wrap
                font.pixelSize: 13
            }

            ExecutionChips {
                Layout.fillWidth: true
                theme: root.theme
                currentMode: root._isUser ? "" : root.currentMode
                meta: root._isUser ? ({}) : root.meta
                messageText: root._isUser ? "" : root.text
            }

            Label {
                Layout.fillWidth: true
                text: root.timestamp
                color: root.theme.textMuted
                font.pixelSize: 10
                elide: Label.ElideRight
            }
        }
    }
}
