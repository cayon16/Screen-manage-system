pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts

// Màn 2 — bảng chọn slide cho các màn trình chiếu đang có.
Stage {
    id: root
    property var client
    readonly property var buttons: client && client.data.buttons ? client.data.buttons : []
    readonly property var screenIds: {
        const ids = []
        for (const b of buttons)
            if (ids.indexOf(b.screen_id) < 0)
                ids.push(b.screen_id)
        return ids
    }

    function columnTitle(screenId) {
        if (screenIds.length === 1)
            return "Màn trình chiếu"
        const pos = screenIds.indexOf(screenId)
        if (pos === 0)
            return "Màn bên trái"
        if (pos === screenIds.length - 1)
            return "Màn bên phải"
        return "Màn giữa"
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 64
        anchors.rightMargin: 64
        anchors.topMargin: 44
        anchors.bottomMargin: 40
        spacing: 36

        RowLayout {
            Layout.fillWidth: true
            spacing: 24

            Column {
                Layout.fillWidth: true
                spacing: 10
                Text {
                    text: "Thông tin bệnh viện"
                    color: Theme.ink
                    font.family: Theme.font
                    font.pixelSize: 60
                    font.weight: Font.ExtraBold
                }
                Text {
                    text: "Chạm vào nội dung bạn muốn xem — nội dung hiện lên màn hình tương ứng"
                    color: Theme.muted
                    font.family: Theme.font
                    font.pixelSize: 30
                }
            }
            Rectangle {
                Layout.alignment: Qt.AlignBottom
                implicitWidth: pillRow.implicitWidth + 48
                implicitHeight: 58
                radius: height / 2
                border.width: 2
                border.color: Theme.lineSoft
                Row {
                    id: pillRow
                    anchors.centerIn: parent
                    spacing: 12
                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 12; height: 12; radius: 6
                        color: Theme.accent
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: root.screenIds.length + " màn đang chiếu"
                        color: Theme.muted
                        font.family: Theme.font
                        font.pixelSize: 25
                        font.weight: Font.Medium
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 34

            Text {
                visible: root.screenIds.length === 0
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                text: "Hiện không có màn trình chiếu nào đang hoạt động."
                color: Theme.faint
                font.family: Theme.font
                font.pixelSize: 40
            }

            Repeater {
                model: root.screenIds

                ColumnLayout {
                    id: column
                    required property int modelData
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 1
                    spacing: 20

                    Row {
                        leftPadding: 4
                        spacing: 14
                        Rectangle {
                            width: 42; height: 42; radius: 11
                            color: Theme.chip
                            Text {
                                anchors.centerIn: parent
                                text: column.modelData
                                color: Theme.muted
                                font.family: Theme.font
                                font.pixelSize: 23
                                font.weight: Font.Bold
                            }
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: root.columnTitle(column.modelData)
                            color: Theme.faint
                            font.family: Theme.font
                            font.pixelSize: 25
                            font.weight: Font.DemiBold
                            font.letterSpacing: 2.5
                            font.capitalization: Font.AllUppercase
                        }
                    }

                    Repeater {
                        model: root.buttons.filter(b => b.screen_id === column.modelData)

                        Rectangle {
                            id: slideCard
                            required property var modelData
                            readonly property bool current: modelData.current
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.preferredHeight: 1
                            radius: 22
                            color: current || tap.pressed ? Theme.accentSoft : Theme.bg
                            border.width: current ? 4 : 3
                            border.color: current || tap.pressed ? Theme.accent : Theme.lineStrong

                            Text {
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.margins: 38
                                text: slideCard.modelData.title
                                wrapMode: Text.WordWrap
                                lineHeight: 1.2
                                color: slideCard.current ? Theme.ink : Theme.ink2
                                font.family: Theme.font
                                font.pixelSize: 44
                                font.weight: slideCard.current ? Font.Bold : Font.DemiBold
                            }
                            Row {
                                visible: slideCard.current
                                anchors.left: parent.left
                                anchors.bottom: parent.bottom
                                anchors.margins: 38
                                spacing: 10
                                Icon {
                                    anchors.verticalCenter: parent.verticalCenter
                                    path: Icons.check
                                    size: 28
                                    strokeWidth: 2.4
                                    color: Theme.accent
                                }
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: "Đang chiếu"
                                    color: Theme.accent
                                    font.family: Theme.font
                                    font.pixelSize: 26
                                    font.weight: Font.Bold
                                }
                            }
                            TapHandler {
                                id: tap
                                gesturePolicy: TapHandler.ReleaseWithinBounds
                                onTapped: root.client.selectSlide(slideCard.modelData.slide_id)
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 26
            AppButton {
                Layout.fillWidth: true
                variant: "primary"
                icon: Icons.chat
                iconStroke: 1.8
                text: "Chat với Superdoc"
                fontSize: 38
                fontWeight: Font.Bold
                onTapped: root.client.touch("menu_option_chat")
            }
            AppButton {
                Layout.preferredWidth: 460
                icon: Icons.chevronLeft
                text: "Quay lại"
                onTapped: root.client.touch("menu_back")
            }
        }
    }
}
