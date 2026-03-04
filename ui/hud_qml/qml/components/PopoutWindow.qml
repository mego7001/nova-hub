import QtQuick
import QtQuick.Window
import QtQuick.Controls

Window {
    id: root
    property var theme
    property var controller
    property string titleText: "Panel"
    property Component contentComponent
    signal windowClosing()

    width: 980
    height: 680
    visible: false
    title: titleText
    color: "transparent"

    onClosing: {
        root.windowClosing()
    }

    Rectangle {
        anchors.fill: parent
        radius: 12
        color: theme ? theme.panel : "#0A2230"
        border.width: 1
        border.color: theme ? theme.border : "#1E4A5B"
        clip: true

        Loader {
            anchors.fill: parent
            anchors.margins: 10
            active: root.visible && !!root.contentComponent
            sourceComponent: root.contentComponent
        }
    }
}
