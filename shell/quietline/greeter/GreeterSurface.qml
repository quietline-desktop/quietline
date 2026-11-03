import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import ".."
import "../controls"
import "../lock"

// Экран входа на одном мониторе: обои Quietline, дата и время, раскладка и батарея. На
// мониторе с фокусом — форма входа: инициал, имя (со списком, если пользователей больше
// одного), поле пароля, капсула сеанса (если сеансов больше одного), сообщение и кнопки
// «Перезагрузить» и «Выключить».
PanelWindow {
    id: root
    required property var context
    readonly property string focusedName: Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name
        : (Quickshell.screens.length ? Quickshell.screens[0].name : "")
    readonly property bool main: !!screen && screen.name === focusedName
    // Открытый список: "" | "users" | "sessions".
    property string menu: ""

    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "quietline-greeter"
    WlrLayershell.keyboardFocus: main ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
    color: "#101014"
    onMainChanged: {
        if (!main) menu = "";
        else if (backingWindowVisible) context.markReady();
    }
    onBackingWindowVisibleChanged: if (backingWindowVisible && main) context.markReady()

    Wallpaper { anchors.fill: parent }
    Rectangle { anchors.fill: parent; color: Qt.rgba(0, 0, 0, 0.28) }

    LockStatus { id: keyboardStatus; anchors { top: parent.top; right: parent.right; topMargin: 10; rightMargin: 16 } }

    LockClock {
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height * 0.1
    }

    // Щелчок мимо открытого списка закрывает его.
    MouseArea {
        anchors.fill: parent
        visible: root.menu !== ""
        onClicked: { root.menu = ""; password.forceActiveFocus(); }
    }

    ColumnLayout {
        id: form
        visible: root.main
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom; anchors.bottomMargin: parent.height * 0.09
        width: 260
        spacing: 10
        UserAvatar { Layout.alignment: Qt.AlignHCenter; name: root.context.user ? root.context.user.display : "" }
        Rectangle {
            id: who
            readonly property bool choice: root.context.users.length > 1
            Layout.alignment: Qt.AlignHCenter
            implicitWidth: whoRow.implicitWidth + 16; implicitHeight: 24
            radius: 10
            color: whoArea.containsMouse && choice ? Qt.rgba(1, 1, 1, 0.10) : "transparent"
            RowLayout {
                id: whoRow
                anchors.centerIn: parent
                spacing: 2
                Text {
                    renderType: Text.CurveRendering
                    text: root.context.user ? root.context.user.display : Lang.s.greeterNoUsers
                    color: "#ffffff"
                    font.family: Theme.sans; font.pixelSize: 14; font.weight: Font.DemiBold
                }
                Icon {
                    visible: who.choice
                    name: root.menu === "users" ? "expand_less" : "expand_more"
                    size: 18
                    color: Qt.rgba(1, 1, 1, 0.7)
                }
            }
            MouseArea {
                id: whoArea
                anchors.fill: parent
                hoverEnabled: true
                enabled: who.choice && !root.context.busy
                cursorShape: Qt.PointingHandCursor
                onClicked: root.menu = root.menu === "users" ? "" : "users"
            }
            Accessible.role: Accessible.Button
            Accessible.name: Lang.s.greeterChooseUser
        }
        PasswordField {
            id: password
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 220
            busy: root.context.busy || root.context.dataLoading || root.context.dataFailed
            echo: root.context.echo
            focus: root.main && root.menu === ""
            placeholderText: root.context.busy ? Lang.s.lockChecking
                : (root.context.prompt || Lang.s.password)
            Accessible.name: root.context.user ? Lang.f(Lang.s.greeterPasswordLabel, root.context.user.display)
                : Lang.s.password
            onSubmitted: text => root.context.submit(text)
            Keys.onPressed: event => {
                if (event.key === Qt.Key_Tab && root.context.sessions.length > 1) {
                    root.menu = "sessions";
                    event.accepted = true;
                }
            }
        }
        Text {
            renderType: Text.CurveRendering
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredHeight: 16
            text: keyboardStatus.capsLocked ? Lang.s.greeterCapsLock : ""
            color: "#ffcc66"
            font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
        }
        Rectangle {
            id: sessionChip
            visible: root.context.sessions.length > 1
            Layout.alignment: Qt.AlignHCenter
            implicitWidth: chipRow.implicitWidth + 18; implicitHeight: 22
            radius: 11
            color: chipArea.containsMouse ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(1, 1, 1, 0.10)
            RowLayout {
                id: chipRow
                anchors.centerIn: parent
                spacing: 4
                Text {
                    renderType: Text.CurveRendering
                    text: root.context.session ? root.context.session.name : ""
                    color: Qt.rgba(1, 1, 1, 0.78)
                    font.family: Theme.sans; font.pixelSize: Theme.smallFontSize; font.weight: Font.Medium
                }
                Icon {
                    name: root.menu === "sessions" ? "expand_less" : "expand_more"
                    size: 15
                    color: Qt.rgba(1, 1, 1, 0.78)
                }
            }
            MouseArea {
                id: chipArea
                anchors.fill: parent
                hoverEnabled: true
                enabled: !root.context.busy
                cursorShape: Qt.PointingHandCursor
                onClicked: root.menu = root.menu === "sessions" ? "" : "sessions"
            }
            Accessible.role: Accessible.Button
            Accessible.name: Lang.s.greeterChooseSession
        }
        Text {
            renderType: Text.CurveRendering
            Layout.fillWidth: true
            Layout.minimumHeight: 16
            text: root.context.message
            color: root.context.messageIsError ? "#ff8a80" : Qt.rgba(1, 1, 1, 0.75)
            font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
        }
        ShellButton {
            visible: root.context.dataFailed
            Layout.alignment: Qt.AlignHCenter
            text: Lang.s.retry
            foreground: "#ffffff"
            onClicked: root.context.loadData()
        }
        ShellButton {
            Layout.alignment: Qt.AlignHCenter
            text: Lang.s.greeterTextLogin
            foreground: "#ffffff"
            onClicked: root.context.textLogin()
        }
        Text {
            renderType: Text.CurveRendering
            Layout.alignment: Qt.AlignHCenter
            text: "Ctrl+Alt+Backspace"
            color: Qt.rgba(1, 1, 1, 0.55)
            font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
        }
    }

    GreeterMenu {
        visible: root.menu === "users"
        avatars: true
        x: form.x + (form.width - width) / 2
        y: form.y + who.y - height - 6
        items: root.context.users.map(user => ({ id: user.name, label: user.display }))
        current: root.context.userName
        onChosen: id => { root.context.chooseUser(id); root.menu = ""; password.forceActiveFocus(); }
        onDismissed: { root.menu = ""; password.forceActiveFocus(); }
    }
    GreeterMenu {
        visible: root.menu === "sessions"
        x: form.x + (form.width - width) / 2
        y: form.y + sessionChip.y + sessionChip.height + 6
        items: root.context.sessions.map(item => ({ id: item.id, label: item.name }))
        current: root.context.sessionId
        onChosen: id => { root.context.sessionId = id; root.menu = ""; password.forceActiveFocus(); }
        onDismissed: { root.menu = ""; password.forceActiveFocus(); }
    }

    RowLayout {
        visible: root.main
        anchors { right: parent.right; bottom: parent.bottom; rightMargin: 28; bottomMargin: 28 }
        spacing: 12
        Repeater {
            model: [
                { icon: "restart_alt", label: Lang.s.sessionReboot, action: "reboot" },
                { icon: "power_settings_new", label: Lang.s.sessionPoweroff, action: "poweroff" }
            ]
            Rectangle {
                required property var modelData
                implicitWidth: 40; implicitHeight: 40; radius: 20
                color: powerArea.containsMouse ? Qt.rgba(1, 1, 1, 0.26) : Qt.rgba(1, 1, 1, 0.14)
                Icon { anchors.centerIn: parent; name: modelData.icon; size: 20; color: "#ffffff" }
                MouseArea {
                    id: powerArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.context.power(modelData.action)
                }
                ToolTip.visible: powerArea.containsMouse
                ToolTip.delay: 500
                ToolTip.text: modelData.label
                Accessible.role: Accessible.Button
                Accessible.name: modelData.label
            }
        }
    }
    GreeterPowerDialog {
        anchors.fill: parent
        visible: root.main && root.context.powerAction !== ""
        context: root.context
        onVisibleChanged: if (!visible && root.main) password.forceActiveFocus()
    }
}
