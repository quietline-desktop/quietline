import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
import "../controls"
import "../inputs"
import "../logic/Models.js" as Models

// Wi-Fi, Ethernet-адаптеры, профили объекта и полоса «Оставить / Вернуть».
// Один компонент — и сетевая панель верхней панели, и страница «Сеть» окна «Настройки».
ColumnLayout {
    id: root
    required property var network
    property bool compact: true
    property string selectedDevice: ""
    property string passwordFor: ""
    property string deleting: ""
    property bool formOpen: false
    property string lastAttempt: ""
    readonly property var adapter: network.ethernet.find(device => device.device === selectedDevice)
        || network.ethernet.find(device => device.cable) || network.ethernet[0] || null
    readonly property var recentProfile: {
        var used = network.profiles.filter(profile => profile.lastUsed && (!adapter || profile.uuid !== adapter.uuid));
        used.sort((a, b) => b.lastUsed - a.lastUsed);
        return used[0] || null;
    }
    spacing: 12
    // При открытии ищет сети Wi-Fi, кроме времени отсчёта: тогда «Оставить / Вернуть» остаются доступными.
    Component.onCompleted: { if (network.wifi.enabled && network.wifiDevice && !network.pending) network.scanWifi(); }
    Connections {
        target: root.network
        // Неудачное подключение к защищённой сети снова спрашивает пароль.
        function onErrorMessageChanged() {
            if (root.network.errorMessage && root.network.lastAction === "connect" && root.lastAttempt) root.passwordFor = root.lastAttempt;
        }
        function onBusyChanged() { if (!root.network.busy && !root.network.errorMessage) root.lastAttempt = ""; }
    }

    component SectionTitle: Text {
        renderType: Text.CurveRendering
        color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.fontSize; font.weight: Font.DemiBold
        Layout.topMargin: 4
    }
    component Muted: Text {
        renderType: Text.CurveRendering
        color: Theme.text2; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
        wrapMode: Text.Wrap; Layout.fillWidth: true
    }

    Text {
        renderType: Text.CurveRendering
        visible: text.length > 0
        text: root.network.errorMessage || root.network.statusError || root.network.notice
        color: root.network.errorMessage || root.network.statusError ? Theme.danger : Theme.text
        font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
        wrapMode: Text.Wrap; Layout.fillWidth: true
    }

    Rectangle {
        visible: !!root.network.pending
        Layout.fillWidth: true
        implicitHeight: pendingColumn.implicitHeight + 20
        radius: Theme.radiusControl
        color: Theme.fill2
        border.width: 1; border.color: Theme.accent
        ColumnLayout {
            id: pendingColumn
            anchors.fill: parent; anchors.margins: 10
            spacing: 8
            Muted {
                color: Theme.text
                text: root.network.secondsLeft >= 0
                    ? Lang.f(Lang.s.netRevertIn, root.network.secondsLeft)
                    : Lang.s.netUnconfirmed
            }
            RowLayout {
                spacing: 8
                ShellButton { text: Lang.s.netKeep; emphasized: true; enabled: !root.network.busy; onClicked: root.network.keep() }
                ShellButton { text: Lang.s.netRevert; enabled: !root.network.busy; onClicked: root.network.revert() }
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        SectionTitle { text: "Wi-Fi"; Layout.fillWidth: true }
        ShellSwitch {
            visible: !!root.network.wifiDevice
            text: root.network.wifi.enabled ? Lang.s.netOn : Lang.s.netOff
            checked: root.network.wifi.enabled
            enabled: !root.network.busy
            onToggled: root.network.setWifi(checked)
        }
    }
    Muted {
        visible: !!root.network.wifiDevice
        text: root.network.wifiDevice ? root.network.wifiDevice.device + " · " + Models.deviceLabel(root.network.wifiDevice, Lang.s)
            + (root.network.wifiDevice.profile ? " · " + root.network.wifiDevice.profile : "") : ""
    }
    Muted { visible: !root.network.wifiDevice; text: Lang.s.netNoWifi }
    ColumnLayout {
        visible: root.network.wifi.enabled && !!root.network.wifiDevice
        Layout.fillWidth: true
        spacing: 2
        Repeater {
            model: root.compact ? root.network.networks.slice(0, 6) : root.network.networks
            delegate: ColumnLayout {
                id: wifiRow
                required property var modelData
                Layout.fillWidth: true
                spacing: 4
                ShellButton {
                    Layout.fillWidth: true
                    emphasized: wifiRow.modelData.active
                    text: wifiRow.modelData.ssid + "   " + wifiRow.modelData.signal + "%" + (wifiRow.modelData.security ? "  ·  " + Lang.s.netSecured : "")
                    hint: wifiRow.modelData.active ? Lang.s.deviceConnected : Lang.f(Lang.s.netConnectTo, wifiRow.modelData.ssid)
                    enabled: !root.network.busy && !wifiRow.modelData.active
                    onClicked: {
                        root.lastAttempt = wifiRow.modelData.security ? wifiRow.modelData.ssid : "";
                        if (wifiRow.modelData.known || !wifiRow.modelData.security)
                            root.network.connectWifi(wifiRow.modelData.ssid, "", "");
                        else root.passwordFor = wifiRow.modelData.ssid;
                    }
                }
                RowLayout {
                    visible: root.passwordFor === wifiRow.modelData.ssid
                    Layout.fillWidth: true
                    ShellTextField {
                        id: password
                        Layout.fillWidth: true
                        label: Lang.f(Lang.s.netPasswordFor, wifiRow.modelData.ssid)
                        placeholderText: Lang.s.password
                        echoMode: TextInput.Password
                        onAccepted: connect.clicked()
                        onVisibleChanged: { if (visible) forceActiveFocus(); }
                    }
                    ShellButton {
                        id: connect
                        text: Lang.s.connect
                        enabled: password.text.length > 0 && !root.network.busy
                        onClicked: {
                            root.lastAttempt = wifiRow.modelData.ssid;
                            root.network.connectWifi(wifiRow.modelData.ssid, password.text, "");
                            password.clear();
                            root.passwordFor = "";
                        }
                    }
                }
            }
        }
        ShellButton {
            text: root.network.scanning ? Lang.s.netScanning : Lang.s.netRefresh
            enabled: !root.network.busy
            onClicked: root.network.scanWifi()
        }
    }

    SectionTitle { text: "Ethernet" }
    Muted { visible: !root.adapter; text: Lang.s.netNoEthernet }
    Flow {
        visible: root.network.ethernet.length > 1
        Layout.fillWidth: true
        spacing: 4
        Repeater {
            model: root.network.ethernet
            delegate: ShellButton {
                required property var modelData
                text: modelData.device
                hint: Lang.f(Lang.s.netAdapterHint, modelData.device, Models.deviceLabel(modelData, Lang.s))
                emphasized: root.adapter && root.adapter.device === modelData.device
                onClicked: root.selectedDevice = modelData.device
            }
        }
    }
    ColumnLayout {
        visible: !!root.adapter
        Layout.fillWidth: true
        spacing: 6
        Muted {
            color: Theme.text
            text: root.adapter ? root.adapter.device + " · " + Models.deviceLabel(root.adapter, Lang.s)
                + (root.adapter.profile ? " · " + root.adapter.profile : "")
                + (root.adapter.addresses.length ? "\n" + root.adapter.addresses.join(", ") : "")
                + (root.adapter.gateway ? " · " + Lang.f(Lang.s.netGateway, root.adapter.gateway) : "") : ""
        }
        Flow {
            Layout.fillWidth: true
            spacing: 6
            ShellButton {
                text: Lang.s.netUseDhcp
                enabled: !root.network.busy && !root.network.pending
                onClicked: root.network.useDhcp(root.adapter.device)
            }
            ShellButton {
                visible: !!root.recentProfile
                text: root.recentProfile ? Lang.f(Lang.s.netApplyRecent, root.recentProfile.name) : ""
                hint: Lang.s.netRecentProfile
                enabled: !root.network.busy && !root.network.pending
                onClicked: root.network.apply(root.recentProfile.uuid, root.adapter.device)
            }
        }
    }

    SectionTitle { visible: root.network.profiles.length > 0; text: Lang.s.netSavedProfiles }
    Repeater {
        model: root.network.profiles
        delegate: RowLayout {
            id: profileRow
            required property var modelData
            Layout.fillWidth: true
            spacing: 6
            Muted {
                color: Theme.text
                text: profileRow.modelData.name + "\n" + (profileRow.modelData.method === "auto" ? "DHCP" : profileRow.modelData.address
                      + (profileRow.modelData.gateway ? " · " + Lang.f(Lang.s.netGateway, profileRow.modelData.gateway) : "")
                      + (profileRow.modelData.neverDefault ? " · " + Lang.s.netNoRoute : ""))
            }
            ShellButton {
                text: Lang.s.netApply
                enabled: !!root.adapter && !root.network.busy && !root.network.pending
                onClicked: root.network.apply(profileRow.modelData.uuid, root.adapter.device)
            }
            ShellButton {
                text: root.deleting === profileRow.modelData.uuid ? Lang.s.netDeleteConfirm : Lang.s.netDelete
                enabled: !root.network.busy
                onClicked: {
                    if (root.deleting === profileRow.modelData.uuid) { root.network.deleteProfile(profileRow.modelData.uuid); root.deleting = ""; }
                    else root.deleting = profileRow.modelData.uuid;
                }
            }
        }
    }

    ShellButton {
        text: root.formOpen ? Lang.s.netHideForm : Lang.s.netNewProfile
        onClicked: root.formOpen = !root.formOpen
    }
    ColumnLayout {
        id: form
        visible: root.formOpen
        Layout.fillWidth: true
        spacing: 8
        property bool manual: true
        ShellTextField { id: profileName; Layout.fillWidth: true; placeholderText: Lang.s.netProfileNamePlaceholder; label: Lang.s.netProfileName }
        RowLayout {
            spacing: 6
            ShellButton { text: Lang.s.netStatic; emphasized: form.manual; onClicked: form.manual = true }
            ShellButton { text: "DHCP"; emphasized: !form.manual; onClicked: form.manual = false }
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
