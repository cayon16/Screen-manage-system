import QtQuick
import QtQuick.Layouts

// Màn 2 — menu 2 lựa chọn.
Stage {
    id: root
    property var client
    property string hospitalName

    component MenuCard: Rectangle {
        id: card
        property string icon
        property string title
        property string description
        signal tapped()

        Layout.fillWidth: true
        Layout.preferredWidth: 1
        Layout.preferredHeight: 470
        radius: 28
        color: tap.pressed ? Theme.accentSoft : Theme.bg
        border.width: 3
        border.color: tap.pressed ? Theme.accent : Theme.lineStrong

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 56
            spacing: 26

            IconTile { icon: card.icon; tileSize: 112; iconSize: 60 }
            Text {
                Layout.fillWidth: true
                text: card.title
                color: Theme.ink
                font.family: Theme.font
                font.pixelSize: 58
                font.weight: Font.Bold
            }
            Text {
                Layout.fillWidth: true
                Layout.rightMargin: 60
                text: card.description
                color: Theme.muted
                wrapMode: Text.WordWrap
                lineHeight: 1.45
                font.family: Theme.font
                font.pixelSize: 32
            }
            Item { Layout.fillHeight: true }
        }

        Icon {
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 48
            path: Icons.chevronRight
            size: 46
            strokeWidth: 2
            color: Theme.faint3
        }

        TapHandler {
            id: tap
            gesturePolicy: TapHandler.ReleaseWithinBounds
            onTapped: card.tapped()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 118
            HospitalMark {
                anchors.left: parent.left
                anchors.leftMargin: 72
                anchors.verticalCenter: parent.verticalCenter
                anchors.verticalCenterOffset: 4
                name: root.hospitalName
            }
            Text {
                anchors.right: parent.right
                anchors.rightMargin: 72
                anchors.verticalCenter: parent.verticalCenter
                anchors.verticalCenterOffset: 4
                text: "Quầy thông tin tự phục vụ"
                color: Theme.faint
                font.family: Theme.font
                font.pixelSize: 29
                font.weight: Font.Medium
            }
            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 2
                color: Theme.line
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: 72
            Layout.rightMargin: 72
            spacing: 0

            Item { Layout.fillHeight: true }
            Text {
                text: "Xin chào"
                color: Theme.ink
                font.family: Theme.font
                font.pixelSize: 104
                font.weight: Font.ExtraBold
                font.letterSpacing: -2
            }
            Text {
                Layout.topMargin: 16
                Layout.bottomMargin: 68
                text: "Bạn muốn xem gì?"
                color: Theme.muted
                font.family: Theme.font
                font.pixelSize: 46
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 48

                MenuCard {
                    icon: Icons.screenInfo
                    title: "Thông tin bệnh viện"
                    description: "Giờ khám, nội quy, quy trình khám và sơ đồ khoa phòng — hiện lên các màn hình bên cạnh."
                    onTapped: root.client.touch("menu_option_info")
                }
                MenuCard {
                    icon: Icons.chatPlus
                    title: "Chat với Superdoc"
                    description: "Hỏi đáp với trợ lý ảo của bệnh viện về giờ khám, thủ tục, bảo hiểm y tế."
                    onTapped: root.client.touch("menu_option_chat")
                }
            }
            Item { Layout.fillHeight: true }
        }

        Row {
            Layout.alignment: Qt.AlignHCenter
            Layout.bottomMargin: 54
            spacing: 16
            Icon {
                anchors.verticalCenter: parent.verticalCenter
                path: Icons.hand
                size: 32
                strokeWidth: 1.6
                color: Theme.faint
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "Chạm vào ô bạn muốn chọn"
                color: Theme.faint
                font.family: Theme.font
                font.pixelSize: 30
                font.weight: Font.Medium
            }
        }
    }
}
