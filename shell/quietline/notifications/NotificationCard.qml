import QtQuick
import QtQuick.Layouts
import Quickshell
import ".."
import "../controls"

// Карточка уведомления: значок приложения (или картинка уведомления), имя приложения и
// время, заголовок, текст и кнопки действий. Нажатие на карточку — действие по умолчанию;
// крестик в левом верхнем углу появляется при наведении. Критическое — с красной обводкой.
Rectangle {
    id: root
    required property var notification
    property string timeText: ""
    // Подсказка крестика: скрыть карточку или закрыть уведомление.
    property string closeHint: Lang.s.notificationDismiss
    property color surfaceColor: Theme.popupSurface
    signal closeRequested()
    signal activated()
    readonly property var defaultAction: notification ? notification.actions.find(action => action.identifier === "default") || null : null
    readonly property var extraActions: notification ? notification.actions.filter(action => action.identifier !== "default") : []
    readonly property string picture: !notification ? "" : notification.image ? notification.image
        : notification.appIcon ? Quickshell.iconPath(notification.appIcon, true) : ""
    implicitHeight: body.implicitHeight + 24
    radius: Theme.radiusCard
    color: surfaceColor
    border.width: 1
    border.color: notification && notification.urgency === 2 ? Theme.danger : Theme.border
    HoverHandler { id: hover }
    TapHandler {
        onTapped: {
            if (root.defaultAction) root.defaultAction.invoke();
            root.activated();
        }
    }
    RowLayout {
        id: body
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 12; leftMargin: 14; rightMargin: 14 }
        spacing: 11
        Rectangle {
            Layout.alignment: Qt.AlignTop
            Layout.topMargin: 1
            implicitWidth: 34; implicitHeight: 34
            radius: 8
            color: picture.status === Image.Ready ? "transparent" : Theme.fill2
            Image {
                id: picture
                anchors.fill: parent
                source: root.picture
                sourceSize.width: 68; sourceSize.height: 68
                fillMode: Image.PreserveAspectCrop
                smooth: true; mipmap: true
                visible: status === Image.Ready
            }
            Icon { anchors.centerIn: parent; visible: picture.status !== Image.Ready; name: "notifications"; filled: true; size: 19; color: Theme.text2 }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 1
            RowLayout {
                Layout.fillWidth: true
                Text {
                    renderType: Text.CurveRendering
                    Layout.fillWidth: true
                    text: root.notification ? (root.notification.appName || Lang.s.notificationDefaultApp) : ""
                    color: Theme.text2; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
                    elide: Text.ElideRight; textFormat: Text.PlainText
                }
                Text {
                    renderType: Text.CurveRendering
                    text: root.timeText
                    color: Theme.text2; font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
                }
            }
            Text {
                renderType: Text.CurveRendering
                Layout.fillWidth: true
                visible: text.length > 0
                text: root.notification ? root.notification.summary : ""
                color: Theme.text; font.family: Theme.sans; font.pixelSize: Theme.fontSize; font.weight: Font.DemiBold
                wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight; textFormat: Text.PlainText
            }
            Text {
                renderType: Text.CurveRendering
                Layout.fillWidth: true
                visible: text.length > 0
                text: root.notification ? root.notification.body : ""
                color: Qt.rgba(235 / 255, 235 / 255, 245 / 255, 0.82); font.family: Theme.sans; font.pixelSize: Theme.fontSize
                wrapMode: Text.Wrap; maximumLineCount: 4; elide: Text.ElideRight; textFormat: Text.PlainText
                lineHeight: 1.1
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 8
                visible: root.extraActions.length > 0
                spacing: 6
                Repeater {
                    model: root.extraActions
                    delegate: ShellButton {
                        required property var modelData
                        Layout.fillWidth: true; Layout.preferredWidth: 1
                        implicitHeight: 26; radius: 7
                        text: modelData.text
                        font.pixelSize: Theme.smallFontSize
                        selected: true
                        onClicked: modelData.invoke()
                    }
                }
            }
        }
    }
    // Крестик при наведении — в левом верхнем углу, поверх края карточки.
    ShellButton {
        visible: hover.hovered
        x: -6; y: -6
        implicitWidth: 20; implicitHeight: 20
        radius: 10
        symbol: "close"; symbolSize: 13
        foreground: Theme.text2
        hint: root.closeHint
        background: Rectangle {
            radius: 10
            color: Qt.rgba(60 / 255, 60 / 255, 66 / 255, 0.96)
            border.width: 1; border.color: Theme.border
        }
        onClicked: root.closeRequested()
    }
}
