import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
import "../controls"
import "../inputs"
import "../logic/Models.js" as Models

// Wi-Fi, Ethernet-адаптеры, профили объекта и полоса «Оставить / Вернуть» — группами строк
// по 44 px. Один компонент — и сетевая панель верхней панели (`compact`: не больше шести
// других сетей), и страница «Сеть» окна «Настройки».
// Сети: «Известные» (есть профиль) и «Другие»; строка — имя сети, справа замок защищённой
// сети, сила сигнала и галочка текущей. Нажатие подключает, защищённая сеть без профиля
// сначала спрашивает пароль под строкой. Пока идёт действие, строки не нажимаются.
ColumnLayout {
    id: root
    required property var network
    property bool compact: true
    property string selectedDevice: ""
    property string passwordFor: ""
    property string connectingTo: ""
    property string deleting: ""
    property bool formOpen: false
    property string lastAttempt: ""
    readonly property bool wifiOn: network.wifi.enabled && !!network.wifiDevice
    readonly property var knownNetworks: network.networks.filter(item => item.known || item.active)
    readonly property var otherNetworks: {
        var others = network.networks.filter(item => !item.known && !item.active);
        return compact ? others.slice(0, 6) : others;
    }
    readonly property var adapter: network.ethernet.find(device => device.device === selectedDevice)
        || network.ethernet.find(device => device.cable) || network.ethernet[0] || null
    readonly property var recentProfile: {
        var used = network.profiles.filter(profile => profile.lastUsed && (!adapter || profile.uuid !== adapter.uuid));
        used.sort((a, b) => b.lastUsed - a.lastUsed);
        return used[0] || null;
    }
    spacing: compact ? 12 : 18
    // При открытии ищет сети Wi-Fi, кроме времени отсчёта: тогда «Оставить / Вернуть» остаются доступными.
    Component.onCompleted: { if (network.wifi.enabled && network.wifiDevice && !network.pending) network.scanWifi(); }
    Connections {
        target: root.network
        // Неудачное подключение к защищённой сети снова спрашивает пароль.
        function onErrorMessageChanged() {
            if (root.network.errorMessage && root.network.lastAction === "connect" && root.lastAttempt) root.passwordFor = root.lastAttempt;
        }
        function onBusyChanged() {
            if (root.network.busy) return;
            root.connectingTo = "";
            if (!root.network.errorMessage) root.lastAttempt = "";
        }
    }

    function connect(item) {
        if (network.busy || item.active) return;
        if (!item.known && item.security) { passwordFor = passwordFor === item.ssid ? "" : item.ssid; return; }
        lastAttempt = item.security ? item.ssid : "";
        connectingTo = item.ssid;
        passwordFor = "";
        network.connectWifi(item.ssid, "", "");
    }

    // Небольшая кнопка внутри строки группы.
    component RowButton: ShellButton { implicitHeight: 26; selected: true }
    // Значок справа в строке сети.
    component EndIcon: Icon { size: 16; color: Theme.text2; anchors.verticalCenter: parent ? parent.verticalCenter : undefined }

    component WifiRow: SettingsRow {
        id: wifiRow
        // Встроенный компонент не видит `root`: панель передаётся явно.
        required property var host
        property var item: ({})
        readonly property bool connecting: wifiRow.host.connectingTo === item.ssid && wifiRow.host.network.busy
        label: item.ssid || ""
        labelBold: !!item.active
        note: connecting ? Lang.s.deviceConnecting : ""
        clickable: !item.active && !wifiRow.host.network.busy
        expanded: wifiRow.host.passwordFor === item.ssid
        Accessible.name: (item.ssid || "") + (item.security ? ", " + Lang.s.netSecured : "") + ", " + (item.signal || 0) + "%"
            + (item.active ? ", " + Lang.s.deviceConnected : "")
        onClicked: wifiRow.host.connect(item)
        EndIcon { visible: !!wifiRow.item.security; name: "lock"; filled: true }
        EndIcon { name: Models.wifiSymbol(wifiRow.item.signal || 0); filled: true }
        EndIcon { visible: !!wifiRow.item.active; name: "check"; size: 18; color: Theme.accent; weight: 600 }
        below: RowLayout {
            Layout.fillWidth: true
            spacing: 8
            ShellTextField {
                id: password
                Layout.fillWidth: true
                label: Lang.f(Lang.s.netPasswordFor, wifiRow.item.ssid || "")
                placeholderText: Lang.s.password
                echoMode: TextInput.Password
                onAccepted: { if (join.enabled) join.clicked(); }
                onVisibleChanged: { if (visible) forceActiveFocus(); else clear(); }
                Keys.onEscapePressed: wifiRow.host.passwordFor = ""
            }
            ShellButton {
                id: join
                text: Lang.s.connect
                emphasized: true
                enabled: password.text.length > 0 && !wifiRow.host.network.busy
                onClicked: {
                    wifiRow.host.lastAttempt = wifiRow.item.ssid;
                    wifiRow.host.connectingTo = wifiRow.item.ssid;
                    wifiRow.host.network.connectWifi(wifiRow.item.ssid, password.text, "");
                    password.clear();
                    wifiRow.host.passwordFor = "";
                }
            }
        }
    }

    Text {
        renderType: Text.CurveRendering
        visible: text.length > 0
        Layout.fillWidth: true
        Layout.leftMargin: 4
        text: root.network.errorMessage || root.network.statusError || root.network.notice
        color: root.network.errorMessage || root.network.statusError ? Theme.danger : Theme.text2
        font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
        wrapMode: Text.Wrap
    }

    SettingsGroup {
        visible: !!root.network.pending
        SettingsRow {
            symbol: "history"
            symbolBackground: Theme.accent
            symbolColor: Theme.accentForeground
            label: root.network.secondsLeft >= 0 ? Lang.f(Lang.s.netRevertIn, root.network.secondsLeft) : Lang.s.netUnconfirmed
            fill: true
            RowLayout {
                spacing: 8
                ShellButton { implicitHeight: 26; text: Lang.s.netKeep; emphasized: true; enabled: !root.network.busy; onClicked: root.network.keep() }
                RowButton { text: Lang.s.netRevert; enabled: !root.network.busy; onClicked: root.network.revert() }
            }
        }
    }

    SettingsGroup {
        SettingsRow {
            symbol: root.wifiOn ? "wifi" : "wifi_off"
            symbolBackground: root.network.wifiConnected ? Theme.accent : Theme.fill2
            symbolColor: root.network.wifiConnected ? Theme.accentForeground : Theme.text
            label: "Wi-Fi"
            note: !root.network.wifiDevice ? Lang.s.netNoWifi
                : !root.network.wifi.enabled ? Lang.s.netOff
                : Models.deviceLabel(root.network.wifiDevice, Lang.s)
                  + (root.network.wifiDevice.profile ? " · " + root.network.wifiDevice.profile : "")
                  + " · " + root.network.wifiDevice.device
            ShellSwitch {
                visible: !!root.network.wifiDevice
                checked: root.network.wifi.enabled
                enabled: !root.network.busy
                onToggled: root.network.setWifi(checked)
                Accessible.name: "Wi-Fi"
            }
        }
    }

    SettingsGroup {
        visible: root.wifiOn && root.knownNetworks.length > 0
        title: Lang.s.netKnownNetworks
        Repeater {
            model: root.knownNetworks
            delegate: WifiRow { required property var modelData; host: root; item: modelData }
        }
    }

    SettingsGroup {
        visible: root.wifiOn
        title: Lang.s.netOtherNetworks
        Repeater {
            model: root.otherNetworks
            delegate: WifiRow { required property var modelData; host: root; item: modelData }
        }
        SettingsRow {
            visible: root.otherNetworks.length === 0
            note: root.network.scanning ? Lang.s.netScanning : Lang.s.netNoNetworks
        }
        SettingsRow {
            label: root.network.scanning ? Lang.s.netScanning : Lang.s.netRefresh
            clickable: !root.network.busy
            onClicked: root.network.scanWifi()
            Icon { name: "refresh"; size: 18; color: Theme.text2 }
        }
    }

    SettingsGroup {
        title: Lang.s.netWired
        SettingsRow {
            visible: !root.adapter
            symbol: "lan"
            note: Lang.s.netNoEthernet
        }
        SettingsRow {
            visible: root.network.ethernet.length > 1
            label: Lang.s.netAdapter
            SegmentedControl {
                showLabels: true; segmentHeight: 22
                model: root.network.ethernet.map(device => ({label: device.device, hint: Models.deviceLabel(device, Lang.s)}))
                currentIndex: root.adapter ? root.network.ethernet.findIndex(device => device.device === root.adapter.device) : -1
                onActivated: index => root.selectedDevice = root.network.ethernet[index].device
            }
        }
        SettingsRow {
            visible: !!root.adapter
            symbol: "lan"
            symbolBackground: root.adapter && Models.deviceLabel(root.adapter, Lang.s) === Lang.s.deviceConnected ? Theme.accent : Theme.fill2
            symbolColor: root.adapter && Models.deviceLabel(root.adapter, Lang.s) === Lang.s.deviceConnected ? Theme.accentForeground : Theme.text
            label: root.adapter ? root.adapter.device + " · " + Models.deviceLabel(root.adapter, Lang.s) + (root.adapter.profile ? " · " + root.adapter.profile : "") : ""
            note: root.adapter ? root.adapter.addresses.join(", ")
                + (root.adapter.gateway ? (root.adapter.addresses.length ? " · " : "") + Lang.f(Lang.s.netGateway, root.adapter.gateway) : "") : ""
            fill: root.compact
            Flow {
                id: ethernetActions
                width: root.compact ? parent.width
                     : dhcpButton.implicitWidth + (recentButton.visible ? spacing + recentButton.implicitWidth : 0)
                spacing: 6
                RowButton {
                    id: dhcpButton
                    text: Lang.s.netUseDhcp
                    enabled: !root.network.busy && !root.network.pending
                    onClicked: root.network.useDhcp(root.adapter.device)
                }
                RowButton {
                    id: recentButton
                    visible: !!root.recentProfile
                    text: root.recentProfile ? Lang.f(Lang.s.netApplyRecent, root.recentProfile.name) : ""
                    hint: Lang.s.netRecentProfile
                    enabled: !root.network.busy && !root.network.pending
                    onClicked: root.network.apply(root.recentProfile.uuid, root.adapter.device)
                }
            }
        }
    }

    SettingsGroup {
        title: Lang.s.netSavedProfiles
        Repeater {
            model: root.network.profiles
            delegate: SettingsRow {
                id: profileRow
                required property var modelData
                label: modelData.name
                note: modelData.method === "auto" ? "DHCP" : modelData.address
                      + (modelData.gateway ? " · " + Lang.f(Lang.s.netGateway, modelData.gateway) : "")
                      + (modelData.neverDefault ? " · " + Lang.s.netNoRoute : "")
                RowButton {
                    text: Lang.s.netApply
                    enabled: !!root.adapter && !root.network.busy && !root.network.pending
                    onClicked: root.network.apply(profileRow.modelData.uuid, root.adapter.device)
                }
                RowButton {
                    text: root.deleting === profileRow.modelData.uuid ? Lang.s.netDeleteConfirm : Lang.s.netDelete
                    foreground: root.deleting === profileRow.modelData.uuid ? Theme.danger : Theme.text
                    enabled: !root.network.busy
                    onClicked: {
                        if (root.deleting === profileRow.modelData.uuid) { root.network.deleteProfile(profileRow.modelData.uuid); root.deleting = ""; }
                        else root.deleting = profileRow.modelData.uuid;
                    }
                }
            }
        }
        SettingsRow {
            id: formRow
            label: root.formOpen ? Lang.s.netHideForm : Lang.s.netNewProfile
            clickable: true
            expanded: root.formOpen
            onClicked: root.formOpen = !root.formOpen
            Icon { name: root.formOpen ? "expand_less" : "add"; size: 18; color: Theme.text2 }
            below: ColumnLayout {
                id: form
                Layout.fillWidth: true
                spacing: 8
                property bool manual: true
                ShellTextField { id: profileName; Layout.fillWidth: true; placeholderText: Lang.s.netProfileNamePlaceholder; label: Lang.s.netProfileName }
                SegmentedControl {
                    showLabels: true; segmentHeight: 22
                    model: [{label: Lang.s.netStatic}, {label: "DHCP"}]
                    currentIndex: form.manual ? 0 : 1
                    onActivated: index => form.manual = index === 0
                }
                ShellTextField { id: profileAddress; visible: form.manual; Layout.fillWidth: true; placeholderText: Lang.s.netAddressPlaceholder; label: Lang.s.netAddressLabel }
                ShellTextField { id: profileGateway; visible: form.manual; Layout.fillWidth: true; placeholderText: Lang.s.netGatewayPlaceholder; label: Lang.s.netGatewayLabel }
                ShellTextField { id: profileDns; visible: form.manual; Layout.fillWidth: true; placeholderText: Lang.s.netDnsPlaceholder; label: "DNS" }
                ShellSwitch {
                    id: neverDefault
                    Layout.fillWidth: true
                    checked: true
                    text: Lang.s.netNeverDefault
                }
                ShellButton {
                    Layout.alignment: Qt.AlignRight
                    text: Lang.s.netSaveProfile
                    emphasized: true
                    enabled: profileName.text.trim().length > 0 && !root.network.busy
                    onClicked: {
                        root.network.saveProfile({
                            name: profileName.text, method: form.manual ? "manual" : "auto",
                            // В режиме DHCP адрес, шлюз и DNS не отправляются.
                            address: form.manual ? profileAddress.text.trim() : null,
                            gateway: form.manual ? profileGateway.text.trim() || null : null,
                            dns: form.manual ? profileDns.text.split(",").map(item => item.trim()).filter(Boolean) : [],
                            neverDefault: neverDefault.checked
                        });
                    }
                }
                Connections {
                    target: root.network
                    function onProfileSaved() {
                        profileName.clear(); profileAddress.clear(); profileGateway.clear(); profileDns.clear();
                        neverDefault.checked = true; form.manual = true; root.formOpen = false;
                    }
                }
            }
        }
    }
}
