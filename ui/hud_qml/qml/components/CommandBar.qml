import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    property var theme
    property bool busy: false
    property bool applyEnabled: true
    property var taskModesModel: []
    property string currentTaskMode: "general"
    signal sendRequested(string message)
    signal applyRequested()
    signal attachRequested()
    signal toolsRequested()
    signal taskModeChangedRequested(string modeId)

    function triggerSend() {
        var text = input.text.trim()
        if (!text.length)
            return
        root.sendRequested(text)
        input.clear()
    }

    function focusInput() {
        input.forceActiveFocus()
    }

    function _syncTaskMode() {
        var wanted = String(root.currentTaskMode || "general")
        if (!taskModeCombo.model || taskModeCombo.model.length === 0)
            return
        for (var i = 0; i < taskModeCombo.model.length; i++) {
            var row = taskModeCombo.model[i]
            var rid = row && row.id ? String(row.id) : "general"
            if (rid === wanted) {
                taskModeCombo.currentIndex = i
                return
            }
        }
        taskModeCombo.currentIndex = 0
    }

    onTaskModesModelChanged: _syncTaskMode()
    onCurrentTaskModeChanged: _syncTaskMode()
    Component.onCompleted: _syncTaskMode()

    color: theme.glassBg
    border.color: theme.glassBorder
    border.width: 1
    radius: 12
    clip: true

    // Subtle inner glow
    Rectangle {
        anchors.fill: parent
        anchors.margins: 1
        radius: 11
        color: "transparent"
        border.width: 1
        border.color: theme.glassHighlight
        opacity: 0.5
    }

    component ActionButton: Button {
        id: btn
        property color fillColor: Qt.rgba(1.0, 1.0, 1.0, 0.05)
        property color borderColor: Qt.rgba(1.0, 1.0, 1.0, 0.1)
        property color accentColor: theme.accent
        
        contentItem: Text {
            text: btn.text.toUpperCase()
            color: btn.hovered ? btn.accentColor : theme.textPrimary
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            font.bold: true
            font.pixelSize: 10
            font.letterSpacing: 1.2
            Behavior on color { ColorAnimation { duration: 150 } }
        }
        background: Rectangle {
            radius: 8
            color: btn.down ? Qt.rgba(1.0, 1.0, 1.0, 0.12) : 
                   (btn.hovered ? Qt.rgba(1.0, 1.0, 1.0, 0.08) : btn.fillColor)
            border.width: 1
            border.color: btn.hovered ? btn.accentColor : btn.borderColor
            Behavior on color { ColorAnimation { duration: 150 } }
            Behavior on border.color { ColorAnimation { duration: 150 } }
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 12

        ActionButton {
            id: attachBtn
            text: "Attach"
            accentColor: theme.positive
            onClicked: root.attachRequested()

            Rectangle {
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.rightMargin: -4
                anchors.topMargin: -4
                width: 48
                height: 16
                radius: 8
                color: theme.danger
                visible: hudController.hasImageAttachments
                border.width: 1
                border.color: "white"
                Text {
                    anchors.centerIn: parent
                    text: "VISION"
                    color: "white"
                    font.bold: true
                    font.pixelSize: 8
                }
            }
        }


        ComboBox {
            id: taskModeCombo
            Layout.preferredWidth: 160
            model: root.taskModesModel
            textRole: "title"
            onActivated: {
                if (!model || currentIndex < 0 || currentIndex >= model.length)
                    return
                var row = model[currentIndex]
                var modeId = row && row.id ? String(row.id) : "general"
                root.taskModeChangedRequested(modeId)
            }
            background: Rectangle {
                radius: 8
                color: Qt.rgba(1.0, 1.0, 1.0, 0.04)
                border.width: 1
                border.color: theme.glassBorder
            }
            contentItem: Text {
                text: taskModeCombo.displayText.toUpperCase()
                color: theme.accent
                leftPadding: 12
                rightPadding: 24
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
                font.family: theme.titleFont
                font.pixelSize: 10
                font.bold: true
                font.letterSpacing: 1.1
            }
        }

        ActionButton {
            text: "Tools"
            accentColor: theme.warning
            onClicked: root.toolsRequested()
        }

        TextField {
            id: input
            Layout.fillWidth: true
            placeholderText: "ENTER COMMAND OR MESSAGE..."
            color: theme.textPrimary
            placeholderTextColor: theme.textDim
            selectionColor: theme.accent
            selectedTextColor: "black"
            font.family: theme.bodyFont
            font.pixelSize: 14
            leftPadding: 14
            selectByMouse: true
            background: Rectangle {
                radius: 8
                color: Qt.rgba(0.0, 0.0, 0.0, 0.2)
                border.width: 1
                border.color: input.activeFocus ? theme.accent : theme.glassBorder
                Behavior on border.color { ColorAnimation { duration: 200 } }
            }
            onAccepted: root.triggerSend()
        }

        AnimatedDots {
            theme: root.theme
            running: root.busy
            visible: root.busy
        }

        ActionButton {
            text: "Send"
            accentColor: theme.accent
            onClicked: root.triggerSend()
        }

        ActionButton {
            text: "Apply"
            accentColor: theme.warning
            borderColor: root.applyEnabled ? theme.warning : Qt.rgba(1.0, 1.0, 1.0, 0.1)
            enabled: root.applyEnabled
            opacity: root.applyEnabled ? 1.0 : 0.4
            onClicked: root.applyRequested()
        }
    }
}
