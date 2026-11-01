import QtQuick
import QtQuick.Controls
import QtQuick.Effects
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import Quickshell.Services.UPower
import Quickshell.Wayland
import ".."
import "../controls"
import "../logic/Models.js" as Models

// Поверхность экрана блокировки на одном экране: размытый снимок экрана, сделанный перед
// блокировкой (`lock-<монитор>.png` в `QUIETLINE_LOCK_BACKDROPS`, файл удаляется сразу
// после загрузки), дата и крупное время, внизу инициал и имя пользователя, поле пароля и
// сообщение PAM; справа сверху — раскладка и батарея.
WlSessionLockSurface {
    id: root
    required property var context
    readonly property string backdrops: Quickshell.env("QUIETLINE_LOCK_BACKDROPS") || ""
    readonly property string user: Quickshell.env("USER") || ""
    readonly property string backdropPath: backdrops && screen ? backdrops + "/lock-" + screen.name + ".png" : ""
    property string layout: ""
    color: "#101014"

    SystemClock { id: clock; precision: SystemClock.Minutes }

    // Раскладка основной клавиатуры; обновляется при её смене.
    Process {
        id: devices
        command: ["hyprctl", "-j", "devices"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var keyboards = JSON.parse(text).keyboards || [];
                    var main = keyboards.find(keyboard => keyboard.main) || keyboards[0] || null;
                    root.layout = main ? Models.layoutCode(main, {}, Lang.s) : "";
                } catch (_) { root.layout = ""; }
            }
        }
    }
    Connections {
        target: Hyprland
        function onRawEvent(event) { if (event.name === "activelayout" && !devices.running) devices.running = true; }
    }

    Image {
        id: backdrop
        anchors.fill: parent
        source: root.backdropPath ? "file://" + root.backdropPath : ""
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        cache: false
        visible: false
        onStatusChanged: {
            if ((status === Image.Ready || status === Image.Error) && root.backdropPath)
                Quickshell.execDetached(["rm", "-f", root.backdropPath]);
        }
    }
    MultiEffect {
        anchors.fill: parent
        source: backdrop
        visible: backdrop.status === Image.Ready
        blurEnabled: true
        blur: 1.0
        blurMax: 64
        brightness: -0.18
        saturation: 0.15
    }
    Rectangle { anchors.fill: parent; color: Qt.rgba(0, 0, 0, 0.18) }

    RowLayout {
        anchors { top: parent.top; right: parent.right; topMargin: 10; rightMargin: 16 }
        spacing: 14
        Rectangle {
            visible: root.layout.length > 0
            implicitWidth: layoutText.implicitWidth + 8; implicitHeight: 16
            radius: 4
            color: "transparent"
            border.width: 1.5; border.color: "#ffffff"
            Text {
                id: layoutText
                renderType: Text.CurveRendering
                anchors.centerIn: parent
                anchors.verticalCenterOffset: 0.75
                text: root.layout
                color: "#ffffff"
                font.family: Theme.sans; font.pixelSize: 10; font.weight: Font.Bold
            }
        }
        Icon {
            visible: !!UPower.displayDevice && UPower.displayDevice.isPresent
            name: UPower.onBattery ? "battery_full" : "battery_charging_full"
            filled: true
            size: 18
        }
    }

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height * 0.1
        spacing: 0
        Text {
            renderType: Text.CurveRendering
            Layout.alignment: Qt.AlignHCenter
            text: Lang.longDate(clock.date)
            color: Qt.rgba(1, 1, 1, 0.88)
            font.family: Theme.sans; font.pixelSize: 20; font.weight: Font.DemiBold
        }
        Text {
            renderType: Text.CurveRendering
            Layout.alignment: Qt.AlignHCenter
            text: Lang.time(clock.date)
            color: Qt.rgba(1, 1, 1, 0.92)
            font.family: Theme.sans; font.pixelSize: 112; font.weight: Font.DemiBold
            font.letterSpacing: -3
            font.features: { "tnum": 1 }
        }
    }

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom; anchors.bottomMargin: parent.height * 0.09
        width: 260
        spacing: 10
        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            implicitWidth: 56; implicitHeight: 56; radius: 28
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: "#6a8cff" }
                GradientStop { position: 1; color: "#b06aff" }
            }
            Text {
                renderType: Text.CurveRendering
                anchors.centerIn: parent
                text: root.user.charAt(0).toUpperCase()
                color: "#ffffff"
                font.family: Theme.sans; font.pixelSize: 22; font.weight: Font.Bold
            }
        }
        Text {
            renderType: Text.CurveRendering
            Layout.alignment: Qt.AlignHCenter
            text: root.user.charAt(0).toUpperCase() + root.user.slice(1)
            color: "#ffffff"
            font.family: Theme.sans; font.pixelSize: 14; font.weight: Font.DemiBold
        }
        TextField {
            id: password
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 220
            echoMode: TextInput.Password
            placeholderText: root.context.checking ? Lang.s.lockChecking : Lang.s.password
            enabled: !root.context.checking
            focus: true
            renderType: Text.CurveRendering
            font.family: Theme.sans; font.pixelSize: Theme.fontSize
            color: "#ffffff"; placeholderTextColor: Qt.rgba(1, 1, 1, 0.55)
            selectionColor: Theme.accent
            implicitHeight: 32
            leftPadding: 14; rightPadding: 34
            Accessible.name: Lang.s.lockPasswordLabel
            background: Rectangle {
                radius: 16
                color: Qt.rgba(1, 1, 1, 0.16)
                border.width: 1
                border.color: password.activeFocus ? Qt.rgba(1, 1, 1, 0.35) : Qt.rgba(1, 1, 1, 0.18)
            }
            // Кнопка входа справа в поле.
            Rectangle {
                anchors.right: parent.right; anchors.rightMargin: 5
                anchors.verticalCenter: parent.verticalCenter
                width: 22; height: 22; radius: 11
                color: Qt.rgba(1, 1, 1, password.text.length ? 0.3 : 0.18)
                Icon { anchors.centerIn: parent; name: "arrow_forward"; size: 15; color: "#ffffff" }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: password.accepted()
                }
            }
            onAccepted: { var text = password.text; password.clear(); root.context.submit(text); }
            Component.onCompleted: forceActiveFocus()
        }
        Text {
            renderType: Text.CurveRendering
            Layout.fillWidth: true
            visible: text.length > 0
            text: root.context.message
            color: root.context.messageIsError ? "#ff8a80" : Qt.rgba(1, 1, 1, 0.75)
            font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
        }
    }
}
