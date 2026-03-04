import QtQuick

QtObject {
    id: motion

    property string intensity: "cinematic" // cinematic | normal | reduced

    readonly property int fadeMs: intensity === "reduced" ? 90 : (intensity === "cinematic" ? 260 : 180)
    readonly property int panelSlideMs: intensity === "reduced" ? 110 : (intensity === "cinematic" ? 320 : 200)
    readonly property int pulseMs: intensity === "reduced" ? 100 : (intensity === "cinematic" ? 240 : 160)
    readonly property int statusSwapMs: intensity === "reduced" ? 80 : (intensity === "cinematic" ? 220 : 140)
}
