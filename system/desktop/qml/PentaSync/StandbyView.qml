import QtQuick
import QtMultimedia

// Video chờ: mỗi màn phát đúng phần của mình trong khung hình chung.
//  - Đã cắt lát sẵn: phát lát riêng (crop 0/1) → nhẹ máy.
//  - Chưa cắt xong: phát nguyên video, đẩy sang trái đúng vị trí → cùng hình, nặng hơn.
// Đồng bộ giữa các màn do StandbySync (Python) lo, theo đồng hồ chung của backend.
Item {
    id: root
    property var client
    property var sync
    readonly property var d: client ? client.data : ({})
    readonly property int cropCount: Math.max(1, d.crop_count || 1)
    readonly property int cropIndex: d.crop_index || 0
    readonly property string source: client ? client.mediaUrl(d.video_src || "/standby-video") : ""
    property string errorText: ""

    clip: true

    Rectangle {
        anchors.fill: parent
        color: "black"
    }

    VideoOutput {
        id: output
        x: -root.cropIndex * root.width
        width: root.width * root.cropCount
        height: root.height
        fillMode: VideoOutput.Stretch
    }

    MediaPlayer {
        id: player
        source: root.source
        videoOutput: output
        loops: MediaPlayer.Infinite
        onSourceChanged: {
            root.errorText = ""
            play()
        }
        onErrorOccurred: (error, errorString) => {
            root.errorText = errorString
        }
    }

    function attachSync() {
        if (root.sync)
            root.sync.attach(player, d.t0 || 0, d.server_now || 0, d.received_at || 0)
    }

    onDChanged: attachSync()
    Component.onCompleted: {
        player.play()
        attachSync()
    }
    Component.onDestruction: {
        if (root.sync)
            root.sync.detach()
        player.stop()
    }

    Text {
        visible: root.errorText !== ""
        anchors.centerIn: parent
        width: parent.width * 0.8
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.Wrap
        color: "white"
        font.family: Theme.font
        font.pixelSize: Math.max(16, parent.height * 0.03)
        text: "Không phát được video chờ (" + root.errorText + ").\nKiểm tra STANDBY_VIDEO_REL_PATH trong backend/app/config.py."
    }
}
