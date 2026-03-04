import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    property var theme
    property var meta: ({})
    property string currentMode: ""
    property string messageText: ""
    readonly property var chipRows: _buildRows()

    visible: chipRows.length > 0
    implicitHeight: visible ? flow.implicitHeight : 0
    implicitWidth: flow.implicitWidth

    function _stringValue(value) {
        if (value === undefined || value === null)
            return ""
        return String(value)
    }

    function _inferProvider() {
        var text = String(root.messageText || "").toLowerCase()
        if (text.indexOf("deepseek") >= 0)
            return "DeepSeek"
        if (text.indexOf("gemini") >= 0)
            return "Gemini"
        if (text.indexOf("openai") >= 0)
            return "OpenAI"
        return ""
    }

    function _inferTool() {
        var text = String(root.messageText || "").toLowerCase()
        if (text.indexOf("patch.apply") >= 0)
            return "patch.apply"
        if (text.indexOf("patch.plan") >= 0)
            return "patch.plan"
        if (text.indexOf("verify") >= 0)
            return "verify"
        if (text.indexOf("security.audit") >= 0)
            return "security.audit"
        return ""
    }

    function _buildRows() {
        var rows = []
        var payload = root.meta && typeof root.meta === "object" ? root.meta : ({})

        var modeValue = _stringValue(payload.mode)
        if (!modeValue.length)
            modeValue = _stringValue(root.currentMode)
        if (modeValue.length)
            rows.push({ title: "Mode", value: modeValue })

        var providerValue = _stringValue(payload.provider)
        if (!providerValue.length)
            providerValue = _stringValue(payload.model)
        if (!providerValue.length)
            providerValue = _inferProvider()
        if (providerValue.length)
            rows.push({ title: "Provider", value: providerValue })

        var toolValue = _stringValue(payload.tool_name)
        if (!toolValue.length && payload.tool_calls !== undefined && payload.tool_calls !== null) {
            if (payload.tool_calls.length > 0) {
                var first = payload.tool_calls[0]
                if (first && typeof first === "object")
                    toolValue = _stringValue(first.name)
            }
        }
        if (!toolValue.length)
            toolValue = _inferTool()
        if (toolValue.length)
            rows.push({ title: "Tool", value: toolValue })

        var latencyValue = ""
        if (payload.latency_ms !== undefined && payload.latency_ms !== null) {
            latencyValue = _stringValue(payload.latency_ms) + "ms"
        }
        if (latencyValue.length)
            rows.push({ title: "Latency", value: latencyValue })

        return rows
    }

    Flow {
        id: flow
        width: parent.width
        spacing: 6

        Repeater {
            model: root.chipRows

            Rectangle {
                required property var modelData

                radius: root.theme.radiusSm
                color: "transparent"
                border.width: 1
                border.color: root.theme.borderHard
                implicitHeight: 24
                implicitWidth: chipText.implicitWidth + 12

                Label {
                    id: chipText
                    anchors.centerIn: parent
                    text: modelData.title + ": " + modelData.value
                    color: root.theme.textSecondary
                    font.pixelSize: 11
                    elide: Label.ElideRight
                }
            }
        }
    }
}