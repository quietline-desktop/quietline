import QtQuick
import QtQuick.Layouts
import ".."

// Разделитель групп правой части панели: вертикальная черта 1×16 px с полями по 10 px.
Rectangle {
    Layout.leftMargin: 10; Layout.rightMargin: 10
    Layout.alignment: Qt.AlignVCenter
    implicitWidth: 1; implicitHeight: 16
    color: Theme.fillStrong
}
