pragma ComponentBehavior: Bound
import QtQuick

// Bong bóng "Superdoc đang soạn câu trả lời" — 3 chấm nhấp nháy lần lượt.
Rectangle {
    width: dots.width + 84
    height: 82
    radius: 28
    bottomLeftRadius: 6
    color: Theme.surface
    border.width: 2
    border.color: Theme.lineSoft

    Row {
        id: dots
        anchors.centerIn: parent
        spacing: 14
        Repeater {
            model: 3
            Rectangle {
                id: dot
                required property int index
                width: 18
                height: 18
                radius: 9
                color: Theme.accent
                SequentialAnimation on opacity {
                    loops: Animation.Infinite
                    PauseAnimation { duration: dot.index * 180 }
                    NumberAnimation { to: 1; duration: 390 }
                    NumberAnimation { to: 0.22; duration: 390 }
                    PauseAnimation { duration: 520 - dot.index * 180 }
                }
            }
        }
    }
}
