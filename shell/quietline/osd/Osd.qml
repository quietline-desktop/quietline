import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import ".."
import "../controls"
import "../logic/Models.js" as Models

// Индикатор громкости, микрофона, яркости и раскладки: капсула 280×52 по центру снизу
// на мониторе с фокусом. Громкость и микрофон показываются по изменению PipeWire от
// любой программы, кроме ползунков самой оболочки и смены устройства по умолчанию; яркость —
// по `show("brightness")` после перечитывания; раскладка — по смене кода в `DesktopModel`.
// Окно не принимает ввод и видно поверх полноэкранных окон.
PanelWindow {
    id: root
    required property var services
    required property var desktop
    required property var indicators
    property string kind: "volume"
    property bool shown: false
    readonly property var view: kind === "layout" ? Models.osdView("layout", desktop.keyboardLayout, false)
        : kind === "brightness" ? Models.osdView("brightness", services.brightness.percent / 100, false)
        : kind === "mic" ? Models.osdView("mic", micAudio ? micAudio.volume : 0, micAudio ? micAudio.muted : false)
        : Models.osdView("volume", sinkAudio ? sinkAudio.volume : 0, sinkAudio ? sinkAudio.muted : false)
    readonly property var sinkAudio: services.audio.available ? services.audio.sink.audio : null
    readonly property var micAudio: services.audio.micAvailable ? services.audio.source.audio : null
    readonly property int motion: indicators.reducedMotion ? 0 : Theme.motionDuration

    function show(value) {
        kind = value;
        shown = true;
        hideTimer.restart();
    }
    // Изменение звука: только тот же узел, что при прошлом изменении, и не от ползунка оболочки.
    property var sinkId: null
    property var micId: null
    function audioChanged(value) {
        var node = value === "mic" ? services.audio.source : services.audio.sink;
        var id = node ? node.id : null;
        var known = value === "mic" ? micId : sinkId;
        if (value === "mic") micId = id; else sinkId = id;
        if (id === null || id !== known || Models.osdSuppressed(services.audio.localUntil, Date.now())) return;
        show(value);
    }

    screen: Quickshell.screens.find(screen => Hyprland.focusedMonitor && screen.name === Hyprland.focusedMonitor.name) || Quickshell.screens[0] || null
    visible: shown || card.opacity > 0
    anchors.bottom: true
    // Над местом дока — на одном месте в «Окнах» и «Тайлах».
    margins.bottom: 72
    exclusionMode: ExclusionMode.Ignore
    exclusiveZone: 0
    mask: Region {}
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    WlrLayershell.namespace: "quietline-osd"
    implicitWidth: 280
    implicitHeight: 52 + 8
    color: "transparent"

    Timer { id: hideTimer; interval: Models.OSD_HIDE_MS; onTriggered: root.shown = false }

    // Первое значение после запуска и смена устройства запоминаются без показа.
    Component.onCompleted: { sinkId = services.audio.sink ? services.audio.sink.id : null; micId = services.audio.source ? services.audio.source.id : null; }
    Connections {
        target: root.sinkAudio
        ignoreUnknownSignals: true
        function onVolumeChanged() { root.audioChanged("volume"); }
        function onMutedChanged() { root.audioChanged("volume"); }
    }
    Connections {
        target: root.micAudio
        ignoreUnknownSignals: true
        function onVolumeChanged() { root.audioChanged("mic"); }
        function onMutedChanged() { root.audioChanged("mic"); }
    }
    Connections {
        target: root.services.brightness
        function onRefreshed() { root.show("brightness"); }
    }
    property string layoutSeen: desktop.keyboardLayout
    Connections {
        target: root.desktop
        function onKeyboardLayoutChanged() {
            var code = root.desktop.keyboardLayout;
            if (code && root.layoutSeen && code !== root.layoutSeen) root.show("layout");
            root.layoutSeen = code;
        }
    }

    Rectangle {
        id: card
        width: root.implicitWidth
        height: 52
        y: root.shown ? 0 : 8
        opacity: root.shown ? 1 : 0
        radius: 26
        color: Theme.solidSurface
        border.width: 1
        border.color: Theme.border
        Behavior on opacity { NumberAnimation { duration: root.motion } }
        Behavior on y { NumberAnimation { duration: root.motion; easing.type: Easing.OutCubic } }
        RowLayout {
            anchors { fill: parent; leftMargin: 18; rightMargin: 18 }
            spacing: 12
            Icon {
                name: root.view.icon
                filled: true
                size: 22
            }
            Rectangle {
                visible: root.view.fill >= 0
                Layout.fillWidth: true
                implicitHeight: 6
                radius: 3
                color: Theme.osdTrack
                Rectangle {
                    width: parent.width * Math.max(0, root.view.fill)
                    height: parent.height
                    radius: 3
                    color: root.kind !== "brightness" && (root.kind === "mic" ? root.micAudio && root.micAudio.muted : root.sinkAudio && root.sinkAudio.muted) ? Theme.text3 : Theme.osdFill
                    Behavior on width { NumberAnimation { duration: root.motion / 2 } }
                }
            }
            Text {
                renderType: Theme.textRenderType(QsWindow.window)
                Layout.fillWidth: root.view.fill < 0
                horizontalAlignment: root.view.fill < 0 ? Text.AlignLeft : Text.AlignRight
                text: root.view.text
                color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize; font.weight: Font.DemiBold
                font.features: { "tnum": 1 }
                Layout.preferredWidth: root.view.fill < 0 ? -1 : 36
            }
        }
    }
}
