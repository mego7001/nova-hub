import QtQuick

QtObject {
    id: tokens

    property string themeVariant: "jarvis_cyan"
    property string motionIntensity: "cinematic"

    readonly property bool isJarvisCyan: themeVariant !== "amber_industrial"

    // Jarvis V3 default palette
    property color colorBg0: isJarvisCyan ? "#060B14" : "#130b03"
    property color colorBg1: isJarvisCyan ? "#0A1222" : "#1a1006"
    property color colorBg2: isJarvisCyan ? "#0F1B33" : "#211407"
    property color colorLineSoft: isJarvisCyan ? "#2D5A7A" : "#8f641d"
    property color colorLineHard: isJarvisCyan ? "#2DA7D6" : "#d79b3a"
    property color colorTextPrimary: isJarvisCyan ? "#EAF6FF" : "#ffe4a8"
    property color colorTextMuted: isJarvisCyan ? "#7FB5D9" : "#c28e3b"
    property color colorStateGood: isJarvisCyan ? "#58CFAE" : "#7ecf9b"
    property color colorStateWarn: isJarvisCyan ? "#F1CE71" : "#e2ab45"
    property color colorStateError: isJarvisCyan ? "#D16E8B" : "#d26f5f"

    property int radiusSm: 8
    property int radiusMd: 12
    property int radiusLg: 16

    property int spacingXs: 4
    property int spacingSm: 8
    property int spacingMd: 12
    property int spacingLg: 16
    property int spacingXl: 20

    property real elevationLow: 0.08
    property real elevationMid: 0.14
    property real elevationHigh: 0.2

    readonly property int _baseMotionFast: 120
    readonly property int _baseMotionNormal: 180
    readonly property int _baseMotionSlow: 260

    property int motionFastMs: motionIntensity === "reduced"
        ? Math.max(60, _baseMotionFast / 2)
        : (motionIntensity === "cinematic" ? _baseMotionFast + 40 : _baseMotionFast)

    property int motionNormalMs: motionIntensity === "reduced"
        ? Math.max(90, _baseMotionNormal / 2)
        : (motionIntensity === "cinematic" ? _baseMotionNormal + 80 : _baseMotionNormal)

    property int motionSlowMs: motionIntensity === "reduced"
        ? Math.max(120, _baseMotionSlow / 2)
        : (motionIntensity === "cinematic" ? _baseMotionSlow + 120 : _baseMotionSlow)
}
