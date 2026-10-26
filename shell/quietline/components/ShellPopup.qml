import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import ".."

// Всплывающее окно панели или дока: закрывается кликом снаружи и Esc, возвращает фокус.
PanelWindow {
    id: root
    default property alias contents: body.data
    property var parentPanel: null
    screen: parentPanel ? parentPanel.screen : null
    visible: false
    anchors { top: true; left: true }
    exclusionMode: ExclusionMode.Ignore
    exclusiveZone: 0
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: visible ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
    property real popupX: 0
    property real popupY: 0
    readonly property real availableWidth: body.width
    readonly property bool opened: visible
    property Item returnFocus: null
    // Одно всплывающее окно на панель показывает одно содержимое за раз, выбранное по имени.
    property string currentName: ""
    property string closedName: ""
    property real closedAt: 0
    readonly property var hints: hintPopup
    signal presented()
    signal dismissed()
    margins.left: popupX
    margins.top: popupY
    color: "transparent"
    function open(name) {
        if (visible) {
            if (name !== undefined && name !== currentName) { currentName = name; Qt.callLater(function() { body.forceActiveFocus(); root.presented(); }); }
            return;
        }
        if (name !== undefined) currentName = name;
        if (PopupState.current && PopupState.current !== root) PopupState.current.close();
        PopupState.current = root;
        var window = parentPanel;
        returnFocus = window ? window.contentItem.Window.window.activeFocusItem : null;
        visible = true;
        Qt.callLater(function() { body.forceActiveFocus(); root.presented(); });
    }
    function close() { visible = false; }
    // Клик снаружи, который закрывает окно через захват фокуса, доходит и до кнопки,
    // поэтому только что закрытое окно не открывается снова для того же содержимого.
    function toggle(name) {
        if (visible && currentName === name) close();
        else if (!visible && closedName === name && Date.now() - closedAt < 300) return;
        else open(name);
    }
    onVisibleChanged: {
        if (!visible) {
            closedName = currentName;
            closedAt = Date.now();
            hintPopup.hide(null);
            if (PopupState.current === root) PopupState.current = null;
            dismissed();
            if (returnFocus) returnFocus.forceActiveFocus();
        }
    }
    data: [
    HintPopup { id: hintPopup },
    HyprlandFocusGrab {
        windows: [root]
        active: root.visible
        onCleared: root.close()
    },
    Rectangle {
        anchors.fill: parent
        radius: Theme.panelRadius
        color: Theme.surface
        border.width: 1
        border.color: Theme.border
        FocusScope {
            id: body
            anchors.fill: parent
            anchors.margins: 12
            focus: true
            Keys.onEscapePressed: root.close()
        }
    }
    ]
}
