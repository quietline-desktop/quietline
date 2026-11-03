import QtQuick
import ".."

// Кружок с первой буквой имени пользователя на градиенте.
Rectangle {
    property string name: ""
    property real size: 56
    implicitWidth: size; implicitHeight: size; radius: size / 2
    gradient: Gradient {
        orientation: Gradient.Horizontal
        GradientStop { position: 0; color: "#6a8cff" }
        GradientStop { position: 1; color: "#b06aff" }
    }
    Text {
        renderType: Text.CurveRendering
        anchors.centerIn: parent
        text: parent.name.charAt(0).toUpperCase()
        color: "#ffffff"
        font.family: Theme.sans; font.pixelSize: Math.round(parent.size * 0.39); font.weight: Font.Bold
    }
}
