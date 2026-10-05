pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Window
import PentaSync

// 1 cửa sổ toàn màn hình cho 1 màn hiển thị. Python (window_manager.py) gắn nó vào đúng QScreen.
Window {
    id: win
    required property var client
    required property var sync
    required property var manager
    required property int role
    property var info: ({})

    // Không bao giờ nhận kích hoạt: chạm vào 1 màn mà kích hoạt nó thì màn đang được chạm khác
    // bị mất kích hoạt và Qt huỷ thao tác chạm dở ở đó (2 người dùng màn 2 và 4 cùng lúc sẽ mất
    // chạm / mất phím). Màn hiển thị không cần bàn phím — phím tắt là phím tắt toàn cục.
    flags: Qt.Window | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus
    color: "white"
    title: "PentaSync — Màn " + role
    visible: false

    readonly property string viewName: client.connected ? client.view : "connecting"
    property bool pointerIdle: false

    Loader {
        id: viewLoader
        anchors.fill: parent
        sourceComponent: {
            switch (win.viewName) {
            case "standby": return standbyView
            case "blackout": return blackoutView
            case "menu": return menuView
            case "slide_control": return slideControlView
            case "prompt_chat": return promptChatView
            case "slide": return slideView
            case "chat": return chatView
            default: return connectingView
            }
        }
    }

    Component {
        id: connectingView
        ConnectingView { role: win.role; roleName: win.info.role_name || "" }
    }
    Component {
        id: standbyView
        StandbyView { client: win.client; sync: win.sync }
    }
    Component {
        id: blackoutView
        BlackoutView {}
    }
    Component {
        id: menuView
        MenuView { client: win.client; hospitalName: win.manager.hospitalName }
    }
    Component {
        id: slideControlView
        SlideControlView { client: win.client }
    }
    Component {
        id: promptChatView
        PromptChatView { hospitalName: win.manager.hospitalName }
    }
    Component {
        id: slideView
        SlideView { client: win.client; hospitalName: win.manager.hospitalName }
    }
    Component {
        id: chatView
        ChatView { client: win.client; manager: win.manager; role: win.role }
    }

    IdentifyOverlay {
        anchors.fill: parent
        visible: win.manager.identifying
        info: win.info
        seconds: win.manager.identifySeconds
    }

    // Con trỏ chuột nằm yên trên màn hiển thị 3 giây thì ẩn đi (không chặn chạm hay bấm).
    HoverHandler {
        cursorShape: win.pointerIdle ? Qt.BlankCursor : Qt.ArrowCursor
        onPointChanged: {
            win.pointerIdle = false
            idleTimer.restart()
        }
    }
    Timer {
        id: idleTimer
        interval: 3000
        running: true
        onTriggered: win.pointerIdle = true
    }
}
