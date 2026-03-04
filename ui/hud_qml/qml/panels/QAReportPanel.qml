import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    property var theme
    property var controller

    color: theme.glassBg
    border.color: theme.glassBorder
    border.width: 1
    radius: 12
    clip: true

    // Inner highlight
    Rectangle {
        anchors.fill: parent
        anchors.margins: 1
        color: "transparent"
        border.color: theme.glassHighlight
        border.width: 1
        radius: parent.radius - 1
    }

    property string severityFilter: "all"
    property string searchText: ""

    function _matchesFinding(item) {
        if (!item) return false
        var sev = String(item.severity || "").toLowerCase()
        var code = String(item.code || "").toLowerCase()
        var msg = String(item.message || "").toLowerCase()
        if (severityFilter !== "all" && sev !== severityFilter) return false
        if (!searchText.length) return true
        var q = searchText.toLowerCase()
        return code.indexOf(q) >= 0 || msg.indexOf(q) >= 0
    }

    function _statusColor(text) {
        var upper = String(text || "").toUpperCase()
        if (upper.indexOf("FAIL") >= 0) return theme.danger
        if (upper.indexOf("WARN") >= 0) return theme.warning
        return theme.positive
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 12

        // Header Row
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Label {
                    text: "QUALITY ASSURANCE REPORT"
                    color: theme.textPrimary
                    font.family: theme.titleFont
                    font.pixelSize: 11
                    font.bold: true
                    font.letterSpacing: 1.5
                }
                Label {
                    text: controller ? controller.qaReportText.toUpperCase() : "NO REPORT LOADED"
                    color: theme.textMuted
                    font.pixelSize: 9
                    font.bold: true
                }
            }

            Rectangle {
                Layout.preferredWidth: 200
                Layout.preferredHeight: 32
                radius: 8
                color: Qt.rgba(0.0, 0.0, 0.0, 0.25)
                border.width: 1
                border.color: root._statusColor(controller ? controller.qaStatusChip : "")
                
                Label {
                    anchors.centerIn: parent
                    text: controller ? controller.qaStatusChip.toUpperCase() : "QA: N/A"
                    color: theme.textPrimary
                    font.family: theme.titleFont
                    font.pixelSize: 10
                    font.bold: true
                }
            }
        }

        // Secondary Controls
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Label {
                Layout.fillWidth: true
                text: controller ? controller.qaLatestPath : ""
                color: theme.textDim
                font.pixelSize: 10
                elide: Label.ElideMiddle
            }
            RowLayout {
                spacing: 8
                Button {
                    text: "REFRESH"
                    flat: true
                    onClicked: if (controller) controller.refreshQaReport()
                }
                Button {
                    text: "OPEN FOLDER"
                    flat: true
                    onClicked: if (controller) controller.runPaletteAction("reports.open", "")
                }
            }
        }

        // Filters
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            ComboBox {
                Layout.preferredWidth: 140
                model: ["all", "info", "warn", "fail", "error"]
                onActivated: root.severityFilter = String(currentText)
            }

            TextField {
                Layout.fillWidth: true
                placeholderText: "Search findings..."
                color: theme.textPrimary
                background: Rectangle {
                    color: Qt.rgba(1.0, 1.0, 1.0, 0.04)
                    border.color: theme.glassHighlight
                    radius: 6
                }
                onTextChanged: root.searchText = text
            }
        }

        // Content Area
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 12

            // Findings List
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: Qt.rgba(1.0, 1.0, 1.0, 0.03)
                border.width: 1
                border.color: Qt.rgba(1.0, 1.0, 1.0, 0.08)
                radius: 10
                clip: true

                ListView {
                    id: findingsView
                    anchors.fill: parent
                    anchors.margins: 12
                    model: controller ? controller.qaFindingsModel : null
                    spacing: 12
                    clip: true
                    cacheBuffer: 1000
                    reuseItems: true

                    delegate: Item {
                        required property string severity
                        required property string code
                        required property string message
                        required property string context
                        width: ListView.view.width
                        visible: root._matchesFinding(model)
                        height: visible ? content.implicitHeight + 12 : 0

                        ColumnLayout {
                            id: content
                            width: parent.width
                            spacing: 4
                            RowLayout {
                                Label {
                                    text: severity.toUpperCase() + " • " + code
                                    color: severity === "fail" || severity === "error" ? theme.danger
                                          : severity === "warn" ? theme.warning : theme.accent
                                    font.family: theme.titleFont
                                    font.pixelSize: 10
                                    font.bold: true
                                }
                            }
                            Label {
                                Layout.fillWidth: true
                                text: message
                                color: theme.textPrimary
                                font.pixelSize: 12
                                wrapMode: Label.Wrap
                            }
                            Label {
                                Layout.fillWidth: true
                                text: context
                                color: theme.textDim
                                font.pixelSize: 10
                                wrapMode: Label.Wrap
                                visible: context.length > 0
                            }
                            Rectangle {
                                Layout.fillWidth: true
                                height: 1
                                color: theme.glassHighlight
                                opacity: 0.3
                            }
                        }
                    }
                }
            }

            // Metrics List
            Rectangle {
                Layout.preferredWidth: 260
                Layout.fillHeight: true
                color: Qt.rgba(1.0, 1.0, 1.0, 0.03)
                border.width: 1
                border.color: Qt.rgba(1.0, 1.0, 1.0, 0.08)
                radius: 10
                clip: true

                ListView {
                    id: metricsView
                    anchors.fill: parent
                    anchors.margins: 12
                    model: controller ? controller.qaMetricsModel : null
                    spacing: 10
                    clip: true
                    cacheBuffer: 500
                    reuseItems: true
                    delegate: ColumnLayout {
                        required property string section
                        required property string key
                        required property string value
                        width: metricsView.width
                        spacing: 2
                        Label {
                            Layout.fillWidth: true
                            text: (section + "." + key).toUpperCase()
                            color: theme.accent
                            font.family: theme.titleFont
                            font.pixelSize: 9
                            font.bold: true
                            opacity: 0.8
                        }
                        Label {
                            Layout.fillWidth: true
                            text: value
                            color: theme.textPrimary
                            font.pixelSize: 11
                            font.bold: true
                            elide: Label.ElideRight
                        }
                        Rectangle {
                            Layout.fillWidth: true
                            height: 1
                            color: theme.glassHighlight
                            opacity: 0.2
                        }
                    }
                }
            }
        }
    }
}
