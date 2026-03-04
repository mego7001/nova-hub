import QtQuick

QtObject {
    id: theme

    // Supported variants: jarvis_cyan | amber_industrial
    property string variantName: "jarvis_cyan"

    readonly property bool isJarvisCyan: variantName !== "amber_industrial"

    // Background layers
    property color bgGlass: isJarvisCyan ? "#CC0A1222" : "#CC1B1510"
    property color bgSolid: isJarvisCyan ? "#060B14" : "#0D0A08"

    // Typography
    property color textPrimary: isJarvisCyan ? "#EAF6FF" : "#F8E9CF"
    property color textSecondary: isJarvisCyan ? "#B3DEFF" : "#DFC79D"
    property color textMuted: isJarvisCyan ? "#7FB5D9" : "#AA8A5D"

    // Accents
    property color accentPrimary: isJarvisCyan ? "#35D6FF" : "#E3A33B"
    property color accentSecondary: isJarvisCyan ? "#21FFC6" : "#B26B2B"
    property color accentSoft: isJarvisCyan ? "#98F0FF" : "#F0C879"

    // Borders and state colors
    property color borderSoft: isJarvisCyan ? "#2D5A7A" : "#6E532B"
    property color borderHard: isJarvisCyan ? "#2DA7D6" : "#B8893E"
    property color dangerMuted: isJarvisCyan ? "#D16E8B" : "#A65A49"
    property color successMuted: isJarvisCyan ? "#58CFAE" : "#5F865C"

    // Glow
    property color glowSoft: isJarvisCyan ? "#3335D6FF" : "#33E3A33B"
    property color glowStrong: isJarvisCyan ? "#5535D6FF" : "#55E3A33B"

    // Radius
    property int radiusSm: 8
    property int radiusMd: 12
    property int radiusLg: 16

    // Animation defaults
    property int animFastMs: 120
    property int animMedMs: 180
}
