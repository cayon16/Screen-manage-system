import QtQuick

// Biểu tượng khiên + tên bệnh viện viết hoa.
Row {
    id: root
    property string name
    property real iconSize: 44
    property color iconColor: Theme.accent
    property int fontSize: 30
    property color textColor: Theme.muted
    spacing: 20

    Icon {
        anchors.verticalCenter: parent.verticalCenter
        path: Icons.shield
        size: root.iconSize
        color: root.iconColor
    }
    Text {
        anchors.verticalCenter: parent.verticalCenter
        text: root.name
        color: root.textColor
        font.family: Theme.font
        font.pixelSize: root.fontSize
        font.weight: Font.DemiBold
        font.letterSpacing: root.fontSize * 0.06
        font.capitalization: Font.AllUppercase
    }
}
