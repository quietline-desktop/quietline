import QtQuick
import QtQuick.Layouts
import ".."

// Группа настроек: подпись над блоком и скруглённый блок со строками `SettingsRow`
// (дочерние элементы); строки сами отделяются волосяной линией.
ColumnLayout {
    id: root
    property string title: ""
    default property alias rows: box.data
    spacing: 7
    Layout.fillWidth: true
    Layout.maximumWidth: 640
    Text {
        renderType: Text.CurveRendering
        visible: root.title.length > 0
        Layout.leftMargin: 4
        text: root.title
        color: Theme.text2
        font.family: Theme.sans; font.pixelSize: Theme.smallFontSize; font.weight: Font.DemiBold
    }
    Rectangle {
        Layout.fillWidth: true
        implicitHeight: box.implicitHeight
        radius: 11
        color: Theme.fill
        border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.05)
        ColumnLayout {
            id: box
            width: parent.width
            spacing: 0
        }
    }
}
