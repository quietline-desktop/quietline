import QtQuick
import QtQuick.Layouts
import ".."
import "../controls"
import "../inputs"

// Страница «Звук» окна «Настройки»: группа выхода (громкость, кнопка звука, выбор
// устройства с галочкой у текущего) и группа микрофона.
ColumnLayout {
    id: root
    required property var audio
    spacing: 18

    // Ползунок громкости с кнопкой выключения слева и процентом справа.
    component VolumeLine: RowLayout {
        id: line
        property bool muted: false
        property real volume: 0
        property string symbol: ""
        property string mutedSymbol: ""
        property string hint: ""
        property string label: ""
        signal toggled()
        signal moved(real value)
        Layout.fillWidth: true
        spacing: 8
        ShellButton {
            symbol: line.muted ? line.mutedSymbol : line.symbol
            foreground: line.muted ? Theme.danger : Theme.text
            hint: line.hint
            onClicked: line.toggled()
        }
        ShellSlider {
            Layout.fillWidth: true
            label: line.label
            to: 1.0
            value: line.volume
            onMoved: line.moved(value)
        }
        Text {
            renderType: Text.CurveRendering
            Layout.preferredWidth: 40
            horizontalAlignment: Text.AlignRight
            text: Math.round(line.volume * 100) + "%"
            color: Theme.text2; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
            font.features: ({ "tnum": 1 })
        }
    }

    SettingsGroup {
        visible: !root.audio.available
        SettingsRow { symbol: "volume_off"; note: Lang.s.audioNotFound }
    }

    SettingsGroup {
        visible: root.audio.available
        title: Lang.s.audioOutput
        SettingsRow {
            label: Lang.s.audioVolume
            fill: true
            VolumeLine {
                width: parent.width
                muted: root.audio.available && root.audio.sink.audio.muted
                volume: root.audio.available ? root.audio.sink.audio.volume : 0
                symbol: "volume_up"; mutedSymbol: "volume_off"
                hint: muted ? Lang.s.audioUnmute : Lang.s.audioMute
                label: Lang.s.audioVolume
                onToggled: root.audio.toggleMute()
                onMoved: value => root.audio.setVolume(value)
            }
        }
        Repeater {
            model: root.audio.sinks
            delegate: SettingsRow {
                id: sinkRow
                required property var modelData
                readonly property bool current: root.audio.sink === modelData
                symbol: "speaker"
                label: modelData.description || modelData.nickname || modelData.name
                labelBold: current
                clickable: !current
                onClicked: root.audio.selectSink(modelData)
                Icon { visible: sinkRow.current; name: "check"; size: 18; weight: 600; color: Theme.accent }
            }
        }
    }

    SettingsGroup {
        visible: root.audio.micAvailable
        title: Lang.s.audioMic
        SettingsRow {
            label: Lang.s.audioInputLevel
            fill: true
            VolumeLine {
                width: parent.width
                muted: root.audio.micAvailable && root.audio.source.audio.muted
                volume: root.audio.micAvailable ? root.audio.source.audio.volume : 0
                symbol: "mic"; mutedSymbol: "mic_off"
                hint: muted ? Lang.s.audioMicUnmute : Lang.s.audioMicMute
                label: Lang.s.audioMic
                onToggled: root.audio.toggleMicMute()
                onMoved: value => root.audio.setMicVolume(value)
            }
        }
    }
}
