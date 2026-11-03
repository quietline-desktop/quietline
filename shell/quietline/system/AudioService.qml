import QtQuick
import Quickshell
import Quickshell.Services.Pipewire
import "../logic/Models.js" as Models

// Звук PipeWire: выход и микрофон по умолчанию, громкость до 150 %, выбор выхода и микрофона,
// потоки воспроизведения приложений (`playback`) и приложения, которые сейчас записывают
// микрофон (`micUsers`).
Scope {
    id: root
    readonly property var sink: Pipewire.defaultAudioSink
    readonly property var source: Pipewire.defaultAudioSource
    readonly property bool available: Pipewire.ready && !!sink && !!sink.audio
    readonly property bool micAvailable: Pipewire.ready && !!source && !!source.audio
    readonly property var sinks: Pipewire.nodes.values.filter(node => node.isSink && !node.isStream && node.audio)
    // Устройства ввода отбираются без `properties`: они действительны только у узлов под трекером.
    readonly property var sources: Pipewire.nodes.values.filter(node => !node.isSink && !node.isStream && node.audio)
    // Время (мс), до которого изменения звука считаются сделанными ползунками оболочки:
    // индикатор их не показывает.
    property real localUntil: 0
    function markLocal() { localUntil = Date.now() + Models.OSD_LOCAL_MS; }
    function setVolume(value) { if (available) { markLocal(); sink.audio.volume = Models.clampVolume(value); } }
    function toggleMute() { if (available) { markLocal(); sink.audio.muted = !sink.audio.muted; } }
    function setMicVolume(value) { if (micAvailable) { markLocal(); source.audio.volume = Models.clampVolume(value); } }
    function toggleMicMute() { if (micAvailable) { markLocal(); source.audio.muted = !source.audio.muted; } }
    // Шаг громкости колесом мыши на панели: выше 100 % колесо не поднимает (ползунок — до 150 %);
    // индикатор показывает новое значение.
    function stepVolume(delta) {
        if (!available) return;
        var current = sink.audio.volume;
        sink.audio.volume = Math.max(0, Math.min(Math.max(1, current), current + delta));
    }
    function selectSink(node) { Pipewire.preferredDefaultAudioSink = node; }
    function selectSource(node) { Pipewire.preferredDefaultAudioSource = node; }
    function setStreamVolume(node, value) { if (node && node.audio) { markLocal(); node.audio.volume = Models.clampVolume(value); } }
    function toggleStreamMute(node) { if (node && node.audio) { markLocal(); node.audio.muted = !node.audio.muted; } }
    // Потоки приложений; входные (`media.class` Stream/Input/Audio) — запись микрофона.
    readonly property var streams: Pipewire.nodes.values.filter(node => node.isStream)
    readonly property var playback: streams.filter(node => node.audio && !!node.properties
        && node.properties["media.class"] === "Stream/Output/Audio")
    readonly property var micUsers: Models.micUsers(streams.map(node => node.properties)
        .filter(props => !!props && props["media.class"] === "Stream/Input/Audio"))
    // Свойства звука узлов обновляются, только пока их держит трекер.
    PwObjectTracker { objects: [root.sink, root.source].filter(Boolean).concat(root.streams) }
}
