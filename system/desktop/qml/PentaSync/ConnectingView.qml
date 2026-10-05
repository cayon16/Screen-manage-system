import QtQuick

// Hiện khi chưa nối được backend. Chờ 2 giây mới hiện để backend khởi động lại nhanh không
// làm các màn chớp trắng.
Item {
    id: root
    property int role: 0
    property string roleName: ""
    property bool showNow: false

    Timer {
        interval: 2000
        running: true
        onTriggered: root.showNow = true
    }

    Rectangle {
        anchors.fill: parent
        color: Theme.bg
    }

    Stage {
        visible: root.showNow

        Column {
            anchors.centerIn: parent
            spacing: 28

            Icon {
                anchors.horizontalCenter: parent.horizontalCenter
                path: Icons.shield
                size: 96
                color: Theme.accent
                SequentialAnimation on opacity {
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.35; duration: 900; easing.type: Easing.InOutQuad }
                    NumberAnimation { to: 1; duration: 900; easing.type: Easing.InOutQuad }
                }
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Đang kết nối hệ thống…"
                color: Theme.ink
                font.family: Theme.font
                font.pixelSize: 56
                font.weight: Font.Bold
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Màn " + root.role + (root.roleName ? " · " + root.roleName : "")
                color: Theme.faint
                font.family: Theme.font
                font.pixelSize: 32
            }
        }
    }
}
