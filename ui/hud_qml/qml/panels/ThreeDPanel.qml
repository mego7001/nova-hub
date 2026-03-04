import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Item {
    id: root
    property var theme
    property var controller
    property bool lazyLoaded: false

    function ensureActivated() {
        if (lazyLoaded)
            return
        lazyLoaded = true
        if (controller)
            controller.activateThreeD()
    }

    onVisibleChanged: {
        if (visible)
            ensureActivated()
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 8

        Label {
            Layout.fillWidth: true
            text: controller ? controller.threeDSummary : ""
            color: theme.textMuted
            wrapMode: Label.Wrap
        }
        RowLayout {
            Layout.fillWidth: true
            visible: controller ? controller.geometryEmpty : false
            Label {
                Layout.fillWidth: true
                text: "No geometry loaded"
                color: theme.textMuted
                elide: Label.ElideRight
            }
            Button {
                text: "Load sample"
                onClicked: if (controller) controller.loadSampleGeometry()
            }
        }
        Loader {
            Layout.fillWidth: true
            Layout.preferredHeight: 320
            active: root.visible && root.lazyLoaded
            sourceComponent: ThreeDViewport {
                theme: root.theme
                controller: root.controller
                entityModel: root.controller ? root.controller.entitiesModel : null
            }
        }
    }
}
