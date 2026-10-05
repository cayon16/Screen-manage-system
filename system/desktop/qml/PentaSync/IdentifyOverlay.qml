pragma ComponentBehavior: Bound
import QtQuick

// Lớp "Nhận diện màn": viền xanh ôm sát 4 mép + số màn thật to, để kiểm tra căn chỉnh và gán
// cảm ứng ngay tại chỗ. Viền bị cắt hoặc lệch = cửa sổ chưa khớp màn (hoặc TV đang overscan).
Item {
    id: root
    property var info: ({})
    property string title: "Màn số"
    property string bigText: info.role !== undefined ? String(info.role) : "?"
    property string subtitle: info.role_name || ""
    property int seconds: 10

    // Đang nhận diện thì chạm không được lọt xuống giao diện bên dưới.
    MouseArea {
        anchors.fill: parent
    }

    Stage {
        Column {
            anchors.centerIn: parent
            anchors.verticalCenterOffset: -30
            spacing: 22

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: root.title
                color: Theme.accent
                font.family: Theme.font
                font.pixelSize: 42
                font.weight: Font.DemiBold
                font.letterSpacing: 9
                font.capitalization: Font.AllUppercase
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: root.bigText
                color: Theme.ink
                font.family: Theme.font
                font.pixelSize: 400
                font.weight: Font.ExtraBold
                lineHeight: 0.86
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: root.subtitle
                color: Theme.ink2
                font.family: Theme.font
                font.pixelSize: 50
                font.weight: Font.Bold
            }

            Row {
                visible: root.info.device !== undefined
                anchors.horizontalCenter: parent.horizontalCenter
                topPadding: 24
                spacing: 18

                Repeater {
                    model: [
                        { label: "Độ phân giải", value: (root.info.width || "?") + " × " + (root.info.height || "?"), strong: false },
                        { label: "Tỉ lệ hiển thị", value: (root.info.scale || "?") + "%", strong: false },
                        { label: "Cảm ứng", value: root.info.touch ? "Có" : "Không", strong: !!root.info.touch },
                        { label: "Thiết bị", value: root.info.device || "?", strong: false },
                        { label: "Card đồ hoạ", value: root.info.gpu || "?", strong: false }
                    ]
                    Rectangle {
                        id: fact
                        required property var modelData
                        width: cell.implicitWidth + 64
                        height: cell.implicitHeight + 36
                        radius: 16
                        color: fact.modelData.strong ? Theme.accentSoft : Theme.bg
                        border.width: fact.modelData.strong ? 3 : 2
                        border.color: fact.modelData.strong ? Theme.accent : Theme.lineStrong
                        Column {
                            id: cell
                            anchors.centerIn: parent
                            spacing: 3
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: fact.modelData.label
                                color: fact.modelData.strong ? Theme.accent : Theme.faint2
                                font.family: Theme.font
                                font.pixelSize: 19
                                font.weight: Font.DemiBold
                                font.letterSpacing: 1.9
                                font.capitalization: Font.AllUppercase
                            }
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: fact.modelData.value
                                color: fact.modelData.strong ? Theme.accent : Theme.ink
                                font.family: Theme.font
                                font.pixelSize: 33
                                font.weight: Font.Bold
                            }
                        }
                    }
                }
            }
        }

        Column {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 56
            spacing: 8
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Viền xanh phải ôm sát 4 mép màn hình — nếu bị cắt hoặc lệch là cửa sổ chưa khớp màn"
                color: Theme.muted
                font.family: Theme.font
                font.pixelSize: 28
                font.weight: Font.Medium
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Tự tắt sau " + root.seconds + " giây"
                color: Theme.faint2
                font.family: Theme.font
                font.pixelSize: 24
            }
        }
    }

    // Viền và góc vẽ SAU (nằm trên) khung nội dung, theo pixel thật của cửa sổ (không co giãn)
    // để thấy rõ từng mép.
    Rectangle {
        anchors.fill: parent
        color: "transparent"
        border.width: 14
        border.color: Theme.accent
    }
    Repeater {
        model: [
            { ax: 0, ay: 0 }, { ax: 1, ay: 0 }, { ax: 0, ay: 1 }, { ax: 1, ay: 1 }
        ]
        Item {
            id: corner
            required property var modelData
            x: corner.modelData.ax ? root.width - 14 - width : 14
            y: corner.modelData.ay ? root.height - 14 - height : 14
            width: 120
            height: 120
            Rectangle { x: 0; y: corner.modelData.ay ? corner.height - 6 : 0; width: corner.width; height: 6; color: Theme.ink }
            Rectangle { x: corner.modelData.ax ? corner.width - 6 : 0; y: 0; width: 6; height: corner.height; color: Theme.ink }
        }
    }
}
