import QtQuick

// Ô vuông nền xanh nhạt chứa 1 biểu tượng (dùng ở menu, chat, hộp thoại).
Rectangle {
    id: root
    property string icon
    property real iconSize: 60
    property real iconStroke: 1.6
    property color iconColor: Theme.accent
    property real tileSize: 112

    width: tileSize
    height: tileSize
    radius: tileSize * 0.22
    color: Theme.accentSoft

    Icon {
        anchors.centerIn: parent
        path: root.icon
        size: root.iconSize
        strokeWidth: root.iconStroke
        color: root.iconColor
    }
}
