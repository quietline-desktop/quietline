import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import "../.."
import "../../controls"
import "../../panels"
import "../../inputs"
import "../frame"
import "../pages"
import "../../logic/Models.js" as Models

// Окно «Настройки»: боковая навигация и страницы на тех же компонентах управления,
// что и всплывающие панели, поэтому изменение здесь видно и там.
// `open(section)` открывает раздел по идентификатору (прежние `time` и `pins` — `datetime` и `dock`);
// пусто или неизвестно — текущий раздел; уже открытое окно переходит на активное пространство
// и получает фокус. Окно создаётся при открытии и уничтожается при
// закрытии: закрытое композитором `FloatingWindow` повторно не показывается. Раздел,
// привязки и сведения о системе живут вне окна и переживают его закрытие.
Scope {
    id: root
    required property var services
    required property var desktop
    property string section: "network"
    // Разделы не зависят от языка: подпись берётся в делегате по `label`, поэтому смена языка
    // не пересоздаёт модель списка и не сбрасывает текущий раздел. `group` — номер группы в
    // боковой панели (между группами — отступ), `color` — цвет квадрата значка. Порядок
    // разделов — порядок страниц в `pages`.
    readonly property var sections: Models.SETTINGS_SECTIONS
    // Строка поиска боковой панели: разделы, в подписи или ключевых словах которых она есть.
    property string filter: ""
    readonly property var visibleSections: sections.filter(item => {
        var needle = filter.trim().toLowerCase();
        if (!needle) return true;
        return (Lang.s[item.label] + " " + (Lang.s[item.keywords] || "")).toLowerCase().indexOf(needle) >= 0;
    })
    // Привязки Hyprland; памятка `shortcuts` пересчитывается из них при смене языка и списка приложений.
    property var binds: []
    readonly property var shortcuts: Models.describeBinds(binds, Lang.s, desktop.entries)
    property var info: null
    readonly property bool opened: windowLoader.active

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
    // Данные разделов окна; страницы из `pages/` перечитывают свои сами при открытии.
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
                                    renderType: Theme.textRenderType(QsWindow.window)
                                    color: Theme.text
                                    selectionColor: Theme.accent
                                    font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
                                    clip: true
                                    onTextChanged: root.filter = text
                                    onAccepted: { if (root.visibleSections.length) root.section = root.visibleSections[0].id; }
                                    Keys.onDownPressed: navigation.forceActiveFocus()
                                    Accessible.name: Lang.s.settingsSearch
                                    Text {
                                        renderType: Theme.textRenderType(QsWindow.window)
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
                                        // Плитка выбранного раздела светлая полупрозрачная: цветная слилась бы с акцентной подсветкой строки.
                                        Rectangle {
                                            implicitWidth: 22; implicitHeight: 22; radius: 6
                                            color: navItem.current ? Theme.selectedTile : navItem.modelData.color
                                            Icon { anchors.centerIn: parent; name: navItem.modelData.symbol; filled: true; size: 15; color: Theme.accentForeground }
                                        }
                                        Text {
                                            renderType: Theme.textRenderType(QsWindow.window)
                                            Layout.fillWidth: true
                                            text: Lang.s[navItem.modelData.label]
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
                        SettingsPage {
                            title: Lang.s.settingsNetwork
                            NetworkControls { Layout.fillWidth: true; network: root.services.network; compact: false }
                        }
                        SettingsPage {
                            title: "Bluetooth"
                            BluetoothControls { Layout.fillWidth: true; bluetooth: root.services.bluetooth }
                        }
                        SettingsPage {
                            title: Lang.s.settingsAudio
                            AudioControls { Layout.fillWidth: true; audio: root.services.audio; full: true }
                        }
                        DisplayPage { brightness: root.services.brightness; display: root.services.display }
                        MousePage {}
                        KeyboardPage { desktop: root.desktop }
                        PowerPage { power: root.services.power }
                        SettingsPage {
                            title: Lang.s.settingsAppearance
                            PageNote { visible: Appearance.error !== ""; color: Theme.danger; text: Appearance.error }
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
                                                renderType: Theme.textRenderType(QsWindow.window)
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
                            PageNote { visible: !Appearance.applied; text: Lang.s.appearancePending }
                        }
                        DockPage { desktop: root.desktop }
                        SettingsPage {
                            title: Lang.s.settingsNotifications
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
                        SettingsPage {
                            id: regionPage
                            // Дата для подписей форматов; обновляется при каждом открытии раздела.
                            property date today: new Date()
                            onOpened: today = new Date()
                            title: Lang.s.settingsRegion
                            PageNote { visible: Lang.error !== ""; color: Theme.danger; text: Lang.error }
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
                        }
                        DateTimePage {}
                        AppsPage {}
                        SettingsPage {
                            title: Lang.s.settingsShortcuts
                            PageNote { visible: root.shortcuts.length === 0; text: Lang.s.shortcutsUnreadable }
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
                                                renderType: Theme.textRenderType(QsWindow.window)
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
                        SettingsPage {
                            title: Lang.s.settingsAbout
                            PageNote { visible: !root.info; text: Lang.s.aboutLoading }
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
                                        PageValue { text: modelData[1] || Lang.s.noData }
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
