import QtQuick
import QtQuick.Layouts

// Màn 2 đang chat mà bấm "Xem thông tin bệnh viện" → phải xác nhận vì chat sẽ bị xoá.
Rectangle {
    id: dlg
    signal yes()
    signal no()

    color: Theme.scrim

    // Chặn chạm xuống khung chat bên dưới; chạm ra ngoài không tự chọn gì.
    MouseArea {
        anchors.fill: parent
    }

    Rectangle {
        anchors.centerIn: parent
        width: 1160
        height: content.implicitHeight + 128
        radius: 34
        color: Theme.bg
        border.width: 3
        border.color: Theme.lineStrong

        ColumnLayout {
            id: content
            anchors.top: parent.top
            anchors.topMargin: 68
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: 76
            anchors.rightMargin: 76
            spacing: 38

            RowLayout {
                Layout.fillWidth: true
                spacing: 30
                Rectangle {
                    Layout.alignment: Qt.AlignTop
                    implicitWidth: 104
                    implicitHeight: 104
                    radius: 26
                    color: "#F1F3F5"
                    border.width: 2
                    border.color: Theme.lineSoft
                    Icon {
                        anchors.centerIn: parent
                        path: Icons.warning
                        size: 56
                        strokeWidth: 1.6
                        color: Theme.ink2
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 18
                    Text {
                        Layout.fillWidth: true
                        text: "Kết thúc đoạn chat để xem thông tin bệnh viện?"
                        wrapMode: Text.WordWrap
                        lineHeight: 1.2
                        color: Theme.ink
                        font.family: Theme.font
                        font.pixelSize: 56
                        font.weight: Font.ExtraBold
                    }
                    Text {
                        Layout.fillWidth: true
                        text: "Toàn bộ đoạn trò chuyện hiện tại sẽ bị xoá và không xem lại được trên màn hình này."
                        wrapMode: Text.WordWrap
                        lineHeight: 1.5
                        color: Theme.muted
                        font.family: Theme.font
                        font.pixelSize: 34
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 26
                AppButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    variant: "primary"
                    icon: Icons.check
                    iconStroke: 2.4
                    text: "Đồng ý, kết thúc"
                    fontSize: 40
                    fontWeight: Font.Bold
                    verticalPadding: 36
                    radius: 22
                    onTapped: dlg.yes()
                }
                AppButton {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    icon: Icons.chevronLeft
                    iconStroke: 2.4
                    text: "Huỷ, tiếp tục chat"
                    fontSize: 40
                    fontWeight: Font.Bold
                    verticalPadding: 36
                    radius: 22
                    onTapped: dlg.no()
                }
            }
        }
    }
}
