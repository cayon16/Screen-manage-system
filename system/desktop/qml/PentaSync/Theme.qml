pragma Singleton
import QtQuick

// Bảng màu của bản thiết kế nền trắng đã duyệt (../design/*.dc.html).
QtObject {
    readonly property string font: "Be Vietnam Pro"

    readonly property color bg: "#FFFFFF"
    readonly property color surface: "#F5F7F9"
    readonly property color surfaceMuted: "#F0F2F4"
    readonly property color chip: "#EEF1F4"

    readonly property color ink: "#101A22"
    readonly property color ink2: "#2E3E4A"
    readonly property color muted: "#5A6B78"
    readonly property color faint: "#7A8894"
    readonly property color faint2: "#8B97A2"
    readonly property color faint3: "#9AA8B4"
    readonly property color disabled: "#BCC6CF"

    readonly property color line: "#E4E9ED"
    readonly property color lineSoft: "#DCE3E9"
    readonly property color lineStrong: "#C3CDD6"

    readonly property color accent: "#1668A8"
    readonly property color accentPressed: "#0F4E7E"
    readonly property color accentSoft: "#EDF3F8"
    readonly property color accentBorder: "#BBD3E6"

    readonly property color danger: "#B24A41"
    readonly property color dangerStrong: "#C8534A"
    readonly property color dangerSoft: "#FBEFEE"
    readonly property color dangerSurface: "#FDF7F6"
    readonly property color dangerBorder: "#E3B4B0"
    readonly property color dangerText: "#A2726C"

    readonly property color scrim: Qt.rgba(16 / 255, 26 / 255, 34 / 255, 0.34)

    readonly property int stageWidth: 1920
    readonly property int stageHeight: 1080
}
