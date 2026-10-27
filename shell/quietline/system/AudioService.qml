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
    function setVolume(value) { if (available) sink.audio.volume = Models.clampVolume(value); }
    function toggleMute() { if (available) sink.audio.muted = !sink.audio.muted; }
    function setMicVolume(value) { if (micAvailable) source.audio.volume = Models.clampVolume(value); }
    function toggleMicMute() { if (micAvailable) source.audio.muted = !source.audio.muted; }
    function selectSink(node) { Pipewire.preferredDefaultAudioSink = node; }
    // Свойства звука узлов обновляются, только пока их держит трекер.
    PwObjectTracker { objects: [root.sink, root.source].filter(Boolean) }
}
