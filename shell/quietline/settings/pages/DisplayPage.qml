import QtQuick
import QtQuick.Layouts
import Quickshell
import "../.."
import "../../controls"
import "../../inputs"
import "../../panels"
import "../frame"
import "../../logic/Models.js" as Models

// Страница «Экран и яркость»: яркость встроенного экрана и группа на каждый подключённый
// монитор — разрешение, частота, масштаб, расположение, поворот и VRR (`DisplayService`).
// Смена разрешения, частоты, расположения или поворота применяется сразу и ждёт подтверждения
// 15 секунд; без ответа сервис записывает прежние значения монитора обратно.
SettingsPage {
    id: root
    required property var brightness
    required property var display
    title: Lang.s.settingsDisplay
    onOpened: display.refresh()
    function label(output) { return Models.isBuiltinOutput(output.name) ? Lang.s.displayBuiltin : (output.description || output.name); }

    // Подтверждение режима — над группами, чтобы его было видно без прокрутки.
    SettingsGroup {
        visible: !!root.display.confirming
        SettingsRow {
            symbol: "schedule"
            symbolBackground: Theme.accent
            symbolColor: Theme.accentForeground
            label: Lang.f(Lang.s.displayConfirm, root.display.secondsLeft)
            note: {
                var change = root.display.confirming;
                var output = change ? root.display.outputs.find(item => item.output === change.output) : null;
                return output ? root.label(output) : "";
            }
            ShellButton { implicitHeight: 26; selected: true; text: Lang.s.displayRevert; onClicked: root.display.revert() }
            ShellButton { implicitHeight: 26; emphasized: true; text: Lang.s.displayKeep; onClicked: root.display.keep() }
        }
    }
    SettingsGroup {
        visible: Quickshell.screens.some(screen => Models.isBuiltinOutput(screen.name))
        SettingsRow {
            label: Lang.s.brightnessLabel
            fill: true
            BrightnessControls { width: parent.width; brightness: root.brightness }
        }
    }
    PageNote {
        visible: !Quickshell.screens.some(screen => Models.isBuiltinOutput(screen.name))
        text: Lang.s.settingsBrightnessNote
    }

    Repeater {
        model: root.display.outputs
        delegate: SettingsGroup {
            id: monitorGroup
            required property var modelData
            readonly property var output: modelData
            readonly property var saved: root.display.monitors[output.output] || {}
            // Сохранённый режим `WxH@R` → {width, height, refresh}; без него — null («Авто»).
            readonly property var savedMode: {
                var found = /^(\d+)x(\d+)@([\d.]+)$/.exec(saved.mode || "");
                return found ? {width: Number(found[1]), height: Number(found[2]), refresh: Number(found[3])} : null;
            }
            readonly property var resolutions: Models.displayResolutions(output.modes)
            // Разрешение, для которого показываются частоты и масштабы: выбранное или текущее.
            readonly property int modeWidth: savedMode ? savedMode.width : output.width
            readonly property int modeHeight: savedMode ? savedMode.height : output.height
            readonly property var rates: Models.displayRates(output.modes, modeWidth, modeHeight)
            readonly property var scales: Models.scaleChoices(modeWidth, modeHeight)
            Layout.fillWidth: true
            title: root.label(output)
            enabled: !root.display.busy

            SettingsRow {
                label: Lang.s.displayResolution
                note: Lang.f(Lang.s.displayNow, monitorGroup.output.width, monitorGroup.output.height, Models.refreshLabel(monitorGroup.output.refreshRate, Lang.s))
                ShellSelect {
                    label: Lang.s.displayResolution
                    model: [{label: Lang.s.displayScaleAuto}].concat(monitorGroup.resolutions.map(mode => ({label: mode.width + "×" + mode.height})))
                    currentIndex: monitorGroup.savedMode
                        ? 1 + monitorGroup.resolutions.findIndex(mode => mode.width === monitorGroup.savedMode.width && mode.height === monitorGroup.savedMode.height)
                        : 0
                    onActivated: index => {
                        if (index === 0) { root.display.set(monitorGroup.output.output, {mode: "auto"}, true); return; }
                        var mode = monitorGroup.resolutions[index - 1];
                        var rates = Models.displayRates(monitorGroup.output.modes, mode.width, mode.height);
                        root.display.set(monitorGroup.output.output, {mode: Models.displayMode(mode.width, mode.height, rates[0])}, true);
                    }
                }
            }
            SettingsRow {
                label: Lang.s.displayRefresh
                ShellSelect {
                    label: Lang.s.displayRefresh
                    model: [{label: Lang.s.displayScaleAuto}].concat(monitorGroup.rates.map(rate => ({label: Models.refreshLabel(rate, Lang.s)})))
                    currentIndex: monitorGroup.savedMode ? 1 + Models.nearestRate(monitorGroup.rates, monitorGroup.savedMode.refresh) : 0
                    onActivated: index => root.display.set(monitorGroup.output.output,
                        {mode: index === 0 ? "auto" : Models.displayMode(monitorGroup.modeWidth, monitorGroup.modeHeight, monitorGroup.rates[index - 1])}, true)
                }
            }
            SettingsRow {
                label: Lang.s.settingsScale
                note: Lang.s.displayScaleNote
                fill: true
                SegmentedControl {
                    showLabels: true; segmentHeight: 24
                    model: [{label: Lang.s.displayScaleAuto}].concat(monitorGroup.scales.map(scale => ({label: Lang.f(Lang.s.displayScalePercent, Math.round(scale * 100))})))
                    // «Авто» — 0; сохранённый масштаб вне списка — ни один сегмент.
                    currentIndex: monitorGroup.saved.scale === undefined ? 0
                        : (index => index < 0 ? -1 : index + 1)(monitorGroup.scales.findIndex(scale => Math.abs(scale - monitorGroup.saved.scale) < 0.001))
                    busy: root.display.busy
                    onActivated: index => root.display.set(monitorGroup.output.output, {scale: index === 0 ? "auto" : monitorGroup.scales[index - 1]}, false)
                }
            }
            SettingsRow {
                visible: root.display.outputs.length > 1
                label: Lang.s.displayPosition
                fill: true
                SegmentedControl {
                    readonly property var positions: ["auto", "auto-left", "auto-right", "auto-up", "auto-down"]
                    showLabels: true; segmentHeight: 24
                    model: [{label: Lang.s.displayScaleAuto}, {label: Lang.s.displayPositionLeft}, {label: Lang.s.displayPositionRight},
                            {label: Lang.s.displayPositionUp}, {label: Lang.s.displayPositionDown}]
                    currentIndex: positions.indexOf(monitorGroup.saved.position || "auto")
                    busy: root.display.busy
                    onActivated: index => root.display.set(monitorGroup.output.output, {position: positions[index]}, true)
                }
            }
            SettingsRow {
                label: Lang.s.displayRotation
                SegmentedControl {
                    showLabels: true; segmentHeight: 22
                    model: [{label: Lang.s.displayRotationNone}, {label: "90°"}, {label: "180°"}, {label: "270°"}]
                    currentIndex: monitorGroup.saved.transform !== undefined ? monitorGroup.saved.transform : Math.max(0, Math.min(3, monitorGroup.output.transform || 0))
                    busy: root.display.busy
                    onActivated: index => root.display.set(monitorGroup.output.output, {transform: index}, true)
                }
            }
            SettingsRow {
                label: Lang.s.displayVrr
                SegmentedControl {
                    showLabels: true; segmentHeight: 22
                    model: [{label: Lang.s.displayVrrOff}, {label: Lang.s.displayVrrOn}, {label: Lang.s.displayVrrFullscreen}]
                    currentIndex: monitorGroup.saved.vrr !== undefined ? monitorGroup.saved.vrr : (monitorGroup.output.vrr ? 1 : 0)
                    busy: root.display.busy
                    onActivated: index => root.display.set(monitorGroup.output.output, {vrr: index}, false)
                }
            }
        }
    }
    PageNote { visible: root.display.error !== ""; color: Theme.danger; text: root.display.error }
    PageNote { visible: !root.display.applied; text: Lang.s.displayScalePending }
    PageNote { text: Lang.s.settingsDisplayNote }
}
