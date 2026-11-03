import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import "../.."
import "../../controls"
import "../../inputs"
import "../frame"

// Страница «Дата и время»: текущие дата и время, синхронизация по сети и часовой пояс
// (`quietline-shell time`; пояс выбирается в раскрывающемся списке с поиском), формат часов и
// дата на панели (`Lang` и `quietline-shell region`).
SettingsPage {
    id: root
    title: Lang.s.settingsDateTime
    readonly property var values: store.values || {}
    property date now: new Date()
    property var zones: []
    property string zoneFilter: ""
    readonly property var shownZones: {
        var needle = zoneFilter.trim().toLowerCase().replace(/ /g, "_");
        return needle ? zones.filter(zone => zone.toLowerCase().indexOf(needle) >= 0) : zones;
    }
    onOpened: {
        now = new Date();
        store.load();
    }

    SettingsStore {
        id: store
        command: ["quietline-shell", "time"]
        failure: Lang.s.timeFailed
    }
    Process {
        id: zonesReader
        command: ["quietline-shell", "time", "--zones"]
        stdout: StdioCollector {
            onStreamFinished: { try { root.zones = JSON.parse(text).zones || []; } catch (_) { root.zones = []; } }
        }
    }
    Timer { interval: 1000; repeat: true; running: root.visible; onTriggered: root.now = new Date() }

    SettingsGroup {
        SettingsRow {
            symbol: "schedule"
            symbolBackground: Theme.accent
            symbolColor: Theme.accentForeground
            label: Lang.time(root.now)
            note: Lang.fullDate(root.now) + (root.values.timezone ? " · " + root.values.timezone : "")
        }
        SettingsRow {
            label: Lang.s.timeAuto
            note: Lang.s.timeAutoNote
            ShellSwitch {
                enabled: store.values !== null
                checked: root.values.ntp === true
                onToggled: store.set({ntp: checked})
                Accessible.name: Lang.s.timeAuto
            }
        }
        SettingsRow {
            id: zoneRow
            label: Lang.s.timeZone
            note: root.values.timezone || ""
            ShellButton {
                implicitHeight: 26; selected: true
                text: Lang.s.timeZoneChange
                enabled: store.values !== null
                onClicked: {
                    zoneRow.expanded = !zoneRow.expanded;
                    if (zoneRow.expanded && !root.zones.length && !zonesReader.running) zonesReader.running = true;
                    if (zoneRow.expanded) Qt.callLater(() => zoneSearch.forceActiveFocus());
                }
            }
            below: ColumnLayout {
                Layout.fillWidth: true
                spacing: 8
                ShellTextField {
                    id: zoneSearch
                    Layout.fillWidth: true
                    placeholderText: Lang.s.timeZoneSearch
                    onTextChanged: root.zoneFilter = text
                    Keys.onDownPressed: zoneList.forceActiveFocus()
                    onAccepted: { if (root.shownZones.length) { store.set({timezone: root.shownZones[0]}); zoneRow.expanded = false; } }
                }
                ListView {
                    id: zoneList
                    Layout.fillWidth: true
                    Layout.preferredHeight: 220
                    clip: true
                    model: root.shownZones
                    keyNavigationEnabled: true
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ShellScrollBar {}
                    Keys.onReturnPressed: { store.set({timezone: root.shownZones[currentIndex]}); zoneRow.expanded = false; }
                    delegate: Rectangle {
                        id: zoneItem
                        required property var modelData
                        required property int index
                        readonly property bool current: modelData === root.values.timezone
                        readonly property bool lit: zoneArea.containsMouse || (zoneList.activeFocus && zoneList.currentIndex === index)
                        width: zoneList.width
                        height: Theme.menuRowHeight
                        radius: Theme.radiusSmall
                        color: lit ? Theme.accent : "transparent"
                        Icon {
                            id: zoneCheck
                            anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                            name: zoneItem.current ? "check" : ""
                            size: 16
                            color: zoneItem.lit ? Theme.accentForeground : Theme.accent
                        }
                        Text {
                            renderType: Theme.textRenderType(QsWindow.window)
                            anchors { left: zoneCheck.right; leftMargin: 6; verticalCenter: parent.verticalCenter }
                            text: zoneItem.modelData.replace(/_/g, " ")
                            color: zoneItem.lit ? Theme.accentForeground : Theme.text
                            font.family: Theme.sans; font.pixelSize: Theme.fontSize
                        }
                        MouseArea {
                            id: zoneArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: { store.set({timezone: zoneItem.modelData}); zoneRow.expanded = false; }
                        }
                    }
                    Text {
                        renderType: Theme.textRenderType(QsWindow.window)
                        anchors.centerIn: parent
                        visible: zoneList.count === 0 && !zonesReader.running
                        text: Lang.s.timeZoneNone
                        color: Theme.text3; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
                    }
                }
            }
        }
    }
    PageNote { visible: store.error !== ""; color: Theme.danger; text: store.error }

    SettingsGroup {
        title: Lang.s.timeFormats
        SettingsRow {
            label: Lang.s.settingsClock
            SegmentedControl {
                showLabels: true; segmentHeight: 22
                model: [{label: Lang.s.clock24}, {label: Lang.s.clock12}]
                currentIndex: Lang.clock === "24h" ? 0 : 1
                onActivated: index => Lang.update({clock: index === 0 ? "24h" : "12h"})
            }
        }
        SettingsRow {
            label: Lang.s.settingsBarDate
            fill: true
            SegmentedControl {
                readonly property var modes: ["short", "numeric", "weekday"]
                showLabels: true; segmentHeight: 22
                model: modes.map(mode => ({label: Lang.barDay(root.now, mode)}))
                currentIndex: modes.indexOf(Lang.barDate)
                onActivated: index => Lang.update({barDate: modes[index]})
            }
        }
    }
}
