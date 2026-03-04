import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: root

    property var theme
    property string objectPrefix: "hudV2"
    property string activeDrawer: "tools"
    property bool compactMode: false
    property var drawers: []
    signal drawerRequested(string drawerId)

    function _capitalize(value) {
        var text = String(value || "")
        if (!text.length)
            return text
        return text.charAt(0).toUpperCase() + text.slice(1)
    }

    function _drawerObjectName(drawerId, drawerTitle) {
        if (root.compactMode)
            return root.objectPrefix + "Drawer" + root._capitalize(drawerTitle) + "Button"
        return root.objectPrefix + "DrawerTab_" + drawerId
    }

    function _isActive(drawerId) {
        return String(root.activeDrawer || "").toLowerCase() === String(drawerId || "").toLowerCase()
    }

    spacing: 8

    Label {
        Layout.fillWidth: true
        text: root.compactMode ? "Drawer" : "Navigation"
        color: root.theme ? root.theme.textPrimary : "#eaf6ff"
        font.bold: true
        font.pixelSize: 13
    }

    Loader {
        Layout.fillWidth: true
        sourceComponent: root.compactMode ? compactTabs : fullTabs
    }

    Component {
        id: fullTabs

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 6

            Repeater {
                model: root.drawers
                delegate: Rectangle {
                    required property var modelData
                    Layout.fillWidth: true
                    radius: root.theme ? root.theme.radiusSm : 8
                    color: root._isActive(modelData.id) ? (root.theme ? root.theme.glowSoft : "#332da7d6") : (root.theme ? root.theme.bgSolid : "#060b14")
                    border.width: 1
                    border.color: root._isActive(modelData.id) ? (root.theme ? root.theme.borderHard : "#2da7d6") : (root.theme ? root.theme.borderSoft : "#2d5a7a")
                    implicitHeight: 36

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 6
                        spacing: 8

                        Rectangle {
                            Layout.preferredWidth: 8
                            Layout.preferredHeight: 8
                            radius: 4
                            color: root._isActive(modelData.id) ? (root.theme ? root.theme.accentPrimary : "#35d6ff") : (root.theme ? root.theme.borderSoft : "#2d5a7a")
                        }

                        Label {
                            Layout.fillWidth: true
                            text: String(modelData.title || "")
                            color: root.theme ? root.theme.textSecondary : "#b3deff"
                            font.bold: root._isActive(modelData.id)
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: root.drawerRequested(String(modelData.id || "tools"))
                    }

                    // Keep test-discoverable object naming in full mode.
                    objectName: root._drawerObjectName(String(modelData.id || ""), String(modelData.title || ""))
                }
            }
        }
    }

    Component {
        id: compactTabs

        GridLayout {
            Layout.fillWidth: true
            columns: 3
            rowSpacing: 6
            columnSpacing: 6

            Button {
                objectName: root._drawerObjectName("tools", "Tools")
                text: "Tools"
                checkable: true
                checked: root.activeDrawer === "tools"
                onClicked: root.drawerRequested("tools")
            }

            Button {
                objectName: root._drawerObjectName("attach", "Attach")
                text: "Attach"
                checkable: true
                checked: root.activeDrawer === "attach"
                onClicked: root.drawerRequested("attach")
            }

            Button {
                objectName: root._drawerObjectName("health", "Health")
                text: "Health"
                checkable: true
                checked: root.activeDrawer === "health"
                onClicked: root.drawerRequested("health")
            }

            Button {
                objectName: root._drawerObjectName("history", "History")
                text: "History"
                checkable: true
                checked: root.activeDrawer === "history"
                onClicked: root.drawerRequested("history")
            }

            Button {
                objectName: root._drawerObjectName("voice", "Voice")
                text: "Voice"
                checkable: true
                checked: root.activeDrawer === "voice"
                onClicked: root.drawerRequested("voice")
            }
        }
    }
}
