import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import ".."

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
    color: "#101014"

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

    LockStatus { anchors { top: parent.top; right: parent.right; topMargin: 10; rightMargin: 16 } }

    LockClock {
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height * 0.1
    }

    ColumnLayout {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom; anchors.bottomMargin: parent.height * 0.09
        width: 260
        spacing: 10
        UserAvatar { Layout.alignment: Qt.AlignHCenter; name: root.user }
        Text {
            renderType: Theme.textRenderType(QsWindow.window)
            Layout.alignment: Qt.AlignHCenter
            text: root.user.charAt(0).toUpperCase() + root.user.slice(1)
            color: "#ffffff"
            font.family: Theme.sans; font.pixelSize: 14; font.weight: Font.DemiBold
        }
        PasswordField {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 220
            busy: root.context.checking
            placeholderText: root.context.checking ? Lang.s.lockChecking : Lang.s.password
            Accessible.name: Lang.s.lockPasswordLabel
            onSubmitted: text => root.context.submit(text)
        }
        Text {
            renderType: Theme.textRenderType(QsWindow.window)
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
