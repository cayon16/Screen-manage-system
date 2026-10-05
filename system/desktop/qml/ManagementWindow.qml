pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import PentaSync

// Màn quản lý: có màn thứ 6 thì chiếm trọn màn chính; ít hơn thì mở dạng cửa sổ nổi bằng
// Ctrl+Shift+M. Chỉ đọc ảnh chụp trạng thái từ backend và gửi lệnh — không tự giữ trạng thái.
Window {
    id: win
    required property var admin
    required property var manager
    required property bool windowed

    flags: windowed ? (Qt.Window | Qt.WindowStaysOnTopHint) : (Qt.Window | Qt.FramelessWindowHint)
    color: Theme.surface
    title: "PentaSync — Bảng điều khiển"
    visible: false

    readonly property var snap: admin.snapshot
    readonly property var screens: snap.screens || []
    readonly property var slides: snap.slides || []
    readonly property var stats: snap.stats || ({})
    readonly property bool blackout: !!snap.blackout
    property real now: Date.now() / 1000
    // Hộp xác nhận đang mở: "" | "reset" | "quit"
    property string confirmAction: ""

    readonly property var viewLabels: ({
        "standby": "Video chờ",
        "blackout": "Màn đen",
        "menu": "Menu",
        "slide_control": "Bảng chọn slide",
        "prompt_chat": "Chờ người dùng",
        "slide": "Đang chiếu",
        "chat": "Đang chat"
    })

    Timer {
        interval: 1000
        repeat: true
        running: win.visible
        onTriggered: win.now = Date.now() / 1000
    }

    function displayOf(role) {
        const list = manager.displays || []
        for (let i = 0; i < list.length; i++)
            if (list[i].role === role)
                return list[i]
        return null
    }
    function duration(seconds) {
        seconds = Math.max(0, Math.floor(seconds))
        const h = Math.floor(seconds / 3600)
        const m = Math.floor(seconds % 3600 / 60)
        const s = seconds % 60
        if (h > 0)
            return h + " giờ " + m + " phút"
        if (m > 0)
            return m + " phút " + (s < 10 ? "0" : "") + s + " giây"
        return s + " giây"
    }
    function shortDuration(seconds) {
        if (seconds === null || seconds === undefined)
            return "—"
        seconds = Math.round(seconds)
        const m = Math.floor(seconds / 60)
        return m > 0 ? m + " ph " + (seconds % 60) + " s" : seconds + " s"
    }

    component SectionTitle: Text {
        color: Theme.faint2
        font.family: Theme.font
        font.pixelSize: 15
        font.weight: Font.Bold
        font.letterSpacing: 1.8
        font.capitalization: Font.AllUppercase
    }

    component ControlButton: Rectangle {
        id: control
        property string icon
        property color iconColor: Theme.accent
        property string title
        property string subtitle
        property bool danger: false
        signal tapped()

        Layout.fillWidth: true
        implicitHeight: 84
        radius: 14
        color: tap.pressed ? (danger ? Theme.dangerSoft : Theme.accentSoft) : (danger ? Theme.dangerSurface : Theme.bg)
        border.width: 2
        border.color: danger ? Theme.dangerBorder : (tap.pressed ? Theme.accent : Theme.lineStrong)
        opacity: enabled ? 1 : 0.45

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 20
            anchors.rightMargin: 20
            spacing: 16
            Icon {
                path: control.icon
                size: 32
                strokeWidth: 1.7
                color: control.danger ? Theme.danger : control.iconColor
            }
            Column {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    text: control.title
                    color: control.danger ? Theme.danger : Theme.ink
                    font.family: Theme.font
                    font.pixelSize: 21
                    font.weight: Font.Bold
                }
                Text {
                    text: control.subtitle
                    color: control.danger ? Theme.dangerText : Theme.faint2
                    font.family: Theme.font
                    font.pixelSize: 16
                }
            }
        }
        TapHandler {
            id: tap
            enabled: control.enabled
            gesturePolicy: TapHandler.ReleaseWithinBounds
            onTapped: control.tapped()
        }
    }

    Stage {
        Rectangle {
            anchors.fill: parent
            color: Theme.surface
        }

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            // ---------- đầu trang ----------
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 70
                color: Theme.bg
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 36
                    anchors.rightMargin: 36
                    spacing: 22
                    Icon { path: Icons.shield; size: 28 }
                    Text {
                        text: "PentaSync — Bảng điều khiển"
                        color: Theme.ink
                        font.family: Theme.font
                        font.pixelSize: 24
                        font.weight: Font.Bold
                    }
                    Item { Layout.fillWidth: true }
                    Row {
                        spacing: 8
                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            width: 10; height: 10; radius: 5
                            color: win.admin.connected ? Theme.accent : Theme.dangerStrong
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: win.admin.connected && win.snap.started_at
                                  ? "Máy chủ đang chạy · " + win.duration(win.now - win.snap.started_at)
                                  : "Đang kết nối máy chủ…"
                            color: win.admin.connected ? Theme.muted : Theme.danger
                            font.family: Theme.font
                            font.pixelSize: 17
                        }
                    }
                    Text {
                        text: win.manager.monitorCount + " màn · "
                              + (win.windowed ? "Ctrl+Shift+M để ẩn bảng này" : "màn chính = màn quản lý")
                        color: Theme.faint2
                        font.family: Theme.font
                        font.pixelSize: 17
                    }
                    AppButton {
                        text: "Thoát ứng dụng"
                        fontSize: 16
                        fontWeight: Font.DemiBold
                        horizontalPadding: 16
                        verticalPadding: 8
                        radius: 10
                        border.width: 2
                        onTapped: win.confirmAction = "quit"
                    }
                }
                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 2
                    color: Theme.line
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.leftMargin: 36
                Layout.rightMargin: 36
                Layout.topMargin: 22
                Layout.bottomMargin: 26
                spacing: 20

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 18

                    // ---------- trạng thái màn ----------
                    SectionTitle {
                        text: "Trạng thái màn hiển thị"
                            + (win.manager.unusedCount > 0 ? " · " + win.manager.unusedCount + " màn thừa không dùng" : "")
                    }
                    Text {
                        visible: win.manager.touchWarning !== ""
                        Layout.fillWidth: true
                        Layout.topMargin: -8
                        wrapMode: Text.WordWrap
                        text: "Cảm ứng: " + win.manager.touchWarning
                        color: Theme.danger
                        font.family: Theme.font
                        font.pixelSize: 16
                        font.weight: Font.DemiBold
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 13
                        Repeater {
                            model: win.screens
                            Rectangle {
                                id: card
                                required property var modelData
                                readonly property var s: modelData
                                readonly property var display: win.displayOf(s.role)
                                readonly property bool lost: s.active && !s.connected
                                readonly property bool touch: display ? display.touch : false
                                Layout.fillWidth: true
                                Layout.preferredWidth: 1
                                implicitHeight: cardColumn.implicitHeight + 32
                                radius: 14
                                color: Theme.bg
                                opacity: s.active ? 1 : 0.55
                                border.width: 2
                                border.color: lost ? Theme.dangerStrong
                                              : (s.active && (s.role === 2 || s.role === 4)) ? Theme.accent
                                              : Theme.lineSoft

                                ColumnLayout {
                                    id: cardColumn
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.top: parent.top
                                    anchors.margins: 16
                                    spacing: 10

                                    RowLayout {
                                        Layout.fillWidth: true
                                        Text {
                                            Layout.fillWidth: true
                                            text: "Màn " + card.s.role
                                            color: Theme.ink
                                            font.family: Theme.font
                                            font.pixelSize: 22
                                            font.weight: Font.ExtraBold
                                        }
                                        Rectangle {
                                            implicitWidth: pill.implicitWidth + 20
                                            implicitHeight: pill.implicitHeight + 8
                                            radius: height / 2
                                            border.width: 1
                                            border.color: card.lost ? Theme.dangerBorder : card.s.active ? Theme.accentBorder : Theme.lineSoft
                                            color: card.lost ? Theme.dangerSoft : card.s.active ? Theme.accentSoft : Theme.surface
                                            Text {
                                                id: pill
                                                anchors.centerIn: parent
                                                text: !card.s.active ? "Không có màn"
                                                      : card.lost ? "Mất kết nối"
                                                      : (win.viewLabels[card.s.view] || card.s.view)
                                                color: card.lost ? Theme.danger : card.s.active ? Theme.accent : Theme.faint2
                                                font.family: Theme.font
                                                font.pixelSize: 14
                                                font.weight: Font.DemiBold
                                            }
                                        }
                                    }

                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 90
                                        radius: 9
                                        color: card.lost ? "#F7F1F0" : "#F0F3F6"
                                        border.width: 1
                                        border.color: card.lost ? "#EEDCDA" : Theme.line
                                        Column {
                                            anchors.centerIn: parent
                                            width: parent.width - 16
                                            spacing: 3
                                            Text {
                                                width: parent.width
                                                horizontalAlignment: Text.AlignHCenter
                                                wrapMode: Text.WordWrap
                                                maximumLineCount: 2
                                                elide: Text.ElideRight
                                                text: {
                                                    const s = card.s
                                                    if (!s.active) return "Không cắm / không dùng"
                                                    if (card.lost) return "Không có tín hiệu"
                                                    if (s.view === "chat") return "Có người đang trò chuyện"
                                                    if (s.view === "slide") return s.slide_title || "Slide"
                                                    if (s.view === "menu") return "Menu 2 lựa chọn"
                                                    return win.viewLabels[s.view] || s.view
                                                }
                                                color: card.lost ? Theme.danger : Theme.muted
                                                font.family: Theme.font
                                                font.pixelSize: 15
                                            }
                                            Text {
                                                visible: card.s.chat_open && !!card.s.chat_started_at
                                                width: parent.width
                                                horizontalAlignment: Text.AlignHCenter
                                                text: card.s.chat_started_at ? win.duration(win.now - card.s.chat_started_at) : ""
                                                color: Theme.faint2
                                                font.family: Theme.font
                                                font.pixelSize: 15
                                            }
                                        }
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        elide: Text.ElideRight
                                        text: card.display
                                              ? card.display.width + "×" + card.display.height + " · " + (card.touch ? "CẢM ỨNG" : "không cảm ứng")
                                              : "—"
                                        color: card.touch ? Theme.accent : Theme.faint2
                                        font.family: Theme.font
                                        font.pixelSize: 15
                                        font.weight: card.touch ? Font.DemiBold : Font.Normal
                                    }
                                    Text {
                                        visible: !!(card.display && card.display.gpu)
                                        Layout.fillWidth: true
                                        Layout.topMargin: -6
                                        elide: Text.ElideRight
                                        text: card.display ? card.display.gpu : ""
                                        color: Theme.faint2
                                        font.family: Theme.font
                                        font.pixelSize: 13
                                    }
                                }
                            }
                        }
                    }

                    // ---------- đổi slide ----------
                    SectionTitle {
                        Layout.topMargin: 8
                        text: "Đổi nội dung đang chiếu" + (win.blackout ? " · đang tắt màn hình" : "")
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: 13
                        enabled: !win.blackout && win.admin.connected
                        opacity: enabled ? 1 : 0.5

                        Text {
                            visible: win.slides.length === 0
                            Layout.fillWidth: true
                            text: "Không có màn trình chiếu nào (màn 1, 3, 5) đang hoạt động."
                            color: Theme.faint2
                            font.family: Theme.font
                            font.pixelSize: 19
                        }

                        Repeater {
                            model: {
                                const ids = []
                                for (const b of win.slides)
                                    if (ids.indexOf(b.screen_id) < 0)
                                        ids.push(b.screen_id)
                                return ids
                            }
                            ColumnLayout {
                                id: slideColumn
                                required property int modelData
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                Layout.preferredWidth: 1
                                spacing: 9
                                Text {
                                    text: "Màn " + slideColumn.modelData
                                    color: Theme.muted
                                    font.family: Theme.font
                                    font.pixelSize: 17
                                    font.weight: Font.DemiBold
                                }
                                Repeater {
                                    model: win.slides.filter(b => b.screen_id === slideColumn.modelData)
                                    Rectangle {
                                        id: slideButton
                                        required property var modelData
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        Layout.preferredHeight: 1
                                        radius: 13
                                        color: modelData.current || slideTap.pressed ? Theme.accentSoft : Theme.bg
                                        border.width: modelData.current ? 3 : 2
                                        border.color: modelData.current || slideTap.pressed ? Theme.accent : Theme.lineStrong
                                        Text {
                                            anchors.fill: parent
                                            anchors.margins: 17
                                            verticalAlignment: Text.AlignVCenter
                                            wrapMode: Text.WordWrap
                                            elide: Text.ElideRight
                                            text: slideButton.modelData.title
                                            color: slideButton.modelData.current ? Theme.ink : Theme.ink2
                                            font.family: Theme.font
                                            font.pixelSize: 22
                                            font.weight: slideButton.modelData.current ? Font.Bold : Font.Medium
                                        }
                                        TapHandler {
                                            id: slideTap
                                            gesturePolicy: TapHandler.ReleaseWithinBounds
                                            onTapped: win.admin.selectSlide(slideButton.modelData.slide_id)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // ---------- điều khiển ----------
                ColumnLayout {
                    Layout.preferredWidth: 400
                    Layout.minimumWidth: 400
                    Layout.maximumWidth: 400
                    Layout.fillHeight: true
                    spacing: 13

                    SectionTitle { text: "Điều khiển" }

                    ControlButton {
                        icon: Icons.power
                        title: "Đưa về video chờ"
                        subtitle: "Các màn quay lại video chờ"
                        enabled: win.admin.connected && !win.blackout
                        onTapped: win.admin.command("force_standby")
                    }
                    ControlButton {
                        icon: Icons.screenOff
                        iconColor: Theme.ink2
                        title: win.blackout ? "Bật lại màn hình" : "Tắt hẳn màn hình"
                        subtitle: win.blackout ? "Các màn về video chờ, nhận chạm lại" : "Màn đen, bỏ qua mọi thao tác chạm"
                        enabled: win.admin.connected
                        onTapped: win.admin.command(win.blackout ? "blackout_off" : "blackout_on")
                    }
                    ControlButton {
                        icon: Icons.identify
                        title: "Nhận diện màn"
                        subtitle: "Hiện số màn to lên " + win.manager.identifySeconds + " giây"
                        onTapped: win.manager.identify()
                    }
                    ControlButton {
                        danger: true
                        icon: Icons.reset
                        title: "Reset hệ thống"
                        subtitle: "Kết thúc mọi đoạn chat, tải lại các màn"
                        enabled: win.admin.connected
                        onTapped: win.confirmAction = "reset"
                    }

                    Item { Layout.fillHeight: true }

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: statsColumn.implicitHeight + 36
                        radius: 16
                        color: Theme.bg
                        border.width: 2
                        border.color: Theme.lineSoft
                        ColumnLayout {
                            id: statsColumn
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: 18
                            spacing: 9
                            SectionTitle { text: "Hôm nay" }
                            Repeater {
                                model: [
                                    { label: "Lượt trò chuyện", value: String(win.stats.chats_today ?? "—"), danger: false },
                                    { label: "Thời gian trung bình", value: win.shortDuration(win.stats.avg_chat_seconds), danger: false },
                                    { label: "Lỗi kết nối AI", value: String(win.stats.ai_errors_today ?? "—"), danger: (win.stats.ai_errors_today || 0) > 0 }
                                ]
                                RowLayout {
                                    id: statRow
                                    required property var modelData
                                    Layout.fillWidth: true
                                    Text {
                                        Layout.fillWidth: true
                                        text: statRow.modelData.label
                                        color: Theme.muted
                                        font.family: Theme.font
                                        font.pixelSize: 19
                                    }
                                    Text {
                                        text: statRow.modelData.value
                                        color: statRow.modelData.danger ? Theme.danger : Theme.ink
                                        font.family: Theme.font
                                        font.pixelSize: 19
                                        font.weight: Font.Bold
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // ---------- hộp xác nhận (reset / thoát) ----------
        Rectangle {
            anchors.fill: parent
            visible: win.confirmAction !== ""
            color: Theme.scrim
            MouseArea {
                anchors.fill: parent
                onClicked: win.confirmAction = ""
            }
            Rectangle {
                anchors.centerIn: parent
                width: 720
                height: resetColumn.implicitHeight + 72
                radius: 24
                color: Theme.bg
                border.width: 2
                border.color: Theme.lineStrong
                MouseArea { anchors.fill: parent }
                ColumnLayout {
                    id: resetColumn
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 36
                    spacing: 18
                    Text {
                        Layout.fillWidth: true
                        text: win.confirmAction === "quit" ? "Thoát PentaSync?" : "Reset toàn bộ hệ thống?"
                        color: Theme.ink
                        font.family: Theme.font
                        font.pixelSize: 34
                        font.weight: Font.ExtraBold
                    }
                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        text: win.confirmAction === "quit"
                              ? "Mọi màn hiển thị sẽ tắt và các đoạn chat đang mở kết thúc. Mở lại bằng PentaSync.exe."
                              : "Mọi đoạn chat đang mở sẽ kết thúc, slide trở về mặc định, màn đen (nếu có) được bật lại và các màn hiển thị được mở lại từ đầu."
                        lineHeight: 1.4
                        color: Theme.muted
                        font.family: Theme.font
                        font.pixelSize: 21
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: 8
                        spacing: 14
                        AppButton {
                            Layout.fillWidth: true
                            variant: "danger"
                            text: win.confirmAction === "quit" ? "Thoát" : "Reset ngay"
                            fontSize: 22
                            verticalPadding: 18
                            radius: 14
                            onTapped: {
                                const action = win.confirmAction
                                win.confirmAction = ""
                                if (action === "quit")
                                    win.manager.quit()
                                else
                                    win.manager.resetSystem()
                            }
                        }
                        AppButton {
                            Layout.fillWidth: true
                            text: "Huỷ"
                            fontSize: 22
                            verticalPadding: 18
                            radius: 14
                            onTapped: win.confirmAction = ""
                        }
                    }
                }
            }
        }
    }

    IdentifyOverlay {
        anchors.fill: parent
        visible: win.manager.identifying && !win.windowed
        info: ({})
        title: "Màn này là"
        bigText: "QL"
        subtitle: "Màn quản lý"
        seconds: win.manager.identifySeconds
    }

    Shortcut {
        sequence: "Ctrl+Shift+M"
        onActivated: win.manager.toggleManagement()
    }
    Shortcut {
        sequence: "Ctrl+Shift+I"
        onActivated: win.manager.identify()
    }
    Shortcut {
        sequence: "Ctrl+Shift+Q"
        onActivated: win.manager.quit()
    }
}
