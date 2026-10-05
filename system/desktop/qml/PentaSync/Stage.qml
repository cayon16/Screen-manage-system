import QtQuick

// Khung vẽ cố định 1920×1080 (đúng kích thước bản thiết kế), co giãn đều cho vừa cửa sổ.
// Màn 16:9 nào cũng lấp kín; màn tỉ lệ khác thì còn dải trắng hai bên, không méo chữ.
Item {
    id: root
    default property alias content: stage.data
    anchors.fill: parent

    Rectangle {
        anchors.fill: parent
        color: Theme.bg
    }

    Item {
        id: stage
        width: Theme.stageWidth
        height: Theme.stageHeight
        anchors.centerIn: parent
        scale: Math.min(root.width / Theme.stageWidth, root.height / Theme.stageHeight)
    }
}
