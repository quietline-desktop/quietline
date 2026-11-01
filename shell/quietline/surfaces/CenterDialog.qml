import QtQuick
import QtQuick.Effects
import Quickshell
import Quickshell.Wayland
import ".."

// Диалог по центру экрана поверх всего с затемнением: забирает клавиатуру, Esc и щелчок
// по затемнению закрывают его, пока `locked` не запрещает закрытие (например, во время
// завершения приложений). Содержимое — дочерние элементы, ширина карточки — `cardWidth`.
PanelWindow {
    id: root
    default property alias contents: body.data
    property var parentPanel: null
    property real cardWidth: 300
    property bool locked: false
    property bool reducedMotion: false
    readonly property bool opened: visible
    readonly property var hints: null
    signal dismissed()
    screen: parentPanel ? parentPanel.screen : null
    visible: false
    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "quietline-dialog"
    WlrLayershell.keyboardFocus: visible ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
    color: "transparent"
    function open() {
        visible = true;
        appear.restart();
        Qt.callLater(function() { body.forceActiveFocus(); });
    }
    function close() { if (visible) { visible = false; dismissed(); } }
    Rectangle {
        anchors.fill: parent
        color: Theme.scrim
        opacity: card.shown
        MouseArea { anchors.fill: parent; onClicked: { if (!root.locked) root.close(); } }
    }
    RectangularShadow {
        anchors.fill: card
        radius: card.radius
        blur: 40; offset.y: 16; spread: -4
        color: Theme.shadow
        opacity: card.opacity; scale: card.scale
    }
    Rectangle {
        id: card
        property real shown: 1
        NumberAnimation { id: appear; target: card; property: "shown"; from: 0; to: 1; duration: root.reducedMotion ? 0 : Theme.motionDuration; easing.type: Easing.OutCubic }
        anchors.centerIn: parent
        width: root.cardWidth
        height: body.childrenRect.height + 40
        radius: Theme.radiusCard
        // Под диалогом нет размытия Hyprland: карточка почти непрозрачна.
        color: Qt.rgba(32 / 255, 32 / 255, 36 / 255, 0.97)
        border.width: 1; border.color: Theme.border
        opacity: shown
        scale: 0.96 + 0.04 * shown
        // Щелчок по карточке не доходит до затемнения.
        MouseArea { anchors.fill: parent }
        FocusScope {
            id: body
            x: 20; y: 20
            width: parent.width - 40
            height: childrenRect.height
            focus: true
            Keys.onEscapePressed: { if (!root.locked) root.close(); }
        }
    }
}
