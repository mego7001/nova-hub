import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ScrollView {
    id: panel
    clip: true

    property var theme
    property bool controllerReady: false
    property string objectPrefix: "hudV2"
    property string healthStatsSummary: "Health unavailable."
    property string ollamaHealthSummary: "Ollama status unavailable."
    property var ollamaAvailableModels: []
    property string ollamaSessionModelOverride: ""
    property var healthStatsModel: []
    property string pendingSummary: ""
    property bool showPendingSummary: false

    signal refreshRequested()
    signal doctorRequested()
    signal refreshModelsRequested()
    signal ollamaModelRequested(string model)

    ColumnLayout {
        width: parent.availableWidth > 0 ? parent.availableWidth : parent.width
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Button {
                objectName: panel.objectPrefix + "HealthRefreshButton"
                Layout.fillWidth: true
                text: "Refresh Health"
                onClicked: panel.refreshRequested()
            }

            Button {
                objectName: panel.objectPrefix + "HealthDoctorButton"
                Layout.fillWidth: true
                text: "Doctor Report"
                onClicked: panel.doctorRequested()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            radius: panel.theme ? panel.theme.radiusSm : 6
            color: panel.theme ? panel.theme.bgGlass : "#2a1c0d"
            border.width: 1
            border.color: panel.theme ? panel.theme.borderSoft : "#7a5520"
            implicitHeight: ollamaHealthColumn.implicitHeight + 14

            ColumnLayout {
                id: ollamaHealthColumn
                anchors.fill: parent
                anchors.margins: 7
                spacing: 6

                Label {
                    Layout.fillWidth: true
                    text: "Local LLM: Ollama"
                    color: panel.theme ? panel.theme.textPrimary : "#f5d9aa"
                    font.bold: true
                }

                Label {
                    Layout.fillWidth: true
                    text: panel.ollamaHealthSummary
                    color: panel.theme ? panel.theme.textSecondary : "#d9ac63"
                    wrapMode: Label.Wrap
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Button {
                        objectName: panel.objectPrefix + "OllamaRefreshModelsButton"
                        text: "Refresh Models"
                        onClicked: panel.refreshModelsRequested()
                    }

                    ComboBox {
                        id: ollamaModelCombo
                        objectName: panel.objectPrefix + "OllamaModelCombo"
                        Layout.fillWidth: true
                        model: ["default"].concat(panel.ollamaAvailableModels || [])

                        function syncIndex() {
                            var wanted = String(panel.ollamaSessionModelOverride || "")
                            var resolved = wanted.length > 0 ? wanted : "default"
                            if (!model || model.length <= 0) {
                                currentIndex = -1
                                return
                            }
                            for (var i = 0; i < model.length; i++) {
                                if (String(model[i]) === resolved) {
                                    currentIndex = i
                                    return
                                }
                            }
                            currentIndex = 0
                        }

                        onActivated: {
                            if (!model || currentIndex < 0 || currentIndex >= model.length)
                                return
                            panel.ollamaModelRequested(String(model[currentIndex] || "default"))
                        }
                        onModelChanged: syncIndex()
                        onVisibleChanged: if (visible) syncIndex()
                        Component.onCompleted: syncIndex()
                    }
                }
            }
        }

        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: panel.theme ? panel.theme.textSecondary : "#d9ac63"
            text: panel.healthStatsSummary
        }

        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: panel.theme ? panel.theme.textSecondary : "#d9ac63"
            text: panel.pendingSummary
            visible: panel.showPendingSummary
        }

        ListView {
            objectName: panel.objectPrefix + "HealthStatsList"
            Layout.fillWidth: true
            Layout.preferredHeight: 220
            clip: true
            spacing: 5
            model: panel.healthStatsModel
            delegate: Rectangle {
                required property string provider
                required property string calls
                required property string success_rate
                required property string avg_latency_ms
                property string last_error: ""
                property string last_used: ""

                width: ListView.view.width
                radius: panel.theme ? panel.theme.radiusSm : 6
                color: panel.theme ? panel.theme.bgSolid : "#1a1208"
                border.width: 1
                border.color: panel.theme ? panel.theme.borderSoft : "#7a5520"
                implicitHeight: healthRow.implicitHeight + 10

                ColumnLayout {
                    id: healthRow
                    anchors.fill: parent
                    anchors.margins: 5
                    spacing: 2

                    Label {
                        Layout.fillWidth: true
                        text: provider + " | calls=" + calls + " | success=" + success_rate + " | avg=" + avg_latency_ms + "ms"
                        color: panel.theme ? panel.theme.textPrimary : "#f5d9aa"
                        wrapMode: Label.Wrap
                    }

                    Label {
                        Layout.fillWidth: true
                        text: (String(last_used || "").length > 0 || String(last_error || "").length > 0)
                            ? ("last=" + last_used + (String(last_error || "").length > 0 ? (" | error=" + last_error) : ""))
                            : ""
                        color: panel.theme ? panel.theme.textMuted : "#b68d57"
                        wrapMode: Label.Wrap
                        visible: String(text || "").length > 0
                    }
                }
            }
        }
    }
}
