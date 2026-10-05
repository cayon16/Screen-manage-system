pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts

// Khung chat với Superdoc (màn 2 và màn 4).
// Bàn phím chỉ hiện khi chạm vào ô nhập, ẩn khi chạm ra ngoài / bấm "Ẩn" (như điện thoại).
// Không dùng ô nhập thật của Qt: 2 màn chat có thể được dùng cùng lúc mà Windows chỉ cho 1
// cửa sổ giữ bàn phím — nên chữ đang gõ được giữ ngay trong view này.
Stage {
    id: root
    property var client
    property var manager
    property int role

    property string draft: ""
    property bool keyboardOpen: false
    property string seenSession: ""

    readonly property bool waiting: client ? client.waitingForAi : false
    readonly property bool hasSession: client ? client.sessionId !== "" : false
    readonly property bool confirming: client ? client.state === "CHAT_CONFIRM_SWITCH" : false
    readonly property bool tier1: client ? client.tier1Visible : false
    readonly property int messageCount: list.count
    readonly property int maxDraft: 500
    readonly property var suggestions: [
        "Mấy giờ bệnh viện mở cửa?",
        "Khoa cấp cứu ở đâu?",
        "Thủ tục dùng bảo hiểm y tế",
        "Quy trình đăng ký khám"
    ]

    function syncSession() {
        if (client && client.sessionId !== seenSession) {
            seenSession = client.sessionId
            draft = ""
            keyboardOpen = false
        }
    }
    function typeKey(ch) {
        if (draft.length < maxDraft)
            draft = manager.telex.typeKey(draft, ch)
    }
    function send() {
        if (client.sendChat(draft))
            draft = ""
    }

    Component.onCompleted: syncSession()
    Connections {
        target: root.client
        function onChatChanged() { root.syncSession() }
    }
    onConfirmingChanged: if (confirming) keyboardOpen = false
    onTier1Changed: if (tier1) keyboardOpen = false

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ---------- đầu trang ----------
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: root.keyboardOpen ? 98 : 128

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 48
                anchors.rightMargin: 48
                spacing: 20

                IconTile {
                    icon: root.keyboardOpen ? Icons.chat : Icons.chatPlus
                    tileSize: root.keyboardOpen ? 56 : 70
                    iconSize: root.keyboardOpen ? 32 : 40
                }
                Column {
                    Layout.fillWidth: true
                    spacing: 3
                    Text {
                        text: "Superdoc"
                        color: Theme.ink
                        font.family: Theme.font
                        font.pixelSize: root.keyboardOpen ? 33 : 38
                        font.weight: Font.Bold
                    }
                    Text {
                        visible: !root.keyboardOpen
                        text: root.waiting ? "Đang soạn câu trả lời…" : "Trợ lý ảo bệnh viện"
                        color: root.waiting ? Theme.accent : Theme.faint
                        font.family: Theme.font
                        font.pixelSize: 25
                        font.weight: root.waiting ? Font.Medium : Font.Normal
                    }
                }
                AppButton {
                    visible: root.role === 2
                    text: "Xem thông tin bệnh viện"
                    fontSize: root.keyboardOpen ? 26 : 29
                    horizontalPadding: root.keyboardOpen ? 28 : 34
                    verticalPadding: root.keyboardOpen ? 14 : 20
                    radius: 16
                    onTapped: root.client.touch("menu_option_info")
                }
                AppButton {
                    text: "Kết thúc"
                    fontSize: root.keyboardOpen ? 26 : 29
                    horizontalPadding: root.keyboardOpen ? 28 : 34
                    verticalPadding: root.keyboardOpen ? 14 : 20
                    radius: 16
                    onTapped: root.client.touch("exit_chat")
                }
            }
            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 2
                color: Theme.line
            }
        }

        // ---------- nội dung hội thoại ----------
        Item {
            id: body
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            // Chạm vào vùng hội thoại = chạm ra ngoài ô nhập → ẩn bàn phím.
            TapHandler {
                onTapped: root.keyboardOpen = false
            }

            // Lời chào + câu hỏi gợi ý khi chưa hỏi gì.
            Column {
                visible: root.messageCount === 0 && !root.waiting
                anchors.centerIn: parent
                width: parent.width - 400
                spacing: 42

                IconTile {
                    visible: !root.keyboardOpen
                    anchors.horizontalCenter: parent.horizontalCenter
                    icon: Icons.chatPlus
                    tileSize: 152
                    iconSize: 84
                    iconStroke: 1.4
                }
                Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    text: "Xin chào, tôi là Superdoc.\nBạn cần hỏi gì về bệnh viện?"
                    lineHeight: 1.28
                    color: Theme.ink
                    font.family: Theme.font
                    font.pixelSize: root.keyboardOpen ? 42 : 54
                    font.weight: Font.Bold
                }
                Flow {
                    visible: !root.keyboardOpen
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: Math.min(parent.width, 1300)
                    spacing: 20
                    Repeater {
                        model: root.suggestions
                        Rectangle {
                            id: chip
                            required property string modelData
                            width: chipText.implicitWidth + 80
                            height: chipText.implicitHeight + 44
                            radius: height / 2
                            color: chipTap.pressed ? Theme.accentSoft : Theme.bg
                            border.width: 2
                            border.color: chipTap.pressed ? Theme.accent : Theme.lineStrong
                            opacity: root.hasSession ? 1 : 0.5
                            Text {
                                id: chipText
                                anchors.centerIn: parent
                                text: chip.modelData
                                color: Theme.ink2
                                font.family: Theme.font
                                font.pixelSize: 32
                                font.weight: Font.Medium
                            }
                            TapHandler {
                                id: chipTap
                                gesturePolicy: TapHandler.ReleaseWithinBounds
                                onTapped: root.client.sendChat(chip.modelData)
                            }
                        }
                    }
                }
            }

            ListView {
                id: list
                anchors.fill: parent
                anchors.leftMargin: 48
                anchors.rightMargin: 48
                topMargin: 36
                bottomMargin: 36
                spacing: 28
                model: root.client ? root.client.messages : null
                boundsBehavior: Flickable.StopAtBounds
                visible: count > 0 || root.waiting

                // Danh sách cuộn được nên "nuốt" chạm, bộ bắt chạm của vùng cha không nhận được —
                // phải bắt ngay tại đây để chạm vào tin nhắn cũng ẩn được bàn phím.
                TapHandler {
                    onTapped: root.keyboardOpen = false
                }

                delegate: ChatBubble {
                    required property var model
                    width: ListView.view.width
                    who: model.who
                    text: model.text
                }

                footer: Column {
                    width: ListView.view ? ListView.view.width : 0
                    topPadding: 28
                    spacing: 28
                    TypingDots {
                        visible: root.waiting
                    }
                    Rectangle {
                        visible: root.client && root.client.errorText !== ""
                        width: Math.min(errorText.implicitWidth, 1164) + 76
                        height: errorText.height + 44
                        radius: 22
                        color: Theme.dangerSurface
                        border.width: 2
                        border.color: Theme.dangerBorder
                        Text {
                            id: errorText
                            x: 38
                            y: 22
                            width: Math.min(implicitWidth, 1164)
                            wrapMode: Text.Wrap
                            textFormat: Text.PlainText
                            text: root.client ? root.client.errorText : ""
                            color: Theme.danger
                            font.family: Theme.font
                            font.pixelSize: 34
                            font.weight: Font.Medium
                        }
                    }
                }

                onContentHeightChanged: Qt.callLater(positionViewAtEnd)
                onHeightChanged: Qt.callLater(positionViewAtEnd)
            }
        }

        // ---------- ô nhập + bàn phím ----------
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: composer.implicitHeight + (root.keyboardOpen ? 46 : 68)
            color: root.keyboardOpen ? Theme.surface : Theme.bg

            Rectangle {
                width: parent.width
                height: 2
                color: Theme.line
            }

            ColumnLayout {
                id: composer
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.leftMargin: root.keyboardOpen ? 40 : 48
                anchors.rightMargin: root.keyboardOpen ? 40 : 48
                anchors.topMargin: root.keyboardOpen ? 20 : 30
                spacing: 16

                RowLayout {
                    Layout.fillWidth: true
                    spacing: root.keyboardOpen ? 18 : 22

                    Rectangle {
                        id: inputBox
                        readonly property bool usable: root.hasSession
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.keyboardOpen ? 94 : 102
                        radius: 22
                        color: root.keyboardOpen ? Theme.bg : (usable && !root.waiting ? Theme.surface : Theme.surfaceMuted)
                        border.width: root.keyboardOpen ? 4 : 3
                        border.color: root.keyboardOpen ? Theme.accent : (root.waiting ? Theme.lineSoft : Theme.lineStrong)

                        Row {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.leftMargin: 34
                            anchors.rightMargin: 34
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 4

                            Text {
                                id: inputText
                                anchors.verticalCenter: parent.verticalCenter
                                width: Math.min(implicitWidth, parent.width - 8)
                                elide: Text.ElideLeft
                                textFormat: Text.PlainText
                                text: root.draft !== "" ? root.draft
                                    : root.waiting ? "Đang chờ Superdoc trả lời…"
                                    : root.keyboardOpen ? ""
                                    : "Chạm vào đây để nhập câu hỏi…"
                                color: root.draft !== "" ? Theme.ink : root.waiting ? Theme.faint3 : Theme.faint2
                                font.family: Theme.font
                                font.pixelSize: 36
                            }
                            Rectangle {
                                id: caret
                                visible: root.keyboardOpen
                                anchors.verticalCenter: parent.verticalCenter
                                width: 3
                                height: 42
                                color: Theme.accent
                                SequentialAnimation on opacity {
                                    running: caret.visible
                                    loops: Animation.Infinite
                                    NumberAnimation { to: 0; duration: 80 }
                                    PauseAnimation { duration: 450 }
                                    NumberAnimation { to: 1; duration: 80 }
                                    PauseAnimation { duration: 450 }
                                }
                            }
                        }

                        TapHandler {
                            enabled: inputBox.usable
                            gesturePolicy: TapHandler.ReleaseWithinBounds
                            onTapped: root.keyboardOpen = true
                        }
                    }

                    AppButton {
                        Layout.preferredWidth: root.keyboardOpen ? 146 : 128
                        Layout.preferredHeight: root.keyboardOpen ? 94 : 102
                        variant: "primary"
                        icon: Icons.send
                        iconSize: root.keyboardOpen ? 38 : 42
                        iconStroke: 2.2
                        radius: 22
                        enabled: root.hasSession && !root.waiting && root.draft.trim() !== ""
                        onTapped: root.send()
                    }
                }

                RowLayout {
                    visible: root.keyboardOpen
                    Layout.fillWidth: true
                    Text {
                        Layout.fillWidth: true
                        text: "Gõ tiếng Việt kiểu Telex — aa → â, dd → đ, s f r x j → dấu"
                        color: Theme.faint
                        font.family: Theme.font
                        font.pixelSize: 23
                    }
                    Row {
                        spacing: 8
                        Icon {
                            anchors.verticalCenter: parent.verticalCenter
                            path: Icons.chevronDown
                            size: 24
                            strokeWidth: 2
                            color: Theme.faint
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Chạm ra ngoài để ẩn bàn phím"
                            color: Theme.faint
                            font.family: Theme.font
                            font.pixelSize: 23
                            font.weight: Font.Medium
                        }
                        TapHandler {
                            onTapped: root.keyboardOpen = false
                        }
                    }
                }

                OnScreenKeyboard {
                    visible: root.keyboardOpen
                    Layout.fillWidth: true
                    Layout.preferredHeight: visible ? 412 : 0
                    onTyped: ch => root.typeKey(ch)
                    onErase: root.draft = root.manager.telex.erase(root.draft)
                    onHide: root.keyboardOpen = false
                }
            }
        }
    }

    Tier1Dialog {
        anchors.fill: parent
        visible: root.tier1
        seconds: root.client ? root.client.tier1Seconds : 30
        serial: root.client ? root.client.tier1Serial : 0
        onAck: root.client.ackTier1()
    }

    ConfirmSwitchDialog {
        anchors.fill: parent
        visible: root.confirming
        onYes: root.client.touch("confirm_yes")
        onNo: root.client.touch("confirm_no")
    }
}
