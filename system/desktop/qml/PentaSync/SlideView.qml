pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtMultimedia

// Màn 1/3/5 — slide chữ (theo bản thiết kế), hoặc ảnh/video lấp cả màn.
Item {
    id: root
    property var client
    property string hospitalName
    readonly property var slide: client ? client.data.slide : undefined
    readonly property string kind: slide ? slide.kind : ""
    readonly property string mediaSource: slide && slide.src ? client.mediaUrl(slide.src) : ""
    property string videoError: ""
    onMediaSourceChanged: videoError = ""

    // ---------- slide chữ ----------
    Stage {
        visible: root.kind === "text" || root.kind === ""

        Text {
            visible: !root.slide
            anchors.centerIn: parent
            text: "Chưa có nội dung cho màn này trong content_manifest/slides.json"
            color: Theme.faint
            font.family: Theme.font
            font.pixelSize: 40
        }

        ColumnLayout {
            visible: !!root.slide
            anchors.fill: parent
            anchors.leftMargin: 104
            anchors.rightMargin: 104
            anchors.topMargin: 80
            anchors.bottomMargin: 64
            spacing: 0

            Row {
                spacing: 20
                Layout.bottomMargin: 44
                Rectangle {
                    width: 10; height: 58; radius: 5
                    color: Theme.accent
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.slide ? root.slide.title : ""
                    color: Theme.muted
                    font.family: Theme.font
                    font.pixelSize: 32
                    font.weight: Font.DemiBold
                    font.letterSpacing: 4.5
                    font.capitalization: Font.AllUppercase
                }
            }

            Text {
                Layout.fillWidth: true
                text: root.slide ? (root.slide.subtitle || "") : ""
                visible: text !== ""
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
                lineHeight: 1.08
                color: Theme.ink
                font.family: Theme.font
                font.pixelSize: 104
                font.weight: Font.ExtraBold
                font.letterSpacing: -2
            }

            // Danh sách căn giữa vùng còn lại; nội dung dài hơn chỗ trống thì thu nhỏ cả khối
            // cho vừa, không bao giờ tràn mất chân trang.
            Item {
                id: listArea
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.topMargin: 20
                Layout.bottomMargin: 36

                Column {
                    id: bullets
                    width: listArea.width
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 28
                    scale: height > 0 ? Math.min(1, listArea.height / height) : 1
                    transformOrigin: Item.Left

                    Repeater {
                        model: root.slide ? (root.slide.bullets || []) : []
                        Row {
                            id: bullet
                            required property string modelData
                            required property int index
                            width: bullets.width
                            spacing: 32
                            Rectangle {
                                id: badge
                                width: 82; height: 82; radius: 22
                                color: Theme.accentSoft
                                Text {
                                    anchors.centerIn: parent
                                    text: bullet.index + 1
                                    color: Theme.accent
                                    font.family: Theme.font
                                    font.pixelSize: 42
                                    font.weight: Font.ExtraBold
                                }
                            }
                            Text {
                                width: bullet.width - badge.width - bullet.spacing
                                // 1 dòng thì căn giữa với ô số; nhiều dòng thì bắt đầu ngang mép trên.
                                y: lineCount > 1 ? 0 : (badge.height - height) / 2
                                text: bullet.modelData
                                wrapMode: Text.WordWrap
                                lineHeight: 1.3
                                color: Theme.ink
                                font.family: Theme.font
                                font.pixelSize: 50
                                font.weight: Font.Medium
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 2
                color: Theme.line
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 40
                HospitalMark {
                    name: root.hospitalName
                    iconSize: 36
                    iconColor: Theme.muted
                    fontSize: 29
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: "Cần hỗ trợ? Chạm vào màn hình có chữ Superdoc"
                    color: Theme.faint2
                    font.family: Theme.font
                    font.pixelSize: 28
                }
            }
        }
    }

    // ---------- slide ảnh / video ----------
    Rectangle {
        visible: root.kind === "image" || root.kind === "video"
        anchors.fill: parent
        color: "black"

        Image {
            id: image
            visible: root.kind === "image"
            anchors.fill: parent
            fillMode: Image.PreserveAspectFit
            asynchronous: true
            source: root.kind === "image" ? root.mediaSource : ""
        }

        Loader {
            anchors.fill: parent
            active: root.kind === "video"
            sourceComponent: Item {
                VideoOutput {
                    id: videoOut
                    anchors.fill: parent
                    fillMode: VideoOutput.PreserveAspectFit
                }
                MediaPlayer {
                    id: videoPlayer
                    source: root.mediaSource
                    videoOutput: videoOut
                    loops: MediaPlayer.Infinite
                    onErrorOccurred: (error, errorString) => root.videoError = "Không phát được " + (root.slide ? root.slide.src : "") + " — " + errorString
                    Component.onCompleted: play()
                }
                Component.onDestruction: videoPlayer.stop()
            }
        }

        Text {
            id: mediaError
            anchors.centerIn: parent
            width: parent.width * 0.8
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
            visible: text !== ""
            text: root.kind === "image" && image.status === Image.Error
                  ? "Không tải được " + (root.slide ? root.slide.src : "") + " — kiểm tra file trong content_manifest/media/"
                  : root.kind === "video" ? root.videoError : ""
            color: "white"
            font.family: Theme.font
            font.pixelSize: Math.max(16, parent.height * 0.03)
        }
    }
}
