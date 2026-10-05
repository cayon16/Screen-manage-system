import QtQuick
import QtQuick.Layouts

// 1 phím của bàn phím trên màn. Nhận phím ngay lúc chạm xuống (gõ nhanh không bị sót),
// phím Xoá giữ lâu thì xoá liên tục.
Rectangle {
    id: key
    property string label
    property bool util: false
    property real weight: 1
    property bool autoRepeat: false
    property bool highlighted: false
    signal activated()

    Layout.fillWidth: true
    Layout.fillHeight: true
    Layout.preferredWidth: weight * 100
    radius: 14
    color: tap.pressed || highlighted ? Theme.accentSoft : util ? Theme.chip : Theme.bg
    border.width: 2
    border.color: tap.pressed || highlighted ? Theme.accent : Theme.lineStrong
    opacity: enabled ? 1 : 0.4

    Text {
        anchors.centerIn: parent
        text: key.label
        color: key.util ? Theme.ink2 : Theme.ink
        font.family: Theme.font
        font.pixelSize: key.util || key.label.length > 2 ? 28 : 40
        font.weight: key.label.length > 2 && !key.util ? Font.Medium : Font.DemiBold
    }

    TapHandler {
        id: tap
        enabled: key.enabled
        onPressedChanged: {
            if (pressed) {
                key.activated()
                if (key.autoRepeat)
                    repeat.start()
            } else {
                repeat.stop()
            }
        }
    }

    Timer {
        id: repeat
        interval: 450
        repeat: true
        onTriggered: {
            interval = 80
            key.activated()
        }
        onRunningChanged: if (!running) interval = 450
    }
}
