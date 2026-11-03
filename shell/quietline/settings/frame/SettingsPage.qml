import QtQuick
import QtQuick.Layouts
import Quickshell
import "../.."

// Страница раздела окна «Настройки»: заголовок `title` и колонка групп шириной до 720 px по
// центру области страницы. StackLayout растягивает страницу на всю ширину; дочерние элементы
// занимают всю ширину колонки. `opened` — страница стала видна (раздел открыт): по нему она
// перечитывает свои данные.
Item {
    id: root
    property string title: ""
    default property alias content: pageColumn.data
    signal opened()
    onVisibleChanged: { if (visible) opened(); }
    Component.onCompleted: Qt.callLater(function() { if (root.visible) root.opened(); })
    implicitHeight: pageColumn.implicitHeight + 48
    ColumnLayout {
        id: pageColumn
        width: Math.min(root.width - 56, 720)
        x: Math.round((root.width - width) / 2); y: 20
        spacing: 18
        Text {
            renderType: Theme.textRenderType(QsWindow.window)
            Layout.bottomMargin: 4
            visible: root.title.length > 0
            text: root.title
            color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.headlineFontSize; font.weight: Font.Bold
        }
    }
}
