import QtQuick
import QtQuick.Layouts
import Quickshell.Services.UPower
import ".."
import "../controls"

// Окно батареи под панелью: заряд и состояние (зарядка, время до заряда или разряда), режим
// питания сегментами «Экономия / Баланс / Мощность» и переход к разделу «Питание» в «Настройках».
// Без службы профилей питания вместо сегментов — пояснение.
ColumnLayout {
    id: root
    required property var power
    property bool reducedMotion: false
    signal settingsRequested()
    spacing: 10
    readonly property var profiles: [PowerProfile.PowerSaver, PowerProfile.Balanced, PowerProfile.Performance]
        .filter(value => value !== PowerProfile.Performance || power.hasPerformance)

    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: 4; Layout.rightMargin: 4
        Text {
            renderType: Text.CurveRendering
            Layout.fillWidth: true
            text: Lang.s.batteryTitle
            color: Theme.text
            font.family: Theme.sans; font.pixelSize: Theme.titleFontSize; font.weight: Font.Bold
        }
        Text {
            renderType: Text.CurveRendering
            text: root.power.percent + "%"
            color: Theme.text
            font.family: Theme.sans; font.pixelSize: Theme.titleFontSize; font.weight: Font.DemiBold
            font.features: {"tnum": 1}
        }
    }
    Text {
        renderType: Text.CurveRendering
        Layout.fillWidth: true
        Layout.leftMargin: 4; Layout.rightMargin: 4
        Layout.topMargin: -6
        // Время добавляется, только если оно известно: без него «заряжается» повторило бы состояние.
        readonly property bool full: root.power.charging && root.power.percent >= 100
        readonly property bool timeKnown: !full && root.power.timeText !== "" && root.power.timeText !== Lang.s.powerCharging
        text: (root.power.charging ? (full ? Lang.s.quickCharged : Lang.s.quickCharging) : Lang.s.quickOnBattery)
            + (timeKnown ? " · " + root.power.timeText : "")
        color: Theme.text2
        font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
        elide: Text.ElideRight
    }
    Text {
        renderType: Text.CurveRendering
        Layout.leftMargin: 4
        Layout.topMargin: 4
        text: Lang.s.powerMode
        color: Theme.text2
        font.family: Theme.sans; font.pixelSize: Theme.smallFontSize; font.weight: Font.DemiBold
    }
    Rectangle {
        visible: root.power.profilesAvailable
        Layout.fillWidth: true
        implicitHeight: 36
        radius: Theme.radiusModule
        color: Theme.fill
        border.width: 1; border.color: Theme.moduleBorder
        SegmentedControl {
            anchors.fill: parent; anchors.margins: 3
            color: "transparent"
            showLabels: true
            segmentHeight: 30
            segmentWidth: (width - 4) / model.length
            reducedMotion: root.reducedMotion
            model: root.profiles.map(value => value === PowerProfile.PowerSaver ? {symbol: "eco", label: Lang.s.powerSaverShort, hint: Lang.s.powerSaver}
                                            : value === PowerProfile.Balanced ? {symbol: "balance", label: Lang.s.powerBalanced, hint: Lang.s.powerBalanced}
                                            : {symbol: "bolt", label: Lang.s.powerPerformanceShort, hint: Lang.s.powerPerformance})
            currentIndex: root.profiles.indexOf(root.power.profile)
            onActivated: index => root.power.setProfile(root.profiles[index])
        }
    }
    Text {
        renderType: Text.CurveRendering
        visible: !root.power.profilesAvailable
        Layout.fillWidth: true
        Layout.leftMargin: 4
        text: Lang.s.powerDaemonMissing
        color: Theme.text2
        font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
        wrapMode: Text.Wrap
    }
    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.hairline }
    ShellMenuItem {
        Layout.fillWidth: true
        symbol: "settings"
        text: Lang.s.batterySettings
        onTriggered: root.settingsRequested()
    }
}
