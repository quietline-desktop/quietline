import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import ".."
import "../controls"
import "../panels"
import "../logic/Models.js" as Models

// Окно «Настройки»: боковая навигация и страницы на тех же компонентах управления,
// что и всплывающие панели, поэтому изменение здесь видно и там.
// `open(section)` открывает раздел по идентификатору (`keyboard` открывает `region`);
// пусто или неизвестно — текущий раздел.
FloatingWindow {
    id: root
    required property var services
    required property var desktop
    property string section: "network"
    readonly property var sections: [
        {id: "network", label: Lang.s.settingsNetwork, icon: ""},
        {id: "audio", label: Lang.s.settingsAudio, icon: ""},
        {id: "display", label: Lang.s.settingsDisplay, icon: ""},
        {id: "bluetooth", label: Lang.s.settingsBluetooth, icon: ""},
        {id: "power", label: Lang.s.settingsPower, icon: ""},
        {id: "region", label: Lang.s.settingsRegion, icon: ""},
        {id: "shortcuts", label: Lang.s.settingsShortcuts, icon: ""},
        {id: "about", label: Lang.s.settingsAbout, icon: ""}
    ]
    // Привязки Hyprland; памятка `shortcuts` пересчитывается из них при смене языка и списка приложений.
    property var binds: []
    readonly property var shortcuts: Models.describeBinds(binds, Lang.s, desktop.entries)
    property var info: null
    title: Lang.s.settingsTitle
    visible: false
    implicitWidth: 920
    implicitHeight: 620
    minimumSize: Qt.size(720, 480)
    color: Theme.background

    function open(name) {
        var id = Models.resolveSection(name);
        if (id && sections.some(item => item.id === id)) section = id;
        visible = true;
        Qt.callLater(function() { navigation.forceActiveFocus(); });
    }
    onSectionChanged: load()
    onVisibleChanged: { if (visible) load(); }
    function load() {
        if (section === "shortcuts" && !bindsProcess.running) bindsProcess.running = true;
        if (section === "about" && !aboutProcess.running) aboutProcess.running = true;
        if (section === "network") services.network.refresh();
    }

    Process {
        id: bindsProcess
        command: ["hyprctl", "binds", "-j"]
        stdout: StdioCollector {
            onStreamFinished: {
                try { root.binds = JSON.parse(text).filter(bind => bind && typeof bind === "object"); }
                catch (_) { root.binds = []; }
            }
        }
    }
    Process {
        id: aboutProcess
        command: ["quietline-shell", "about"]
        stdout: StdioCollector {
            onStreamFinished: { try { root.info = JSON.parse(text); } catch (_) { root.info = null; } }
        }
    }

    component PageTitle: Text {
        color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.titleFontSize; font.bold: true
    }
    component Heading: Text {
        color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.fontSize; font.bold: true
    }
    component Line: Text {
        color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.fontSize
        wrapMode: Text.Wrap; Layout.fillWidth: true
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0
        Rectangle {
            Layout.fillHeight: true
            Layout.preferredWidth: 230
            color: Theme.surface
            ListView {
                id: navigation
                anchors.fill: parent; anchors.margins: 10
                spacing: 2
                model: root.sections
                currentIndex: root.sections.findIndex(item => item.id === root.section)
                keyNavigationEnabled: true
                focus: true
                Accessible.role: Accessible.List
                Accessible.name: Lang.s.settingsSections
                Keys.onReturnPressed: root.section = root.sections[currentIndex].id
                onCurrentIndexChanged: { if (currentIndex >= 0) root.section = root.sections[currentIndex].id; }
                delegate: ShellButton {
                    required property var modelData
                    required property int index
                    width: navigation.width
                    hint: modelData.label
                    emphasized: root.section === modelData.id
                    focusPolicy: Qt.NoFocus
                    onClicked: navigation.currentIndex = index
                    contentItem: Row {
                        spacing: 10
                        leftPadding: 6
                        Text {
                            width: 18
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.icon
                            font.family: Theme.icons; font.pixelSize: Theme.fontSize
                            color: root.section === modelData.id ? Theme.accentText : Theme.muted
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.label
                            font.family: Theme.sans; font.pixelSize: Theme.fontSize
                            color: root.section === modelData.id ? Theme.accentText : Theme.text
                        }
                    }
                }
            }
        }
        ScrollView {
            id: pageScroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            ScrollBar.vertical: ShellScrollBar {}
            StackLayout {
                width: pageScroll.availableWidth
                currentIndex: root.sections.findIndex(item => item.id === root.section)
                ColumnLayout {
                    Layout.margins: 24; spacing: 14
                    PageTitle { text: Lang.s.settingsNetwork }
                    NetworkControls { network: root.services.network; compact: false; Layout.fillWidth: true; Layout.maximumWidth: 560 }
                }
                ColumnLayout {
                    Layout.margins: 24; spacing: 14
                    PageTitle { text: Lang.s.settingsAudio }
                    AudioControls { audio: root.services.audio; compact: false; Layout.fillWidth: true; Layout.maximumWidth: 560 }
                }
                ColumnLayout {
                    Layout.margins: 24; spacing: 14
                    PageTitle { text: Lang.s.settingsDisplay }
                    BrightnessControls {
                        visible: Quickshell.screens.some(screen => Models.isBuiltinOutput(screen.name))
                        brightness: root.services.brightness; Layout.fillWidth: true; Layout.maximumWidth: 560
                    }
                    Line {
                        visible: !Quickshell.screens.some(screen => Models.isBuiltinOutput(screen.name))
                        color: Theme.muted; text: Lang.s.settingsBrightnessNote
                    }
                    Repeater {
                        model: Quickshell.screens
                        delegate: Line {
                            required property var modelData
                            text: modelData.name + " · " + modelData.width + "×" + modelData.height
                                + (modelData.model ? " · " + modelData.model : "")
                        }
                    }
                    Line { color: Theme.muted; font.pixelSize: Theme.smallFontSize; text: Lang.s.settingsDisplayNote }
                }
                ColumnLayout {
                    Layout.margins: 24; spacing: 14
                    PageTitle { text: "Bluetooth" }
                    BluetoothControls { bluetooth: root.services.bluetooth; compact: false; Layout.fillWidth: true; Layout.maximumWidth: 560 }
                }
                ColumnLayout {
                    Layout.margins: 24; spacing: 14
                    PageTitle { text: Lang.s.settingsPower }
                    PowerControls { power: root.services.power; Layout.fillWidth: true }
                }
                ColumnLayout {
                    id: regionPage
                    Layout.margins: 24; spacing: 14
                    // Дата для подписей форматов; обновляется при каждом открытии раздела.
                    property date today: new Date()
                    onVisibleChanged: { if (visible) today = new Date(); }
                    PageTitle { text: Lang.s.settingsRegion }
                    Line { visible: Lang.error !== ""; color: Theme.danger; text: Lang.error }

                    Heading { text: Lang.s.regionLanguageTitle }
                    Flow {
                        Layout.fillWidth: true; Layout.maximumWidth: 560; spacing: 6
                        ShellButton { text: Lang.s.languageRu; emphasized: Lang.language === "ru"; onClicked: Lang.update({language: "ru"}) }
                        ShellButton { text: Lang.s.languageEn; emphasized: Lang.language === "en"; onClicked: Lang.update({language: "en"}) }
                    }
                    Line { color: Theme.muted; font.pixelSize: Theme.smallFontSize; text: Lang.s.regionRestartNote }

                    Heading { text: Lang.s.clockTitle }
                    Flow {
                        Layout.fillWidth: true; Layout.maximumWidth: 560; spacing: 6
                        ShellButton { text: Lang.s.clock24; emphasized: Lang.clock === "24h"; onClicked: Lang.update({clock: "24h"}) }
                        ShellButton { text: Lang.s.clock12; emphasized: Lang.clock === "12h"; onClicked: Lang.update({clock: "12h"}) }
                    }
                    Heading { text: Lang.s.regionDateTitle }
                    Flow {
                        Layout.fillWidth: true; Layout.maximumWidth: 560; spacing: 6
                        Repeater {
                            model: ["dmy", "ymd", "mdy"]
                            delegate: ShellButton {
                                required property string modelData
                                text: Lang.dateIn(regionPage.today, modelData)
                                emphasized: Lang.date === modelData
                                onClicked: Lang.update({date: modelData})
                            }
                        }
                    }

                    Heading { text: Lang.s.regionLayoutsTitle }
                    Line { text: Lang.f(Lang.s.keyboardCurrent, root.desktop.keyboardLayoutName || root.desktop.keyboardLayout) }
                    Line { text: Lang.f(Lang.s.regionOrder, Lang.layouts.map(code => Models.layoutLabel(code, Lang.s)).join(" → ")) }
                    Flow {
                        Layout.fillWidth: true; Layout.maximumWidth: 560; spacing: 6
                        ShellButton { text: Lang.s.layoutSwap; onClicked: Lang.update({layouts: Lang.layouts.slice().reverse()}) }
                        ShellButton { text: Lang.s.keyboardNext; onClicked: root.desktop.switchLayout() }
                    }
                    Heading { text: Lang.s.regionToggleTitle }
                    Flow {
                        Layout.fillWidth: true; Layout.maximumWidth: 560; spacing: 6
                        Repeater {
                            model: ["grp:lalt_lshift_toggle", "grp:alt_shift_toggle", "grp:ctrl_shift_toggle", "grp:caps_toggle"]
                            delegate: ShellButton {
                                required property string modelData
                                text: Models.toggleLabel(modelData, Lang.s)
                                emphasized: Lang.toggle === modelData
                                onClicked: Lang.update({toggle: modelData})
                            }
                        }
                    }
                    Line { color: Theme.muted; text: Lang.f(Lang.s.keyboardToggleNote, Models.toggleLabel(Lang.toggle, Lang.s)) }
                }
                ColumnLayout {
                    Layout.margins: 24; spacing: 8
                    PageTitle { text: Lang.s.settingsShortcuts }
                    Line { visible: root.shortcuts.length === 0; color: Theme.muted; text: Lang.s.shortcutsUnreadable }
                    Repeater {
                        model: root.shortcuts
                        delegate: RowLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            Text { Layout.preferredWidth: 180; text: modelData.keys; color: Theme.accent; font.family: Theme.mono; font.pixelSize: Theme.fontSize }
                            Line { text: modelData.action }
                        }
                    }
                }
                ColumnLayout {
                    Layout.margins: 24; spacing: 8
                    PageTitle { text: Lang.s.settingsAbout }
                    Repeater {
                        model: root.info ? [
                            [Lang.s.aboutSystem, root.info.os], [Lang.s.aboutKernel, root.info.kernel], [Lang.s.aboutHostname, root.info.hostname],
                            [Lang.s.aboutCpu, root.info.cpu], [Lang.s.aboutMemory, root.info.memoryGb ? root.info.memoryGb + " " + Lang.s.unitGb : null],
                            ["Hyprland", root.info.hyprland], ["Quickshell", root.info.quickshell]
                        ] : []
                        delegate: RowLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            Text { Layout.preferredWidth: 160; text: modelData[0]; color: Theme.muted; font.family: Theme.sans; font.pixelSize: Theme.fontSize }
                            Line { text: modelData[1] || Lang.s.noData }
                        }
                    }
                    Line { visible: !root.info; color: Theme.muted; text: Lang.s.aboutLoading }
                }
            }
        }
    }
}
