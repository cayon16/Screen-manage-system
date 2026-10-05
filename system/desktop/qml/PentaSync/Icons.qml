pragma Singleton
import QtQuick

// Đường vẽ biểu tượng (khung 24×24), chép từ bản thiết kế. <circle>/<rect> đã đổi sang path.
QtObject {
    readonly property string shield: "M12 3.5 4 7v6c0 4.6 3.3 7.6 8 8.5 4.7-.9 8-3.9 8-8.5V7l-8-3.5Z M12 9.2v5.6M9.2 12h5.6"
    readonly property string screenInfo: "M4.5 4h15a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-15a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2Z M12 17v3M8 20h8 M6.5 12.5 9.5 9l3 3 4.5-5"
    readonly property string chat: "M20.5 12.5c0 3.9-3.8 7-8.5 7-1 0-2-.15-2.9-.42L4 20.5l1.5-3.6C4.2 15.7 3.5 14.2 3.5 12.5c0-3.9 3.8-7 8.5-7s8.5 3.1 8.5 7Z"
    readonly property string chatPlus: chat + " M12 9.3v4.4M9.8 11.5h4.4"
    readonly property string chevronRight: "M9.5 6.5 15 12l-5.5 5.5"
    readonly property string chevronLeft: "M14.5 6.5 9 12l5.5 5.5"
    readonly property string chevronDown: "M6 9.5 12 15.5 18 9.5"
    readonly property string hand: "M9 11V6.2a1.7 1.7 0 0 1 3.4 0V11 M12.4 11V9.2a1.7 1.7 0 0 1 3.4 0V11 M15.8 11.4v-1a1.7 1.7 0 0 1 3.4 0v4.4c0 3.4-2.3 6.2-5.9 6.2-2.6 0-4-1-5.3-2.8l-2.6-4a1.7 1.7 0 0 1 2.7-2l1.5 1.8"
    readonly property string check: "M5 12.5 9.5 17 19 7.5"
    readonly property string send: "M4.5 12h15M13 5.5 19.5 12 13 18.5"
    readonly property string clock: "M20.5 12A8.5 8.5 0 1 1 3.5 12A8.5 8.5 0 1 1 20.5 12Z M12 7.2V12l3.2 2"
    readonly property string warning: "M12 4.2 2.8 19.5h18.4L12 4.2Z M12 10v4.2M12 16.8v.2"
    readonly property string power: "M12 4.5v7 M7.2 7.4a7 7 0 1 0 9.6 0"
    readonly property string screenOff: "M4.5 5h15a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-15a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2Z M6 8.5 18 15.5"
    readonly property string identify: "M4 9.5h5.5V4 M4.6 9.4A8 8 0 1 1 4 14"
    readonly property string reset: "M20 9.5h-5.5V4 M19.4 9.4A8 8 0 1 0 20 14"
}
