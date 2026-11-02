import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import ".."
import "../controls"
import "../panels"
import "../inputs"
import "../logic/Models.js" as Models

// Окно «Настройки»: боковая навигация и страницы на тех же компонентах управления,
// что и всплывающие панели, поэтому изменение здесь видно и там.
// `open(section)` открывает раздел по идентификатору (`keyboard` открывает `region`);
// пусто или неизвестно — текущий раздел; уже открытое окно переходит на активное пространство
// и получает фокус. Окно создаётся при открытии и уничтожается при
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
        {id: "appearance", labelKey: "settingsAppearance", symbol: "palette", color: "#5e5ce6", group: 1},
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
    // Масштабы мониторов из `quietline-shell display`: правило монитора → масштаб; монитора нет — «Авто».
    property var scales: ({})
    property string displayError: ""
    property bool scaleApplied: true

    function open(name) {
        var id = Models.resolveSection(name);
        if (id && sections.some(item => item.id === id)) section = id;
        if (opened) raise();
        windowLoader.active = true;
        load();
    }
    // Уже открытое окно — свёрнутое или на другом пространстве — переходит на активное
    // пространство монитора с фокусом и получает фокус. Окно ищется по классу Quickshell и заголовку.
    function raise() {
        var window = desktop.windows.find(item => (item.appId || item.className) === "org.quickshell" && item.title === Lang.s.settingsTitle);
        if (!window) return;
        var monitor = Hyprland.focusedMonitor;
        var here = monitor && monitor.activeWorkspace && window.workspace_id === monitor.activeWorkspace.id;
        if (here) desktop.focusWindow(window);
        else desktop.restore(window, monitor ? monitor.name : "");
    }
    onSectionChanged: { if (opened) load(); }
    function load() {
        if (section === "shortcuts" && !bindsProcess.running) bindsProcess.running = true;
        if (section === "about" && !aboutProcess.running) aboutProcess.running = true;
        if (section === "network") services.network.refresh();
        if (section === "display") {
            Hyprland.refreshMonitors();
            if (!displayReader.running) displayReader.running = true;
        }
    }
    // Масштаб монитора: число или `"auto"`. Выбор виден сразу, ответ записи его подтверждает.
    function setScale(monitor, scale) {
        var output = Models.displayOutput(monitor);
        if (!output || displayWriter.running) return;
        var next = Object.assign({}, scales);
        if (scale === "auto") delete next[output];
        else next[output] = scale;
        scales = next;
        displayError = "";
        displayWriter.command = ["quietline-shell", "display", "--set", JSON.stringify({output: output, scale: scale})];
        displayWriter.running = true;
    }
    function receiveDisplay(text, writing) {
        var data;
        try { data = JSON.parse(text); } catch (_) { data = {error: "quietline-shell returned no JSON"}; }
        if (data.error) {
            displayError = Lang.s.displayScaleFailed + ": " + data.error;
            if (writing) displayReader.running = true;
            return;
        }
        scales = data.scales || {};
        if (writing) {
            scaleApplied = data.applied !== false;
            Hyprland.refreshMonitors();
        }
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
        id: displayReader
        command: ["quietline-shell", "display"]
        stdout: StdioCollector { onStreamFinished: root.receiveDisplay(text, false) }
    }
    Process {
        id: displayWriter
        stdout: StdioCollector { onStreamFinished: root.receiveDisplay(text, true) }
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
                    Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Theme.sidebarDivider }
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
                                    border.color: Theme.accentRing
                                    RowLayout {
                                        anchors.fill: parent; anchors.leftMargin: 8; anchors.rightMargin: 8
                                        spacing: 9
                                        Rectangle {
                                            implicitWidth: 22; implicitHeight: 22; radius: 6
                                            color: navItem.modelData.color
                                            Icon { anchors.centerIn: parent; name: navItem.modelData.symbol; filled: true; size: 15; color: Theme.accentForeground }
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
                // Высота прокрутки — высота текущей страницы.
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
                            NetworkControls { Layout.fillWidth: true; Layout.maximumWidth: 640; network: root.services.network; compact: false }
                        }
                        Page {
                            PageTitle { text: "Bluetooth" }
                            BluetoothControls { Layout.fillWidth: true; Layout.maximumWidth: 640; bluetooth: root.services.bluetooth }
                        }
                        Page {
                            PageTitle { text: Lang.s.settingsAudio }
                            AudioControls { Layout.fillWidth: true; Layout.maximumWidth: 640; audio: root.services.audio }
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
                                // Режим и масштаб мониторов — из Hyprland.
                                Repeater {
                                    model: Hyprland.monitors.values
                                    delegate: SettingsRow {
                                        required property var modelData
                                        symbol: Models.isBuiltinOutput(modelData.name) ? "laptop" : "desktop_windows"
                                        label: Models.isBuiltinOutput(modelData.name) ? Lang.s.displayBuiltin : (modelData.description || modelData.name)
                                        note: modelData.name
                                        Value { text: Lang.f(Lang.s.displayMode, modelData.width, modelData.height, Math.round(modelData.scale * 100)) }
                                    }
                                }
                            }
                            SettingsGroup {
                                title: Lang.s.settingsScale
                                // Монитор — строка с выбором масштаба из тех, что Hyprland применяет без подгонки.
                                Repeater {
                                    model: Hyprland.monitors.values
                                    delegate: SettingsRow {
                                        id: scaleRow
                                        required property var modelData
                                        readonly property var choices: Models.scaleChoices(modelData.width, modelData.height)
                                        readonly property var saved: root.scales[Models.displayOutput(modelData)]
                                        // «Авто» — 0; сохранённый масштаб вне списка — ни один сегмент.
                                        readonly property int savedIndex: {
                                            if (saved === undefined) return 0;
                                            var index = choices.findIndex(scale => Math.abs(scale - saved) < 0.001);
                                            return index < 0 ? -1 : index + 1;
                                        }
                                        label: Models.isBuiltinOutput(modelData.name) ? Lang.s.displayBuiltin : (modelData.description || modelData.name)
                                        note: Lang.s.displayScaleNote
                                        fill: true
                                        SegmentedControl {
                                            showLabels: true; segmentHeight: 24
                                            model: [{label: Lang.s.displayScaleAuto}].concat(scaleRow.choices.map(scale => ({label: Lang.f(Lang.s.displayScalePercent, Math.round(scale * 100))})))
                                            currentIndex: scaleRow.savedIndex
                                            busy: displayWriter.running
                                            onActivated: index => root.setScale(scaleRow.modelData, index === 0 ? "auto" : scaleRow.choices[index - 1])
                                        }
                                    }
                                }
                            }
                            Note { visible: root.displayError !== ""; color: Theme.danger; text: root.displayError }
                            Note { visible: !root.scaleApplied; text: Lang.s.displayScalePending }
                            Note { text: Lang.s.settingsDisplayNote }
                        }
                        Page {
                            PageTitle { text: Lang.s.settingsAppearance }
                            Note { visible: Appearance.error !== ""; color: Theme.danger; text: Appearance.error }
                            SettingsGroup {
                                title: Lang.s.appearanceTheme
                                // Карточки-превью тем: обои, панель, окно и док в миниатюре; выбранная — рамка акцентом.
                                Row {
                                    Layout.margins: 14
                                    spacing: 18
                                    Repeater {
                                        model: [
                                            {theme: "light", labelKey: "appearanceLight", wall: ["#8fb6ec", "#c9b8e6"], bar: Qt.rgba(246 / 255, 246 / 255, 248 / 255, 0.75), window: "#ffffff", title: "#ececef", dock: Qt.rgba(250 / 255, 250 / 255, 252 / 255, 0.6)},
                                            {theme: "dark", labelKey: "appearanceDark", wall: ["#141a3c", "#0e1230"], bar: Qt.rgba(22 / 255, 22 / 255, 26 / 255, 0.7), window: "#1d1d21", title: "#2b2b30", dock: Qt.rgba(40 / 255, 40 / 255, 46 / 255, 0.6)}
                                        ]
                                        delegate: Column {
                                            id: themeCard
                                            required property var modelData
                                            readonly property bool current: Appearance.theme === modelData.theme
                                            spacing: 7
                                            Accessible.role: Accessible.RadioButton
                                            Accessible.name: Lang.s[modelData.labelKey]
                                            Accessible.checked: current
                                            Rectangle {
                                                width: 156; height: 102; radius: 12
                                                color: "transparent"
                                                border.width: 3
                                                border.color: themeCard.current ? Theme.accent : "transparent"
                                                Rectangle {
                                                    anchors.fill: parent; anchors.margins: 3
                                                    radius: 9
                                                    clip: true
                                                    border.width: themeCard.current ? 0 : 1; border.color: Theme.border
                                                    gradient: Gradient {
                                                        GradientStop { position: 0; color: themeCard.modelData.wall[0] }
                                                        GradientStop { position: 1; color: themeCard.modelData.wall[1] }
                                                    }
                                                    Rectangle { width: parent.width; height: 8; color: themeCard.modelData.bar }
                                                    Rectangle {
                                                        x: 18; y: 20; width: 84; height: 56; radius: 5
                                                        color: themeCard.modelData.window
                                                        Rectangle { width: parent.width; height: 9; radius: 5; color: themeCard.modelData.title }
                                                    }
                                                    Rectangle {
                                                        anchors.horizontalCenter: parent.horizontalCenter
                                                        anchors.bottom: parent.bottom; anchors.bottomMargin: 4
                                                        width: 56; height: 10; radius: 4
                                                        color: themeCard.modelData.dock
                                                    }
                                                }
                                                MouseArea {
                                                    anchors.fill: parent
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: { if (!themeCard.current) Appearance.update({theme: themeCard.modelData.theme}); }
                                                }
                                            }
                                            Text {
                                                renderType: Text.CurveRendering
                                                anchors.horizontalCenter: parent.horizontalCenter
                                                text: Lang.s[themeCard.modelData.labelKey]
                                                color: Theme.text
                                                font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
                                                font.weight: themeCard.current ? Font.DemiBold : Font.Normal
                                            }
                                        }
                                    }
                                }
                                SettingsRow {
                                    label: Lang.s.appearanceApps
                                    note: Lang.s.appearanceAppsNote
                                }
                            }
                            SettingsGroup {
                                title: Lang.s.appearancePointer
                                SettingsRow {
                                    label: Lang.s.appearancePointerColor
                                    SegmentedControl {
                                        showLabels: true; segmentHeight: 22
                                        model: [{label: Lang.s.appearancePointerDark}, {label: Lang.s.appearancePointerLight}]
                                        currentIndex: Appearance.cursor === "light" ? 1 : 0
                                        onActivated: index => Appearance.update({cursor: index === 1 ? "light" : "dark"})
                                    }
                                }
                                SettingsRow {
                                    label: Lang.s.appearancePointerSize
                                    SegmentedControl {
                                        readonly property var sizes: [24, 36, 48]
                                        showLabels: true; segmentHeight: 22
                                        model: [{label: Lang.s.appearanceSizeNormal}, {label: Lang.s.appearanceSizeLarge}, {label: Lang.s.appearanceSizeLarger}]
                                        currentIndex: sizes.indexOf(Appearance.cursorSize)
                                        onActivated: index => Appearance.update({cursorSize: sizes[index]})
                                    }
                                }
                            }
                            SettingsGroup {
                                title: Lang.s.appearancePanel
                                SettingsRow {
                                    label: Lang.s.appearanceBatteryPercent
                                    SegmentedControl {
                                        readonly property var modes: ["off", "beside", "inside"]
                                        showLabels: true; segmentHeight: 22
                                        model: [{label: Lang.s.batteryPercentOff}, {label: Lang.s.batteryPercentBeside}, {label: Lang.s.batteryPercentInside}]
                                        currentIndex: modes.indexOf(Appearance.batteryPercent)
                                        onActivated: index => Appearance.update({batteryPercent: modes[index]})
                                    }
                                }
                            }
                            Note { visible: !Appearance.applied; text: Lang.s.appearancePending }
                        }
                        Page {
                            PageTitle { text: Lang.s.settingsPower }
                            PowerControls { Layout.fillWidth: true; Layout.maximumWidth: 640; power: root.services.power }
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
                                SettingsRow {
                                    label: Lang.s.settingsBarDate
                                    fill: true
                                    SegmentedControl {
                                        readonly property var modes: ["short", "numeric", "weekday"]
                                        showLabels: true; segmentHeight: 22
                                        model: modes.map(mode => ({label: Lang.barDay(regionPage.today, mode)}))
                                        currentIndex: modes.indexOf(Lang.barDate)
                                        onActivated: index => Lang.update({barDate: modes[index]})
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
