import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick3D

Rectangle {
    id: root
    property var theme
    property var controller
    property var entityModel

    color: theme.bgAlt
    border.color: theme.border
    border.width: 1
    radius: 8
    clip: true

    property real yaw: -28
    property real pitch: -24
    property real distance: 360

    function clamp(v, lo, hi) {
        return Math.max(lo, Math.min(hi, v))
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 8

        Rectangle {
            id: viewportWrap
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 8
            color: "#061721"
            border.width: 1
            border.color: theme.border

            View3D {
                id: view3d
                anchors.fill: parent
                camera: camera

                environment: SceneEnvironment {
                    clearColor: "#061721"
                    backgroundMode: SceneEnvironment.Color
                }

                Node {
                    id: rig
                    eulerRotation.x: root.pitch
                    eulerRotation.y: root.yaw

                    PerspectiveCamera {
                        id: camera
                        position: Qt.vector3d(0, 120, root.distance)
                    }
                }

                DirectionalLight {
                    eulerRotation: Qt.vector3d(-35, -45, 0)
                    brightness: 1.25
                }

                PointLight {
                    position: Qt.vector3d(0, 220, 80)
                    brightness: 55
                }

                Model {
                    source: "#Cube"
                    scale: Qt.vector3d(420, 1, 420)
                    materials: PrincipledMaterial {
                        baseColor: "#0B2B38"
                        roughness: 0.9
                        metalness: 0.1
                    }
                }

                Model {
                    source: "#Cube"
                    scale: Qt.vector3d(2, 2, 420)
                    y: 1
                    materials: PrincipledMaterial { baseColor: theme.accent }
                }
                Model {
                    source: "#Cube"
                    scale: Qt.vector3d(420, 2, 2)
                    y: 1
                    materials: PrincipledMaterial { baseColor: theme.accent }
                }

                Repeater3D {
                    model: root.entityModel
                    delegate: Model {
                        required property real x
                        required property real y
                        required property real z
                        required property real size
                        required property real size_x
                        required property real size_y
                        required property real size_z
                        required property string color

                        source: "#Cube"
                        visible: model.visible
                        position: Qt.vector3d(model.x, model.y, model.z)
                        scale: Qt.vector3d(model.size_x, model.size_y, model.size_z)
                        materials: PrincipledMaterial {
                            baseColor: (model.color && model.color.length > 0) ? model.color : theme.accent
                            emissiveFactor: Qt.vector3d(0.05, 0.18, 0.2)
                            roughness: 0.35
                            metalness: 0.12
                        }
                    }
                }
            }

            Rectangle {
                anchors.fill: parent
                visible: root.controller ? root.controller.geometryEmpty : false
                color: Qt.rgba(0.02, 0.08, 0.12, 0.78)
                border.width: 1
                border.color: theme.border
                radius: 8
                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 8
                    Label {
                        text: "No geometry loaded"
                        color: theme.textPrimary
                    }
                    Button {
                        text: "Load sample"
                        onClicked: if (root.controller) root.controller.loadSampleGeometry()
                    }
                }
            }

            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.LeftButton
                property real lastX: 0
                property real lastY: 0
                onPressed: {
                    lastX = mouse.x
                    lastY = mouse.y
                }
                onPositionChanged: {
                    var dx = mouse.x - lastX
                    var dy = mouse.y - lastY
                    root.yaw += dx * 0.35
                    root.pitch = root.clamp(root.pitch + dy * 0.25, -78, -6)
                    lastX = mouse.x
                    lastY = mouse.y
                }
                WheelHandler {
                    onWheel: {
                        root.distance = root.clamp(root.distance - wheel.angleDelta.y * 0.2, 150, 700)
                    }
                }
            }
        }

        Rectangle {
            Layout.preferredWidth: 200
            Layout.fillHeight: true
            color: "#071E28"
            border.width: 1
            border.color: theme.border
            radius: 8

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 6
                Label {
                    text: "Entities"
                    color: theme.textPrimary
                    font.bold: true
                }
                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: root.entityModel
                    clip: true
                    spacing: 4
                    reuseItems: true
                    cacheBuffer: 320
                    delegate: RowLayout {
                        required property int index
                        required property string name
                        spacing: 5
                        CheckBox {
                            checked: model.visible
                            onToggled: if (root.controller) root.controller.setEntityVisible(index, checked)
                        }
                        Label {
                            text: model.name
                            color: theme.textMuted
                            elide: Label.ElideRight
                            Layout.fillWidth: true
                        }
                    }
                }
                Label {
                    Layout.fillWidth: true
                    visible: root.controller ? root.controller.geometryEmpty : false
                    text: "No entities available"
                    color: theme.textMuted
                    horizontalAlignment: Text.AlignHCenter
                }
            }
        }
    }
}
