import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ScrollView {
    id: panel
    clip: true

    property var theme
    property string objectPrefix: "hudV2"
    property string timelineSummary: "No timeline events."
    property var timelineModel: []
    property bool showTimelineList: false
    property string memorySearchQuery: ""
    property string memorySearchScope: "general"
    property string memorySearchStatus: "Memory search ready."
    property int memorySearchTotal: 0
    property int memorySearchOffset: 0
    property int memorySearchLimit: 10
    property var memorySearchResults: []

    signal refreshTimelineRequested()
    signal memorySearchRequested(bool resetOffset)
    signal memoryQueryEdited(string query)
    signal memoryScopeSelectionChanged(string scope)
    signal memoryPrevRequested()
    signal memoryNextRequested()

    ColumnLayout {
        width: parent.availableWidth > 0 ? parent.availableWidth : parent.width
        spacing: 8

        Label {
            Layout.fillWidth: true
            text: panel.timelineSummary
            color: panel.theme ? panel.theme.textSecondary : "#d9ac63"
            wrapMode: Label.Wrap
        }

        Button {
            objectName: panel.objectPrefix + "HistoryRefreshButton"
            text: "Refresh Timeline"
            onClicked: panel.refreshTimelineRequested()
        }

        ListView {
            objectName: panel.objectPrefix + "TimelineList"
            Layout.fillWidth: true
            Layout.preferredHeight: panel.showTimelineList ? 150 : 0
            clip: true
            spacing: 4
            model: panel.showTimelineList ? panel.timelineModel : []
            visible: panel.showTimelineList
            delegate: Rectangle {
                required property string event_type
                required property string recorded_at
                required property string detail
                width: ListView.view.width
                radius: panel.theme ? panel.theme.radiusSm : 6
                color: panel.theme ? panel.theme.bgSolid : "#1a1208"
                border.width: 1
                border.color: panel.theme ? panel.theme.borderSoft : "#7a5520"
                implicitHeight: timelineRow.implicitHeight + 10

                ColumnLayout {
                    id: timelineRow
                    anchors.fill: parent
                    anchors.margins: 5
                    spacing: 2

                    Label {
                        Layout.fillWidth: true
                        text: recorded_at + " | " + event_type
                        color: panel.theme ? panel.theme.textPrimary : "#f5d9aa"
                        wrapMode: Label.Wrap
                    }

                    Label {
                        Layout.fillWidth: true
                        text: detail
                        color: panel.theme ? panel.theme.textMuted : "#b68d57"
                        wrapMode: Label.Wrap
                    }
                }
            }
        }

        Label {
            Layout.fillWidth: true
            text: "Memory Search"
            color: panel.theme ? panel.theme.textPrimary : "#f5d9aa"
            font.bold: true
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            TextField {
                id: memorySearchInput
                objectName: panel.objectPrefix + "MemorySearchInput"
                Layout.fillWidth: true
                placeholderText: "Search extracted memory..."
                text: panel.memorySearchQuery
                onTextChanged: panel.memoryQueryEdited(text)
            }

            ComboBox {
                id: memorySearchScope
                objectName: panel.objectPrefix + "MemorySearchScopeCombo"
                model: ["general", "project"]
                currentIndex: panel.memorySearchScope === "project" ? 1 : 0
                onActivated: {
                    if (!model || currentIndex < 0 || currentIndex >= model.length)
                        return
                    panel.memoryScopeSelectionChanged(String(model[currentIndex] || "general"))
                }
            }

            Button {
                objectName: panel.objectPrefix + "MemorySearchButton"
                text: "Search"
                onClicked: panel.memorySearchRequested(true)
            }
        }

        Label {
            Layout.fillWidth: true
            objectName: panel.objectPrefix + "MemorySearchStatusLabel"
            text: panel.memorySearchStatus + " (total=" + panel.memorySearchTotal + ", offset=" + panel.memorySearchOffset + ")"
            color: panel.theme ? panel.theme.textMuted : "#b68d57"
            wrapMode: Label.Wrap
        }

        ListView {
            objectName: panel.objectPrefix + "MemorySearchResultsList"
            Layout.fillWidth: true
            Layout.preferredHeight: 120
            clip: true
            spacing: 4
            model: panel.memorySearchResults
            delegate: Rectangle {
                width: ListView.view.width
                radius: panel.theme ? panel.theme.radiusSm : 6
                color: panel.theme ? panel.theme.bgSolid : "#1a1208"
                border.width: 1
                border.color: panel.theme ? panel.theme.borderSoft : "#7a5520"
                implicitHeight: memoryRow.implicitHeight + 8

                Label {
                    id: memoryRow
                    anchors.fill: parent
                    anchors.margins: 4
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                    color: panel.theme ? panel.theme.textMuted : "#b68d57"
                    text: {
                        var d = modelData || {}
                        var snippet = String(d.snippet || d.text || d.content || "")
                        var source = String(d.source || d.path || d.doc_id || "unknown")
                        return source + " | " + snippet
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Button {
                objectName: panel.objectPrefix + "MemorySearchPrevButton"
                text: "Prev"
                enabled: panel.memorySearchOffset > 0
                onClicked: panel.memoryPrevRequested()
            }

            Button {
                objectName: panel.objectPrefix + "MemorySearchNextButton"
                text: "Next"
                enabled: (panel.memorySearchOffset + panel.memorySearchLimit) < panel.memorySearchTotal
                onClicked: panel.memoryNextRequested()
            }
        }
    }
}
