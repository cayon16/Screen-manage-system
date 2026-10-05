import QtQuick
import QtQuick.Shapes

// Biểu tượng nét (stroke) vẽ từ path SVG khung 24×24, phóng theo `size` (nét dày phóng theo).
Item {
    id: root
    property string path
    property color color: Theme.accent
    property real strokeWidth: 1.8
    property real size: 40

    implicitWidth: size
    implicitHeight: size

    Shape {
        width: 24
        height: 24
        scale: root.size / 24
        transformOrigin: Item.TopLeft
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            strokeColor: root.color
            strokeWidth: root.strokeWidth
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: root.path }
        }
    }
}
