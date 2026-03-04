import QtQuick

QtObject {
    id: theme

    property bool jarvisMode: true

    // Base Palette: Deep Midnight & Electric Blue
    property color accent: "#00E5FF"           // Electric Cyan
    property color accentSoft: "#64F5FF"
    property color bg: jarvisMode ? "#020B14" : "#05121E"
    property color bgAlt: jarvisMode ? "#081B2B" : "#0E2538"

    // Glassmorphism tokens
    property color glassBg: Qt.rgba(0.05, 0.15, 0.25, 0.65)
    property color glassBorder: Qt.rgba(0.0, 0.9, 1.0, 0.45)
    property color glassHighlight: Qt.rgba(1.0, 1.0, 1.0, 0.08)

    // Legacy Compatibility Aliases (to prevent "undefined" errors)
    property color border: glassBorder
    property color borderSoft: Qt.rgba(1.0, 1.0, 1.0, 0.1)
    property color panel: glassBg
    property color panelRaised: jarvisMode ? "#D01A3B52" : "#E0224A63"

    // Functional colors
    property color positive: "#00FFC2"         // Emerald Glow
    property color warning: "#FFD64A"          // Amber Gold
    property color danger: "#FF4D6D"           // Neon Rose
    property color info: "#4AA3FF"

    // Typography
    property color textPrimary: "#FFFFFF"
    property color textMuted: "#B8D4E2"
    property color textDim: "#7A98A8"

    property string titleFont: "Bahnschrift"
    property string bodyFont: "Segoe UI Semilight"
}
