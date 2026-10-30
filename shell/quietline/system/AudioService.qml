import QtQuick
import Quickshell
import Quickshell.Services.Pipewire
import "../logic/Models.js" as Models

// Звук PipeWire: выход и микрофон по умолчанию, громкость до 150 %, выбор выхода.
Scope {
    id: root
    readonly property var sink: Pipewire.defaultAudioSink
    readonly property var source: Pipewire.defaultAudioSource
    readonly property bool available: Pipewire.ready && !!sink && !!sink.audio
    readonly property bool micAvailable: Pipewire.ready && !!source && !!source.audio
    readonly property var sinks: Pipewire.nodes.values.filter(node => node.isSink && !node.isStream && node.audio)
    // Время (мс), до которого изменения звука считаются сделанными ползунками оболочки:
    // индикатор их не показывает.
    property real localUntil: 0
    function markLocal() { localUntil = Date.now() + Models.OSD_LOCAL_MS; }
    function setVolume(value) { if (available) { markLocal(); sink.audio.volume = Models.clampVolume(value); } }
    function toggleMute() { if (available) { markLocal(); sink.audio.muted = !sink.audio.muted; } }
    function setMicVolume(value) { if (micAvailable) { markLocal(); source.audio.volume = Models.clampVolume(value); } }
    function toggleMicMute() { if (micAvailable) { markLocal(); source.audio.muted = !source.audio.muted; } }
    function selectSink(node) { Pipewire.preferredDefaultAudioSink = node; }
    // Свойства звука узлов обновляются, только пока их держит трекер.
    PwObjectTracker { objects: [root.sink, root.source].filter(Boolean) }
}
