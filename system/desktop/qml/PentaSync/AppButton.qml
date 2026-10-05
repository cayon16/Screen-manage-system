import QtQuick

// Nút chạm: "primary" (nền xanh), "secondary" (viền xám), "danger" (viền đỏ nhạt).
Rectangle {
    id: root
    property string text
    property string icon
    property string variant: "secondary"
    property int fontSize: 36
    property int fontWeight: Font.DemiBold
    property int iconSize: Math.round(fontSize * 1.05)
    property real iconStroke: 2
    property int horizontalPadding: 44
    property int verticalPadding: 30
    property int spacing: 16
    readonly property bool pressed: tap.pressed

    signal tapped()

    readonly property color foreground: !enabled ? Theme.disabled
        : variant === "primary" ? "white"
        : variant === "danger" ? Theme.danger
        : Theme.ink2

    implicitWidth: row.implicitWidth + horizontalPadding * 2
    implicitHeight: row.implicitHeight + verticalPadding * 2
    radius: 20
    color: {
        if (!enabled)
            return Theme.surfaceMuted
        if (variant === "primary")
            return tap.pressed ? Theme.accentPressed : Theme.accent
        if (variant === "danger")
            return tap.pressed ? Theme.dangerSoft : Theme.dangerSurface
        return tap.pressed ? Theme.chip : Theme.bg
    }
    border.width: variant === "primary" && enabled ? 0 : 3
    border.color: !enabled ? Theme.lineSoft : variant === "danger" ? Theme.dangerBorder : Theme.lineStrong

    Row {
        id: row
        anchors.centerIn: parent
        spacing: root.icon && root.text ? root.spacing : 0

        Icon {
            visible: root.icon !== ""
            anchors.verticalCenter: parent.verticalCenter
            path: root.icon
            size: root.iconSize
            strokeWidth: root.iconStroke
            color: root.foreground
        }
        Text {
            visible: root.text !== ""
            anchors.verticalCenter: parent.verticalCenter
            text: root.text
            color: root.foreground
            font.family: Theme.font
            font.pixelSize: root.fontSize
            font.weight: root.fontWeight
        }
    }

    TapHandler {
        id: tap
        enabled: root.enabled
        gesturePolicy: TapHandler.ReleaseWithinBounds
        onTapped: root.tapped()
    }
}
