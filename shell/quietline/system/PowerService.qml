import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.UPower
import "../logic/Models.js" as Models

// Батарея UPower и профили питания power-profiles-daemon.
Scope {
    id: root
    readonly property var battery: UPower.displayDevice
    readonly property bool hasBattery: !!battery && battery.ready && battery.isPresent
    readonly property int percent: hasBattery ? Math.round(battery.percentage * 100) : 0
    readonly property bool charging: hasBattery && (battery.state === UPowerDeviceState.Charging || battery.state === UPowerDeviceState.FullyCharged)
    readonly property string timeText: !hasBattery ? "" : charging
        ? (battery.timeToFull > 0 ? "до полной зарядки " + Models.formatDuration(battery.timeToFull) : "заряжается")
        : (battery.timeToEmpty > 0 ? "осталось " + Models.formatDuration(battery.timeToEmpty) : "")
    // PowerProfiles отдаёт значение и без службы, поэтому её наличие проверяет powerprofilesctl.
    property bool profilesAvailable: false
    readonly property int profile: PowerProfiles.profile
    readonly property bool hasPerformance: PowerProfiles.hasPerformanceProfile
    function setProfile(value) {
        if (value === PowerProfile.Performance && !hasPerformance) return;
        PowerProfiles.profile = value;
    }
    Process {
        command: ["powerprofilesctl", "get"]
        running: true
        onExited: (code, status) => root.profilesAvailable = code === 0
    }
}
