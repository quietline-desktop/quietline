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
// `open(section)` открывает раздел по идентификатору; пусто или неизвестно — текущий раздел.
FloatingWindow {
    id: root
    required property var services
    required property var desktop
    property string section: "network"
    readonly property var sections: [
        {id: "network", label: "Сеть", icon: ""},
        {id: "audio", label: "Звук", icon: ""},
        {id: "display", label: "Экран и яркость", icon: ""},
        {id: "bluetooth", label: "Bluetooth", icon: ""},
        {id: "power", label: "Питание", icon: ""},
        {id: "keyboard", label: "Клавиатура", icon: ""},
        {id: "shortcuts", label: "Сочетания клавиш", icon: ""},
        {id: "about", label: "О системе", icon: ""}
    ]
    property var shortcuts: []
    property var info: null
    title: "Настройки"
    visible: false
    implicitWidth: 920
    implicitHeight: 620
    minimumSize: Qt.size(720, 480)
    color: Theme.background

    function open(name) {
        if (name && sections.some(item => item.id === name)) section = name;
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
                try { root.shortcuts = Models.describeBinds(JSON.parse(text)); }
                catch (_) { root.shortcuts = []; }
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
                Accessible.name: "Разделы настроек"
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
                    PageTitle { text: "Сеть" }
                    NetworkControls { network: root.services.network; compact: false; Layout.fillWidth: true; Layout.maximumWidth: 560 }
                }
                ColumnLayout {
                    Layout.margins: 24; spacing: 14
                    PageTitle { text: "Звук" }
                    AudioControls { audio: root.services.audio; compact: false; Layout.fillWidth: true; Layout.maximumWidth: 560 }
                }
                ColumnLayout {
                    Layout.margins: 24; spacing: 14
                    PageTitle { text: "Экран и яркость" }
                    BrightnessControls {
                        visible: Quickshell.screens.some(screen => Models.isBuiltinOutput(screen.name))
                        brightness: root.services.brightness; Layout.fillWidth: true; Layout.maximumWidth: 560
                    }
                    Line {
                        visible: !Quickshell.screens.some(screen => Models.isBuiltinOutput(screen.name))
                        color: Theme.muted; text: "Яркость подключённых мониторов этим окном не управляется."
                    }
                    Repeater {
                        model: Quickshell.screens
                        delegate: Line {
                            required property var modelData
                            text: modelData.name + " · " + modelData.width + "×" + modelData.height
                                + (modelData.model ? " · " + modelData.model : "")
                        }
                    }
                    Line { color: Theme.muted; font.pixelSize: Theme.smallFontSize; text: "Расположение и разрешение мониторов задаются в конфигурации Hyprland." }
                }
                ColumnLayout {
                    Layout.margins: 24; spacing: 14
                    PageTitle { text: "Bluetooth" }
                    BluetoothControls { bluetooth: root.services.bluetooth; compact: false; Layout.fillWidth: true; Layout.maximumWidth: 560 }
                }
                ColumnLayout {
                    Layout.margins: 24; spacing: 14
                    PageTitle { text: "Питание" }
                    PowerControls { power: root.services.power; Layout.fillWidth: true }
                }
                ColumnLayout {
                    Layout.margins: 24; spacing: 14
                    PageTitle { text: "Клавиатура" }
                    Line { text: "Текущая раскладка: " + (root.desktop.keyboardLayoutName || root.desktop.keyboardLayout) }
                    Line { text: "Раскладки: " + (root.desktop.keyboard && root.desktop.keyboard.layout ? root.desktop.keyboard.layout.split(",").map(item => item.trim().toUpperCase()).join(", ") : "нет данных") }
                    Line { color: Theme.muted; text: "Переключение — левыми Alt+Shift." }
                    ShellButton { text: "Следующая раскладка"; onClicked: root.desktop.switchLayout() }
                }
                ColumnLayout {
                    Layout.margins: 24; spacing: 8
                    PageTitle { text: "Сочетания клавиш" }
                    Line { visible: root.shortcuts.length === 0; color: Theme.muted; text: "Не удалось прочитать привязки Hyprland." }
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
                    PageTitle { text: "О системе" }
                    Repeater {
                        model: root.info ? [
                            ["Система", root.info.os], ["Ядро", root.info.kernel], ["Имя компьютера", root.info.hostname],
                            ["Процессор", root.info.cpu], ["Память", root.info.memoryGb ? root.info.memoryGb + " ГБ" : null],
                            ["Hyprland", root.info.hyprland], ["Quickshell", root.info.quickshell]
                        ] : []
                        delegate: RowLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            Text { Layout.preferredWidth: 160; text: modelData[0]; color: Theme.muted; font.family: Theme.sans; font.pixelSize: Theme.fontSize }
                            Line { text: modelData[1] || "нет данных" }
                        }
                    }
                    Line { visible: !root.info; color: Theme.muted; text: "Сведения загружаются…" }
                }
            }
        }
    }
}
