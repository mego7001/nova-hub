import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ScrollView {
    id: panel
    clip: true

    property var theme
    property bool controllerReady: false
    property string objectPrefix: "hudV2"
    property bool showCatalog: false
    property var toolsCatalogModel: []
    property string toolsBadge: "Tools: unavailable"
    property string confirmationSummary: ""
    property string evidenceChip: ""
    property string actionsChip: ""
    property string risksChip: ""
    property string toggleToolsText: "Toggle Tools Menu"
    property string queueApplyText: "Queue Apply Candidate"
    property string confirmPendingText: "Confirm Pending"
    property string rejectPendingText: "Reject Pending"
    property string runSecurityText: "Run Security Audit"
    property string refreshTimelineText: "Refresh Timeline"
    property bool applyEnabled: false
    property bool hasPendingApproval: false
    property bool confirmationReadOnly: false
    property bool confirmationLocked: false

    signal toggleToolsRequested()
    signal queueApplyRequested()
    signal confirmPendingRequested()
    signal rejectPendingRequested()
    signal runSecurityRequested()
    signal refreshTimelineRequested()

    ColumnLayout {
        width: parent.availableWidth > 0 ? parent.availableWidth : parent.width
        spacing: 8

        Label {
            Layout.fillWidth: true
            text: "Tools Hub"
            color: panel.theme ? panel.theme.textPrimary : "#eaf6ff"
            font.bold: true
            font.pixelSize: 13
        }

        Label {
            Layout.fillWidth: true
            text: panel.toolsBadge
            color: panel.theme ? panel.theme.textSecondary : "#d9ac63"
            wrapMode: Label.Wrap
        }

        Label {
            Layout.fillWidth: true
            text: panel.confirmationSummary
            color: panel.theme ? panel.theme.textMuted : "#b68d57"
            wrapMode: Label.Wrap
            visible: String(panel.confirmationSummary || "").length > 0
        }

        ListView {
            objectName: panel.objectPrefix + "ToolsCatalogList"
            Layout.fillWidth: true
            Layout.preferredHeight: panel.showCatalog ? 165 : 0
            clip: true
            spacing: 5
            model: panel.showCatalog ? panel.toolsCatalogModel : []
            visible: panel.showCatalog
            delegate: Rectangle {
                required property string group
                required property string badge
                required property string description
                required property string reason
                width: ListView.view.width
                radius: panel.theme ? panel.theme.radiusSm : 6
                color: panel.theme ? panel.theme.bgSolid : "#1a1208"
                border.width: 1
                border.color: panel.theme ? panel.theme.borderSoft : "#7a5520"
                implicitHeight: toolRow.implicitHeight + 10

                ColumnLayout {
                    id: toolRow
                    anchors.fill: parent
                    anchors.margins: 5
                    spacing: 2

                    Label {
                        Layout.fillWidth: true
                        text: group + " | " + badge + (reason.length > 0 ? (" | " + reason) : "")
                        color: panel.theme ? panel.theme.textPrimary : "#f5d9aa"
                        font.bold: true
                        wrapMode: Label.Wrap
                    }

                    Label {
                        Layout.fillWidth: true
                        text: description
                        color: panel.theme ? panel.theme.textMuted : "#b68d57"
                        wrapMode: Label.Wrap
                        visible: String(description || "").length > 0
                    }
                }
            }
        }

        Button {
            objectName: panel.objectPrefix + "ToolsToggleMenuButton"
            text: panel.toggleToolsText
            onClicked: panel.toggleToolsRequested()
        }

        Button {
            objectName: panel.objectPrefix + "ToolsQueueApplyButton"
            text: panel.queueApplyText
            enabled: panel.controllerReady && panel.applyEnabled
            onClicked: panel.queueApplyRequested()
        }

        Button {
            objectName: panel.objectPrefix + "ToolsConfirmPendingButton"
            text: panel.confirmPendingText
            enabled: panel.controllerReady && panel.hasPendingApproval && !panel.confirmationReadOnly && !panel.confirmationLocked
            onClicked: panel.confirmPendingRequested()
        }

        Button {
            objectName: panel.objectPrefix + "ToolsRejectPendingButton"
            text: panel.rejectPendingText
            enabled: panel.controllerReady && panel.hasPendingApproval && !panel.confirmationReadOnly && !panel.confirmationLocked
            onClicked: panel.rejectPendingRequested()
        }

        Button {
            objectName: panel.objectPrefix + "ToolsRunSecurityButton"
            text: panel.runSecurityText
            onClicked: panel.runSecurityRequested()
        }

        Button {
            objectName: panel.objectPrefix + "ToolsRefreshTimelineButton"
            text: panel.refreshTimelineText
            onClicked: panel.refreshTimelineRequested()
        }

        Label {
            Layout.fillWidth: true
            text: String(panel.evidenceChip || "")
            color: panel.theme ? panel.theme.textMuted : "#b68d57"
            wrapMode: Label.Wrap
            visible: String(panel.evidenceChip || "").length > 0
        }

        Label {
            Layout.fillWidth: true
            text: String(panel.actionsChip || "")
            color: panel.theme ? panel.theme.textMuted : "#b68d57"
            wrapMode: Label.Wrap
            visible: String(panel.actionsChip || "").length > 0
        }

        Label {
            Layout.fillWidth: true
            text: String(panel.risksChip || "")
            color: panel.theme ? panel.theme.textMuted : "#b68d57"
            wrapMode: Label.Wrap
            visible: String(panel.risksChip || "").length > 0
        }
    }
}
