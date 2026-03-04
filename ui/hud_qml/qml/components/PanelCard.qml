import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    property var theme
    property string title: "Panel"
    property string panelId: ""
    property bool expanded: true
    property bool glow: false
    default property alias contentData: bodyColumn.data

    signal toggled(bool expanded)
    signal popOutRequested(string panelId)

    color: theme.glassBg
    border.color: theme.glassBorder
    border.width: 1
    radius: 12
    clip: true

    implicitWidth: 360
    implicitHeight: header.implicitHeight + bodyWrap.implicitHeight

    // Subtle inner highlight/shadow for depth
    Rectangle {
        anchors.fill: parent
        anchors.margins: 1
        color: "transparent"
        border.color: theme.glassHighlight
        border.width: 1
        radius: parent.radius - 1
        z: 1
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            id: header
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(0.0, 0.45, 0.55, 0.3) }
                GradientStop { position: 1.0; color: Qt.rgba(0.0, 0.35, 0.45, 0.1) }
            }
            border.width: 0
            Layout.fillWidth: true
            implicitHeight: 46

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 12

                Label {
                    text: root.title.toUpperCase()
                    color: theme.textPrimary
                    font.family: theme.titleFont
                    font.pixelSize: 13
                    font.letterSpacing: 1.2
                    font.bold: true
                    Layout.fillWidth: true
                    opacity: 0.95
                }
                Label {
                    text: root.expanded ? "−" : "+"
                    color: theme.accent
                    font.pixelSize: 20
                    font.bold: true
                    opacity: 0.8
                }
                Button {
                    id: popButton
                    text: "↗"
                    visible: !!root.panelId
                    padding: 4
                    contentItem: Text {
                        text: popButton.text
                        color: theme.textPrimary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.bold: true
                        font.pixelSize: 16
                    }
                    background: Rectangle {
                        radius: 8
                        color: popButton.down ? Qt.rgba(1.0, 1.0, 1.0, 0.12) : 
                               (popButton.hovered ? Qt.rgba(1.0, 1.0, 1.0, 0.08) : "transparent")
                        border.width: 1
                        border.color: popButton.hovered ? theme.glassBorder : "transparent"
                    }
                    onClicked: root.popOutRequested(root.panelId)
                }
            }

            MouseArea {
                id: headerMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: function(mouse) {
                    if (popButton.visible && mouse.x > parent.width - 60)
                        return
                    root.expanded = !root.expanded
                    root.toggled(root.expanded)
                }
            }

            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 1
                color: theme.glassBorder
                opacity: 0.3
            }
        }


        Item {
            id: bodyWrap
            Layout.fillWidth: true
            implicitHeight: bodyColumn.implicitHeight + 12
            height: root.expanded ? implicitHeight : 0
            opacity: root.expanded ? 1.0 : 0.0
            clip: true

            Behavior on height {
                NumberAnimation { duration: 300; easing.type: Easing.OutQuart }
            }
            Behavior on opacity {
                NumberAnimation { duration: 250 }
            }

            ColumnLayout {
                id: bodyColumn
                width: parent.width
                spacing: 12
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.leftMargin: 14
                anchors.rightMargin: 14
                anchors.topMargin: 10
                anchors.bottomMargin: 14
            }
        }
    }

    // Outer Glow Behavior
    Rectangle {
        anchors.fill: parent
        color: "transparent"
        radius: root.radius
        border.width: glow ? 2 : 0
        border.color: theme.accent
        opacity: glow ? 0.45 : 0.0
        Behavior on opacity {
            NumberAnimation { duration: 350 }
        }
    }
}
