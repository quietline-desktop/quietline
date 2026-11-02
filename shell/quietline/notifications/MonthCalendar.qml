import QtQuick
import QtQuick.Layouts
import Quickshell
import ".."
import "../controls"
import "../logic/Models.js" as Models

// Календарь месяца для центра уведомлений: название месяца, стрелки перехода, дни недели
// по языку оболочки, сегодняшний день — синим кружком. При открытии — текущий месяц.
Rectangle {
    id: root
    property int year: clock.date.getFullYear()
    property int month: clock.date.getMonth()
    function reset() { year = clock.date.getFullYear(); month = clock.date.getMonth(); }
    function shift(delta) {
        var date = new Date(year, month + delta, 1);
        year = date.getFullYear(); month = date.getMonth();
    }
    readonly property int firstDay: Lang.locale.firstDayOfWeek % 7
    readonly property var cells: Models.monthGrid(year, month, firstDay,
        {year: clock.date.getFullYear(), month: clock.date.getMonth(), day: clock.date.getDate()})
    SystemClock { id: clock; precision: SystemClock.Hours }
    implicitHeight: column.implicitHeight + 20
    radius: Theme.radiusModule
    color: Theme.fill
    border.width: 1; border.color: Theme.moduleBorder
    ColumnLayout {
        id: column
        x: 12; y: 10; width: parent.width - 24
        spacing: 6
        RowLayout {
            Layout.fillWidth: true
            Text {
                renderType: Text.CurveRendering
                Layout.fillWidth: true
                text: {
                    var name = Lang.locale.standaloneMonthName(root.month, Locale.LongFormat);
                    return name.charAt(0).toUpperCase() + name.slice(1) + " " + root.year;
                }
                color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.fontSize; font.weight: Font.DemiBold
            }
            ShellButton { implicitWidth: 24; implicitHeight: 24; symbol: "chevron_left"; symbolSize: 18; foreground: Theme.text2; hint: Lang.s.calendarPrevious; onClicked: root.shift(-1) }
            ShellButton { implicitWidth: 24; implicitHeight: 24; symbol: "chevron_right"; symbolSize: 18; foreground: Theme.text2; hint: Lang.s.calendarNext; onClicked: root.shift(1) }
        }
        GridLayout {
            Layout.fillWidth: true
            columns: 7
            columnSpacing: 2; rowSpacing: 2
            Repeater {
                model: 7
                delegate: Text {
                    required property int index
                    renderType: Text.CurveRendering
                    Layout.fillWidth: true; Layout.preferredWidth: 1
                    horizontalAlignment: Text.AlignHCenter
                    text: {
                        var name = Lang.locale.standaloneDayName((root.firstDay + index) % 7, Locale.ShortFormat);
                        return name.charAt(0).toUpperCase() + name.slice(1);
                    }
                    color: Theme.text3
                    font.family: Theme.sans; font.pixelSize: Theme.captionFontSize; font.weight: Font.DemiBold
                }
            }
            Repeater {
                model: root.cells
                delegate: Item {
                    required property var modelData
                    Layout.fillWidth: true; Layout.preferredWidth: 1
                    implicitHeight: 26
                    Rectangle {
                        anchors.centerIn: parent
                        width: 26; height: 26; radius: 13
                        color: parent.modelData.today ? Theme.accent : "transparent"
                    }
                    Text {
                        renderType: Text.CurveRendering
                        anchors.centerIn: parent
                        text: parent.modelData.day
                        color: parent.modelData.today ? Theme.accentForeground : parent.modelData.current ? Theme.text : Theme.text3
                        font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
                        font.weight: parent.modelData.today ? Font.DemiBold : Font.Normal
                    }
                }
            }
        }
    }
}
