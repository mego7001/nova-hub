import QtQuick
import QtQuick.Layouts

RowLayout {
    id: root
    property var theme
    property bool running: true
    spacing: 4

    Repeater {
        model: 3
        Rectangle {
            id: dot
            width: 7
            height: 7
            radius: 3.5
            color: theme ? theme.accentSoft : "#00E5FF"
            opacity: 0.3
            
            layer.enabled: true
            layer.effect: ShaderEffect {
                property variant source: dot
                property color glowColor: dot.color
            }

            SequentialAnimation on opacity {
                loops: Animation.Infinite
                running: root.running
                NumberAnimation { from: 0.3; to: 1.0; duration: 400; easing.type: Easing.InOutSine }
                NumberAnimation { from: 1.0; to: 0.3; duration: 400; easing.type: Easing.InOutSine }
                PauseAnimation { duration: index * 150 }
            }

            SequentialAnimation on scale {
                loops: Animation.Infinite
                running: root.running
                NumberAnimation { from: 1.0; to: 1.25; duration: 400; easing.type: Easing.InOutSine }
                NumberAnimation { from: 1.25; to: 1.0; duration: 400; easing.type: Easing.InOutSine }
                PauseAnimation { duration: index * 150 }
            }
        }
    }

}
