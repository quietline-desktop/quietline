import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.UPower
import ".."
import "../logic/Models.js" as Models

// Батарея UPower, предупреждения о низком заряде и профили питания power-profiles-daemon.
Scope {
    id: root
    readonly property var battery: UPower.displayDevice
    readonly property bool hasBattery: !!battery && battery.ready && battery.isPresent
    readonly property int percent: hasBattery ? Math.round(battery.percentage * 100) : 0
    readonly property bool charging: hasBattery && (battery.state === UPowerDeviceState.Charging || battery.state === UPowerDeviceState.FullyCharged)
    readonly property string timeText: !hasBattery ? "" : charging
        ? (battery.timeToFull > 0 ? Lang.f(Lang.s.powerUntilFull, Models.formatDuration(battery.timeToFull, Lang.s)) : Lang.s.powerCharging)
        : (battery.timeToEmpty > 0 ? Lang.f(Lang.s.powerRemaining, Models.formatDuration(battery.timeToEmpty, Lang.s)) : "")
    // Предупреждение о низком заряде — уведомлением, как от любой программы: всплывает,
    // попадает в историю; на критическом пороге — критическое. После зарядки счёт заново.
    property var warned: null
    function checkBattery() {
        if (!hasBattery) return;
        if (charging) { warned = null; return; }
        var level = Models.batteryWarning(warned, percent, charging);
        if (level === null) return;
        warned = level;
        var critical = level === Models.BATTERY_CRITICAL;
        Quickshell.execDetached(["notify-send", "--app-name=Quietline", "--urgency=" + (critical ? "critical" : "normal"),
                                 Lang.f(Lang.s.batteryLowTitle, percent), critical ? Lang.s.batteryCriticalBody : Lang.s.batteryLowBody]);
    }
    onPercentChanged: checkBattery()
    onChargingChanged: checkBattery()
    onHasBatteryChanged: checkBattery()
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
