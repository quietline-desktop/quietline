import QtQuick
import QtQuick.Layouts
import ".."
import "../controls"
import "../inputs"

// Громкость и микрофон; в полном виде (`compact: false`) ещё выбор выхода звука.
ColumnLayout {
    id: root
    required property var audio
    property bool compact: true
    spacing: 8
    Text {
        visible: !root.audio.available
        text: "Звуковое устройство не найдено"
        color: Theme.muted; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
    }
    RowLayout {
        visible: root.audio.available
        Layout.fillWidth: true
        ShellButton {
            font.family: Theme.icons
            text: root.audio.available && root.audio.sink.audio.muted ? "" : ""
            hint: root.audio.available && root.audio.sink.audio.muted ? "Включить звук" : "Выключить звук"
            onClicked: root.audio.toggleMute()
        }
        ShellSlider {
            Layout.fillWidth: true
            label: "Громкость"
            to: 1.0
            value: root.audio.available ? root.audio.sink.audio.volume : 0
            onMoved: root.audio.setVolume(value)
        }
    }
    RowLayout {
        visible: root.audio.micAvailable
        Layout.fillWidth: true
        ShellButton {
            font.family: Theme.icons
            text: root.audio.micAvailable && root.audio.source.audio.muted ? "" : ""
            hint: root.audio.micAvailable && root.audio.source.audio.muted ? "Включить микрофон" : "Выключить микрофон"
            onClicked: root.audio.toggleMicMute()
        }
        ShellSlider {
            Layout.fillWidth: true
            label: "Микрофон"
            to: 1.0
            value: root.audio.micAvailable ? root.audio.source.audio.volume : 0
            onMoved: root.audio.setMicVolume(value)
        }
    }
    Text {
        visible: !root.compact && root.audio.sinks.length > 1
        text: "Выход звука"
        color: Theme.muted; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
    }
    Repeater {
        model: root.compact ? [] : root.audio.sinks
        delegate: ShellButton {
            required property var modelData
            Layout.fillWidth: true
            text: modelData.description || modelData.nickname || modelData.name
            emphasized: root.audio.sink === modelData
            onClicked: root.audio.selectSink(modelData)
        }
    }
}
