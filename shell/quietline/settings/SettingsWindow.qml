import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import ".."
import "../controls"
import "../panels"
import "../inputs"
import "../logic/Models.js" as Models

// Окно «Настройки»: боковая навигация и страницы на тех же компонентах управления,
// что и всплывающие панели, поэтому изменение здесь видно и там.
// `open(section)` открывает раздел по идентификатору (`keyboard` открывает `region`);
// пусто или неизвестно — текущий раздел. Окно создаётся при открытии и уничтожается при
// закрытии: закрытое композитором `FloatingWindow` повторно не показывается. Раздел,
// привязки и сведения о системе живут вне окна и переживают его закрытие.
Scope {
    id: root
    required property var services
    required property var desktop
    property string section: "network"
    // Разделы не зависят от языка: подпись берётся в делегате по `labelKey`, поэтому смена языка
    // не пересоздаёт модель списка и не сбрасывает текущий раздел.
    // `group` — номер группы в боковой панели (между группами — отступ), `color` — цвет квадрата значка.
    readonly property var sections: [
        {id: "network", labelKey: "settingsNetwork", symbol: "wifi", color: "#0a84ff", group: 0},
        {id: "bluetooth", labelKey: "settingsBluetooth", symbol: "bluetooth", color: "#0a84ff", group: 0},
        {id: "audio", labelKey: "settingsAudio", symbol: "volume_up", color: "#ff375f", group: 1},
        {id: "display", labelKey: "settingsDisplay", symbol: "light_mode", color: "#0a84ff", group: 1},
        {id: "power", labelKey: "settingsPower", symbol: "battery_full", color: "#30d158", group: 1},
        {id: "notifications", labelKey: "settingsNotifications", symbol: "notifications", color: "#ff453a", group: 1},
        {id: "region", labelKey: "settingsRegion", symbol: "language", color: "#8e8e93", group: 2},
        {id: "shortcuts", labelKey: "settingsShortcuts", symbol: "keyboard", color: "#8e8e93", group: 2},
        {id: "about", labelKey: "settingsAbout", symbol: "info", color: "#8e8e93", group: 2}
    ]
    // Строка поиска боковой панели: разделы, в подписи или ключевых словах которых она есть.
    property string filter: ""
    readonly property var visibleSections: sections.filter(item => {
        var needle = filter.trim().toLowerCase();
        if (!needle) return true;
        return (Lang.s[item.labelKey] + " " + (Lang.s[item.labelKey + "Keywords"] || "")).toLowerCase().indexOf(needle) >= 0;
    })
    // Привязки Hyprland; памятка `shortcuts` пересчитывается из них при смене языка и списка приложений.
    property var binds: []
    readonly property var shortcuts: Models.describeBinds(binds, Lang.s, desktop.entries)
    property var info: null
    readonly property bool opened: windowLoader.active

    function open(name) {
        var id = Models.resolveSection(name);
        if (id && sections.some(item => item.id === id)) section = id;
        windowLoader.active = true;
        load();
    }
    onSectionChanged: { if (opened) load(); }
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
        renderType: Text.CurveRendering
        Layout.bottomMargin: 4
        color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.headlineFontSize; font.weight: Font.Bold
    }
    component Note: Text {
        renderType: Text.CurveRendering
        Layout.fillWidth: true; Layout.maximumWidth: 640
        Layout.leftMargin: 4
        color: Theme.text2; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
        wrapMode: Text.Wrap
    }
    component Value: Text {
        renderType: Text.CurveRendering
        width: Math.min(implicitWidth, parent && parent.maxChildWidth !== undefined ? parent.maxChildWidth : 300)
        color: Theme.text2; font.family: Theme.sans; font.pixelSize: Theme.fontSize
        horizontalAlignment: Text.AlignRight
        elide: Text.ElideRight
    }
    // Страница раздела с полями: StackLayout растягивает дочерний элемент на всю ширину.
    component Page: Item {
        default property alias content: pageColumn.data
        implicitHeight: pageColumn.implicitHeight + 48
        ColumnLayout {
            id: pageColumn
            x: 28; y: 20
            width: parent.width - 56
            spacing: 18
        }
    }

    LazyLoader {
        id: windowLoader
        active: false
        FloatingWindow {
            title: Lang.s.settingsTitle
            visible: true
            implicitWidth: 940
            implicitHeight: 640
            minimumSize: Qt.size(740, 480)
            color: Theme.windowSurface
            onVisibleChanged: { if (!visible) windowLoader.active = false; }
            Component.onCompleted: Qt.callLater(function() { searchField.forceActiveFocus(); })

            RowLayout {
                anchors.fill: parent
                spacing: 0
                Rectangle {
                    Layout.fillHeight: true
                    Layout.preferredWidth: 232
                    color: Theme.sidebarSurface
                    Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Qt.rgba(0, 0, 0, 0.35) }
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: 10
                        spacing: 10
                        // Поиск разделов: Enter открывает первый найденный.
                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: 28
                            radius: Theme.radiusControl
                            color: Theme.fill
                            RowLayout {
                                anchors.fill: parent; anchors.leftMargin: 8; anchors.rightMargin: 8
                                spacing: 6
                                Icon { name: "search"; size: 16; color: Theme.text3 }
                                TextInput {
                                    id: searchField
                                    Layout.fillWidth: true
                                    renderType: Text.CurveRendering
                                    color: Theme.text
                                    selectionColor: Theme.accent
                                    font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
                                    clip: true
                                    onTextChanged: root.filter = text
                                    onAccepted: { if (root.visibleSections.length) root.section = root.visibleSections[0].id; }
                                    Keys.onDownPressed: navigation.forceActiveFocus()
                                    Accessible.name: Lang.s.settingsSearch
                                    Text {
                                        renderType: Text.CurveRendering
                                        visible: !parent.text
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: Lang.s.settingsSearch
                                        color: Theme.text3
                                        font: parent.font
                                    }
                                }
                            }
                        }
                        ListView {
                            id: navigation
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            spacing: 1
                            model: root.visibleSections
                            currentIndex: root.visibleSections.findIndex(item => item.id === root.section)
                            keyNavigationEnabled: true
                            Accessible.role: Accessible.List
                            Accessible.name: Lang.s.settingsSections
                            Keys.onReturnPressed: root.section = root.visibleSections[currentIndex].id
                            onCurrentIndexChanged: { if (currentIndex >= 0 && activeFocus) root.section = root.visibleSections[currentIndex].id; }
                            delegate: Item {
                                id: navItem
                                required property var modelData
                                required property int index
                                readonly property bool gapBefore: index > 0 && root.visibleSections[index - 1].group !== modelData.group
                                readonly property bool current: root.section === modelData.id
                                width: navigation.width
                                height: 30 + (gapBefore ? 10 : 0)
                                Rectangle {
                                    y: navItem.gapBefore ? 10 : 0
                                    width: parent.width; height: 30
                                    radius: 7
                                    color: navItem.current ? Theme.accent : navArea.containsMouse ? Theme.fill : "transparent"
                                    border.width: navItem.current && navigation.activeFocus ? 2 : 0
                                    border.color: Qt.rgba(1, 1, 1, 0.5)
                                    RowLayout {
                                        anchors.fill: parent; anchors.leftMargin: 8; anchors.rightMargin: 8
                                        spacing: 9
                                        Rectangle {
                                            implicitWidth: 22; implicitHeight: 22; radius: 6
                                            color: navItem.modelData.color
                                            Icon { anchors.centerIn: parent; name: navItem.modelData.symbol; filled: true; size: 15; color: "#ffffff" }
                                        }
                                        Text {
                                            renderType: Text.CurveRendering
                                            Layout.fillWidth: true
                                            text: Lang.s[navItem.modelData.labelKey]
                                            color: navItem.current ? Theme.accentForeground : Theme.text
                                            font.family: Theme.sans; font.pixelSize: Theme.fontSize
                                            elide: Text.ElideRight
                                        }
                                    }
                                    MouseArea {
                                        id: navArea
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.section = navItem.modelData.id
                                    }
                                }
                            }
                        }
                    }
                }
                // Прокручивается только текущая страница: высота StackLayout — наибольшая из всех.
                ScrollView {
                    id: pageScroll
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    rightPadding: ScrollBar.vertical.visible ? ScrollBar.vertical.width + 4 : 0
                    ScrollBar.vertical: ShellScrollBar {}
                    contentWidth: availableWidth
                    contentHeight: pages.children[pages.currentIndex] ? pages.children[pages.currentIndex].implicitHeight : 0
                    StackLayout {
                        id: pages
                        width: pageScroll.availableWidth
                        currentIndex: root.sections.findIndex(item => item.id === root.section)
                        Page {
                            PageTitle { text: Lang.s.settingsNetwork }
                            SettingsGroup {
                                SettingsRow {
                                    fill: true
                                    NetworkControls { width: parent.width; network: root.services.network; compact: false }
                                }
                            }
                        }
                        Page {
                            PageTitle { text: "Bluetooth" }
                            SettingsGroup {
                                SettingsRow {
                                    fill: true
                                    BluetoothControls { width: parent.width; bluetooth: root.services.bluetooth; compact: false }
                                }
                            }
                        }
                        Page {
                            PageTitle { text: Lang.s.settingsAudio }
                            SettingsGroup {
                                SettingsRow {
                                    fill: true
                                    AudioControls { width: parent.width; audio: root.services.audio; compact: false }
                                }
                            }
                        }
                        Page {
                            PageTitle { text: Lang.s.settingsDisplay }
                            SettingsGroup {
                                visible: Quickshell.screens.some(screen => Models.isBuiltinOutput(screen.name))
                                SettingsRow {
                                    label: Lang.s.brightnessLabel
                                    fill: true
                                    BrightnessControls { width: parent.width; brightness: root.services.brightness }
                                }
                            }
                            Note {
                                visible: !Quickshell.screens.some(screen => Models.isBuiltinOutput(screen.name))
                                text: Lang.s.settingsBrightnessNote
                            }
                            SettingsGroup {
                                title: Lang.s.settingsMonitors
                                Repeater {
                                    model: Quickshell.screens
                                    delegate: SettingsRow {
                                        required property var modelData
                                        label: modelData.name + (modelData.model ? " · " + modelData.model : "")
                                        Value { text: modelData.width + "×" + modelData.height }
                                    }
                                }
                            }
                            Note { text: Lang.s.settingsDisplayNote }
                        }
                        Page {
                            PageTitle { text: Lang.s.settingsPower }
                            SettingsGroup {
                                SettingsRow {
                                    fill: true
                                    PowerControls { width: parent.width; power: root.services.power }
                                }
                            }
                        }
                        Page {
                            PageTitle { text: Lang.s.settingsNotifications }
                            SettingsGroup {
                                SettingsRow {
                                    label: Lang.s.notificationsDnd
                                    note: Lang.s.settingsDndNote
                                    ShellSwitch {
                                        checked: root.services.notifications.dnd
                                        onToggled: root.services.notifications.setDnd(checked)
                                        Accessible.name: Lang.s.notificationsDnd
                                    }
                                }
                                SettingsRow {
                                    label: Lang.s.settingsHistory
                                    note: Lang.f(Lang.s.settingsHistoryCount, root.services.notifications.history.length)
                                    ShellButton {
                                        implicitHeight: 26
                                        text: Lang.s.notificationsClearAll
                                        selected: true
                                        enabled: root.services.notifications.history.length > 0
                                        onClicked: root.services.notifications.clearAll()
                                    }
                                }
                            }
                        }
                        Page {
                            id: regionPage
                            // Дата для подписей форматов; обновляется при каждом открытии раздела.
                            property date today: new Date()
                            onVisibleChanged: { if (visible) today = new Date(); }
                            PageTitle { text: Lang.s.settingsRegion }
                            Note { visible: Lang.error !== ""; color: Theme.danger; text: Lang.error }
                            SettingsGroup {
                                SettingsRow {
                                    label: Lang.s.settingsLanguage
                                    note: Lang.s.regionRestartNote
                                    SegmentedControl {
                                        showLabels: true; segmentHeight: 22
                                        model: [{label: Lang.s.languageRu}, {label: Lang.s.languageEn}]
                                        currentIndex: Lang.language === "ru" ? 0 : 1
                                        onActivated: index => Lang.update({language: index === 0 ? "ru" : "en"})
                                    }
                                }
                                SettingsRow {
                                    label: Lang.s.settingsClock
                                    SegmentedControl {
                                        showLabels: true; segmentHeight: 22
                                        model: [{label: Lang.s.clock24}, {label: Lang.s.clock12}]
                                        currentIndex: Lang.clock === "24h" ? 0 : 1
                                        onActivated: index => Lang.update({clock: index === 0 ? "24h" : "12h"})
                                    }
                                }
                                SettingsRow {
                                    label: Lang.s.settingsDateFormat
                                    fill: true
                                    SegmentedControl {
                                        readonly property var formats: ["dmy", "ymd", "mdy"]
                                        showLabels: true; segmentHeight: 22
                                        model: formats.map(format => ({label: Lang.dateIn(regionPage.today, format)}))
                                        currentIndex: formats.indexOf(Lang.date)
                                        onActivated: index => Lang.update({date: formats[index]})
                                    }
                                }
                            }
                            SettingsGroup {
                                title: Lang.s.settingsLayouts
                                SettingsRow {
                                    label: Lang.f(Lang.s.regionOrder, Lang.layouts.map(code => Models.layoutLabel(code, Lang.s)).join(" → "))
                                    note: Lang.f(Lang.s.keyboardCurrent, root.desktop.keyboardLayoutName || root.desktop.keyboardLayout)
                                    fill: true
                                    ShellButton { implicitHeight: 26; selected: true; text: Lang.s.layoutSwap; onClicked: Lang.update({layouts: Lang.layouts.slice().reverse()}) }
                                    ShellButton { implicitHeight: 26; selected: true; text: Lang.s.keyboardNext; onClicked: root.desktop.switchLayout() }
                                }
                                SettingsRow {
                                    label: Lang.s.settingsLayoutToggle
                                    note: Lang.layoutsApplied ? Lang.f(Lang.s.keyboardToggleNote, Models.toggleLabel(Lang.toggle, Lang.s)) : Lang.s.regionLayoutsPending
                                    fill: true
                                    SegmentedControl {
                                        readonly property var toggles: ["grp:lalt_lshift_toggle", "grp:alt_shift_toggle", "grp:ctrl_shift_toggle", "grp:caps_toggle"]
                                        showLabels: true; segmentHeight: 24
                                        model: toggles.map(toggle => ({label: Models.toggleLabel(toggle, Lang.s)}))
                                        currentIndex: toggles.indexOf(Lang.toggle)
                                        onActivated: index => Lang.update({toggle: toggles[index]})
                                    }
                                }
                            }
                        }
                        Page {
                            PageTitle { text: Lang.s.settingsShortcuts }
                            Note { visible: root.shortcuts.length === 0; text: Lang.s.shortcutsUnreadable }
                            SettingsGroup {
                                visible: root.shortcuts.length > 0
                                Repeater {
                                    model: root.shortcuts
                                    delegate: SettingsRow {
                                        required property var modelData
                                        label: modelData.action
                                        Rectangle {
                                            implicitWidth: keysText.implicitWidth + 14; implicitHeight: 22
                                            radius: 5
                                            color: Theme.fill2
                                            border.width: 1; border.color: Theme.hairline
                                            Text {
                                                id: keysText
                                                renderType: Text.CurveRendering
                                                anchors.centerIn: parent
                                                text: modelData.keys
                                                color: Theme.text
                                                font.family: Theme.sans; font.pixelSize: Theme.smallFontSize; font.weight: Font.Medium
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        Page {
                            PageTitle { text: Lang.s.settingsAbout }
                            Note { visible: !root.info; text: Lang.s.aboutLoading }
                            SettingsGroup {
                                visible: !!root.info
                                Repeater {
                                    model: root.info ? [
                                        [Lang.s.aboutSystem, root.info.os], [Lang.s.aboutKernel, root.info.kernel], [Lang.s.aboutHostname, root.info.hostname],
                                        [Lang.s.aboutCpu, root.info.cpu], [Lang.s.aboutMemory, root.info.memoryGb ? root.info.memoryGb + " " + Lang.s.unitGb : null],
                                        ["Hyprland", root.info.hyprland], ["Quickshell", root.info.quickshell]
                                    ] : []
                                    delegate: SettingsRow {
                                        required property var modelData
                                        label: modelData[0]
                                        Value { text: modelData[1] || Lang.s.noData }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
