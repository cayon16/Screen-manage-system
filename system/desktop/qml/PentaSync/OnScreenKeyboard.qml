pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts

// Bàn phím QWERTY trên màn (gõ Telex). Chỉ phát tín hiệu, không tự sửa chữ.
ColumnLayout {
    id: kb
    signal typed(string ch)
    signal erase()
    signal hide()

    property bool shift: false
    property bool numbers: false

    readonly property var letterRows: [
        ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
        ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
        ["z", "x", "c", "v", "b", "n", "m"]
    ]
    readonly property var numberRows: [
        ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
        ["-", "/", ":", ";", "(", ")", "&", "@", "\""],
        [",", "?", "!", "'", "%", "+", "="]
    ]
    readonly property var rows: numbers ? numberRows : letterRows

    function press(ch) {
        if (!numbers && shift) {
            kb.typed(ch.toUpperCase())
            shift = false
        } else {
            kb.typed(ch)
        }
    }

    spacing: 12

    RowLayout {
        Layout.fillWidth: true
        Layout.preferredHeight: 94
        spacing: 12
        Repeater {
            model: kb.rows[0]
            KeyButton {
                required property string modelData
                label: kb.shift && !kb.numbers ? modelData.toUpperCase() : modelData
                onActivated: kb.press(modelData)
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.preferredHeight: 94
        Layout.leftMargin: 52
        Layout.rightMargin: 52
        spacing: 12
        Repeater {
            model: kb.rows[1]
            KeyButton {
                required property string modelData
                label: kb.shift && !kb.numbers ? modelData.toUpperCase() : modelData
                onActivated: kb.press(modelData)
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.preferredHeight: 94
        spacing: 12
        KeyButton {
            util: true
            weight: 1.6
            label: "Hoa"
            enabled: !kb.numbers
            highlighted: kb.shift && !kb.numbers
            onActivated: kb.shift = !kb.shift
        }
        Repeater {
            model: kb.rows[2]
            KeyButton {
                required property string modelData
                label: kb.shift && !kb.numbers ? modelData.toUpperCase() : modelData
                onActivated: kb.press(modelData)
            }
        }
        KeyButton {
            util: true
            weight: 1.6
            label: "Xoá"
            autoRepeat: true
            onActivated: kb.erase()
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.preferredHeight: 94
        spacing: 12
        KeyButton {
            util: true
            weight: 1.6
            label: kb.numbers ? "ABC" : "123"
            onActivated: {
                kb.numbers = !kb.numbers
                kb.shift = false
            }
        }
        KeyButton {
            weight: 6
            label: "dấu cách"
            onActivated: kb.typed(" ")
        }
        KeyButton {
            label: "."
            onActivated: kb.typed(".")
        }
        KeyButton {
            util: true
            weight: 1.6
            label: "Ẩn"
            onActivated: kb.hide()
        }
    }
}
