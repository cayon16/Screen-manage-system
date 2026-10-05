import QtQuick

// "Bạn còn muốn tiếp tục trò chuyện không?" — đếm ngược, chạm bất kỳ đâu = còn ở đây.
Rectangle {
    id: dlg
    property int seconds: 30
    property int serial: 0
    property int remaining: seconds
    signal ack()

    color: Theme.scrim

    function restart() {
        remaining = seconds
    }
    onSerialChanged: restart()
    onVisibleChanged: if (visible) restart()

    Timer {
        interval: 1000
        repeat: true
        running: dlg.visible && dlg.remaining > 0
        onTriggered: dlg.remaining -= 1
    }

    MouseArea {
        anchors.fill: parent
        onPressed: dlg.ack()
    }

    Rectangle {
        anchors.centerIn: parent
        width: 1080
        height: content.implicitHeight + 130
        radius: 34
        color: Theme.bg
        border.width: 3
        border.color: Theme.lineStrong

        Column {
            id: content
            anchors.top: parent.top
            anchors.topMargin: 70
            anchors.horizontalCenter: parent.horizontalCenter
            width: parent.width - 152
            spacing: 36

            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                width: 124; height: 124; radius: 62
                color: Theme.accentSoft
                Icon {
                    anchors.centerIn: parent
                    path: Icons.clock
                    size: 68
                    strokeWidth: 1.6
                }
            }
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: "Bạn còn muốn tiếp tục\ntrò chuyện không?"
                lineHeight: 1.22
                color: Theme.ink
                font.family: Theme.font
                font.pixelSize: 62
                font.weight: Font.ExtraBold
            }
            Column {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 14
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Đoạn chat sẽ tự kết thúc sau"
                    color: Theme.muted
                    font.family: Theme.font
                    font.pixelSize: 32
                }
                Row {
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: 12
                    Text {
                        id: number
                        text: Math.max(0, dlg.remaining)
                        color: Theme.accent
                        font.family: Theme.font
                        font.pixelSize: 88
                        font.weight: Font.ExtraBold
                    }
                    Text {
                        anchors.baseline: number.baseline
                        text: "giây"
                        color: Theme.muted
                        font.family: Theme.font
                        font.pixelSize: 36
                        font.weight: Font.Medium
                    }
                }
                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 520; height: 10; radius: 5
                    color: Theme.line
                    Rectangle {
                        width: parent.width * (dlg.seconds > 0 ? Math.max(0, dlg.remaining) / dlg.seconds : 0)
                        height: parent.height
                        radius: 5
                        color: Theme.accent
                        Behavior on width { NumberAnimation { duration: 900 } }
                    }
                }
            }
            AppButton {
                width: parent.width
                variant: "primary"
                icon: Icons.check
                iconStroke: 2.4
                iconSize: 40
                text: "Tôi vẫn ở đây"
                fontSize: 44
                fontWeight: Font.Bold
                verticalPadding: 34
                radius: 22
                onTapped: dlg.ack()
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Chạm vào bất kỳ đâu cũng được tính là bạn còn ở đây"
                color: Theme.faint2
                font.family: Theme.font
                font.pixelSize: 28
            }
        }
    }
}
