import QtQuick

// 1 lượt hội thoại. Câu hỏi của người dùng nằm bên phải (nền xanh nhạt), câu trả lời bên trái.
Item {
    id: root
    property string who
    property string text
    readonly property bool mine: who === "user"
    readonly property int maxTextWidth: mine ? 1024 : 1164

    implicitHeight: bubble.height

    Rectangle {
        id: bubble
        x: root.mine ? root.width - width : 0
        width: Math.min(label.implicitWidth, root.maxTextWidth) + 76
        // Giãn dòng của Qt cộng thêm khoảng trống DƯỚI mỗi dòng, kể cả dòng cuối — trừ phần đó
        // đi để lề trên và lề dưới bằng nhau.
        height: label.height - label.trailingGap + 52
        radius: 28
        topLeftRadius: 28
        topRightRadius: 28
        bottomLeftRadius: root.mine ? 28 : 6
        bottomRightRadius: root.mine ? 6 : 28
        color: root.mine ? Theme.accentSoft : Theme.surface
        border.width: 2
        border.color: root.mine ? Theme.accentBorder : Theme.lineSoft

        Text {
            id: label
            readonly property real trailingGap: lineCount > 0 ? height / lineCount * (1 - 1 / lineHeight) : 0
            x: 38
            y: 26
            width: Math.min(implicitWidth, root.maxTextWidth)
            text: root.text
            // Chữ của người dùng / AI luôn hiện nguyên văn — không hiểu nhầm "<b>" thành định dạng.
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            lineHeight: root.mine ? 1.4 : 1.5
            color: Theme.ink
            font.family: Theme.font
            font.pixelSize: 38
            font.weight: root.mine ? Font.Medium : Font.Normal
        }
    }
}
