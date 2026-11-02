import QtQuick
import QtQuick.Controls
import ".."
import "../controls"

// Поле пароля экрана блокировки и экрана входа: капсула со стрелкой отправки справа.
// `submitted(text)` получает введённый текст, поле сразу очищается. `echo` показывает ввод
// открытым текстом (для вопросов PAM, которые не секретны).
TextField {
    id: root
    property bool busy: false
    property bool echo: false
    signal submitted(string text)

    echoMode: echo ? TextInput.Normal : TextInput.Password
    enabled: !busy
    focus: true
    renderType: Text.CurveRendering
    font.family: Theme.sans; font.pixelSize: Theme.fontSize
    color: "#ffffff"; placeholderTextColor: Qt.rgba(1, 1, 1, 0.55)
    selectionColor: Theme.accent
    implicitWidth: 220; implicitHeight: 32
    leftPadding: 14; rightPadding: 34
    background: Rectangle {
        radius: 16
        color: Qt.rgba(1, 1, 1, 0.16)
        border.width: 1
        border.color: root.activeFocus ? Qt.rgba(1, 1, 1, 0.35) : Qt.rgba(1, 1, 1, 0.18)
    }
    Rectangle {
        anchors.right: parent.right; anchors.rightMargin: 5
        anchors.verticalCenter: parent.verticalCenter
        width: 22; height: 22; radius: 11
        color: Qt.rgba(1, 1, 1, root.text.length ? 0.3 : 0.18)
        Icon { anchors.centerIn: parent; name: "arrow_forward"; size: 15; color: "#ffffff" }
        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: root.accepted()
        }
    }
    onAccepted: { var value = root.text; root.clear(); root.submitted(value); }
    Component.onCompleted: forceActiveFocus()
}
