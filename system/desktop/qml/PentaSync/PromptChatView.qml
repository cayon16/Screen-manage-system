import QtQuick

// Màn 4 khi hệ thống thức — chạm vào bất kỳ đâu là mở chat (Python tự gửi khi có chạm).
Stage {
    id: root
    property string hospitalName

    HospitalMark {
        x: 72
        y: 40
        name: root.hospitalName
        iconSize: 40
        fontSize: 28
        textColor: Theme.faint
    }

    Column {
        anchors.centerIn: parent
        spacing: 52

        Column {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 18
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Trợ lý ảo của bệnh viện"
                color: Theme.muted
                font.family: Theme.font
                font.pixelSize: 42
                font.weight: Font.Medium
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Superdoc"
                color: Theme.ink
                font.family: Theme.font
                font.pixelSize: 108
                font.weight: Font.ExtraBold
                font.letterSpacing: -2
            }
        }

        Rectangle {
            id: card
            anchors.horizontalCenter: parent.horizontalCenter
            width: 1000
            height: cardColumn.implicitHeight + 136
            radius: 34
            color: Theme.bg
            border.width: 4
            border.color: Theme.accent

            SequentialAnimation on border.color {
                loops: Animation.Infinite
                ColorAnimation { to: Theme.accentBorder; duration: 1400; easing.type: Easing.InOutQuad }
                ColorAnimation { to: Theme.accent; duration: 1400; easing.type: Easing.InOutQuad }
            }

            Column {
                id: cardColumn
                anchors.centerIn: parent
                spacing: 30
                IconTile {
                    anchors.horizontalCenter: parent.horizontalCenter
                    icon: Icons.hand
                    tileSize: 144
                    iconSize: 78
                    iconStroke: 1.5
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Chạm để bắt đầu"
                    color: Theme.ink
                    font.family: Theme.font
                    font.pixelSize: 70
                    font.weight: Font.ExtraBold
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 740
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    lineHeight: 1.5
                    text: "Hỏi về giờ khám, quy trình đăng ký, bảo hiểm y tế hay vị trí các khoa phòng."
                    color: Theme.muted
                    font.family: Theme.font
                    font.pixelSize: 34
                }
            }
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Không lưu thông tin cá nhân của bạn"
            color: Theme.faint2
            font.family: Theme.font
            font.pixelSize: 27
        }
    }
}
