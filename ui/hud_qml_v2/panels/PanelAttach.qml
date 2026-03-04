import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: panel
    property var theme
    property string objectPrefix: "hudV2"
    property string summaryText: "No attachments yet."
    property var summaryModel: []
    property bool showSummaryList: false

    signal chooseFilesRequested()

    spacing: 8

    Label {
        Layout.fillWidth: true
        text: "Attach Timeline"
        color: panel.theme ? panel.theme.textPrimary : "#eaf6ff"
        font.bold: true
        font.pixelSize: 13
    }

    Label {
        objectName: panel.objectPrefix + "AttachSummaryLabel"
        Layout.fillWidth: true
        text: panel.summaryText
        color: panel.theme ? panel.theme.textSecondary : "#d9ac63"
        wrapMode: Label.Wrap
    }

    Button {
        objectName: panel.objectPrefix + "AttachChooseFilesButton"
        text: "Choose Files"
        onClicked: panel.chooseFilesRequested()
    }

    ListView {
        objectName: panel.objectPrefix + "AttachSummaryList"
        Layout.fillWidth: true
        Layout.preferredHeight: panel.showSummaryList ? 210 : 0
        clip: true
        spacing: 4
        model: panel.showSummaryList ? panel.summaryModel : []
        visible: panel.showSummaryList
        delegate: Rectangle {
            required property string path
            required property string status
            required property string reason
            required property string reason_code
            required property string type
            width: ListView.view.width
            radius: panel.theme ? panel.theme.radiusSm : 6
            color: String(status || "").toLowerCase() === "accepted"
                ? (panel.theme ? panel.theme.glowSoft : "#2035d6ff")
                : (panel.theme ? panel.theme.bgSolid : "#1a1208")
            border.width: 1
            border.color: String(status || "").toLowerCase() === "accepted"
                ? (panel.theme ? panel.theme.successMuted : "#58cfae")
                : (panel.theme ? panel.theme.borderSoft : "#7a5520")
            implicitHeight: attachRow.implicitHeight + 10

            ColumnLayout {
                id: attachRow
                anchors.fill: parent
                anchors.margins: 5
                spacing: 2

                Label {
                    Layout.fillWidth: true
                    text: status + " | " + type + " | " + path
                    color: panel.theme ? panel.theme.textPrimary : "#f5d9aa"
                    wrapMode: Label.Wrap
                }

                Label {
                    Layout.fillWidth: true
                    text: String(reason || "").length > 0 ? reason : reason_code
                    color: panel.theme ? panel.theme.textMuted : "#b68d57"
                    wrapMode: Label.Wrap
                    visible: String(text || "").length > 0
                }
            }
        }
    }
}
