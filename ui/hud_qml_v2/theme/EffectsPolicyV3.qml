import QtQuick

QtObject {
    id: policy

    property int stallBalancedThresholdMs: 75
    property int stallDegradedThresholdMs: 100
    property int stallCountToBalanced: 2
    property int stallCountToDegraded: 3
    property int stallWindowMs: 10000
}
