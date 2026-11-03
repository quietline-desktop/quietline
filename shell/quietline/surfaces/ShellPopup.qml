import QtQuick
import QtQuick.Effects
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import ".."
import "../logic/Models.js" as Models

// Всплывающее окно панели или дока: полупрозрачная поверхность с тенью, появляется
// затуханием и масштабом от края привязки, закрывается кликом снаружи и Esc, возвращает фокус.
// Окно с `persistent` не закрывается кликом снаружи и не держит клавиатуру исключительно:
// закрытие — Esc и `close()`. Любое окно закрывается само, когда открывается новое окно
// приложения (снимок в Satty, запуск программы): иначе исключительная клавиатура окна панели не
// пустила бы ввод в новое окно. Размер поверхности — `panelWidth` × `panelHeight`, её левый
// верхний угол — `popupX`, `popupY` на экране; вокруг остаётся поле под тень, щелчки в нём
// проходят насквозь. Окно с `windowHeight` больше `panelHeight` держит поверхность слоя этой
// высоты, а `animateHeight` плавно меняет высоту видимой поверхности внутри неё: окно не
// переразмечается, когда содержимое растёт и сжимается.
PanelWindow {
    id: root
    default property alias contents: body.data
    property var parentPanel: null
    property bool reducedMotion: false
    screen: parentPanel ? parentPanel.screen : null
    visible: false
    anchors { top: true; left: true }
    exclusionMode: ExclusionMode.Ignore
    exclusiveZone: 0
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "quietline-popup"
    property bool persistent: false
    WlrLayershell.keyboardFocus: !visible ? WlrKeyboardFocus.None : persistent ? WlrKeyboardFocus.OnDemand : WlrKeyboardFocus.Exclusive
    property real popupX: 0
    property real popupY: 0
    property real panelWidth: 300
    property real panelHeight: 200
    property real windowHeight: panelHeight
    property bool animateHeight: false
    property real padding: 10
    property real radius: Theme.radiusPopup
    property color surfaceColor: Theme.popupSurface
    // Поверхность растёт от верхнего края (под панелью) или от нижнего (над доком).
    property bool fromBottom: false
    readonly property int shadowMargin: 28
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
    margins.left: Math.max(0, popupX - shadowMargin)
    margins.top: Math.max(0, popupY - shadowMargin)
    implicitWidth: frame.x + panelWidth + shadowMargin
    implicitHeight: frame.y + Math.max(windowHeight, frame.height) + shadowMargin
    color: "transparent"
    mask: Region { item: frame }
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
        appear.restart();
        Qt.callLater(function() { body.forceActiveFocus(); root.presented(); });
    }
    function close() { visible = false; }
    // Новое окно приложения: окно панели закрывается, и фокус переходит новому окну — пока
    // клавиатура была у окна панели, Hyprland оставил фокус прежнему окну.
    Connections {
        target: Hyprland
        function onRawEvent(event) {
            if (event.name !== "openwindow" || !root.visible) return;
            root.close();
            var command = Models.focusWindowCommand(String(event.data).split(",")[0]);
            if (command) Qt.callLater(function() { Hyprland.dispatch(command); });
        }
    }
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
        active: root.visible && !root.persistent
        // Перехват снимается и тогда, когда окно само становится `persistent`: закрывает только щелчок снаружи.
        onCleared: { if (!root.persistent) root.close(); }
    },
    RectangularShadow {
        anchors.fill: frame
        radius: root.radius
        blur: 36
        offset.y: 14
        spread: -4
        color: Theme.shadow
        opacity: frame.opacity
        scale: frame.scale
        transformOrigin: frame.transformOrigin
    },
    Rectangle {
        id: frame
        // 0 — только что открыто, 1 — показано; анимируется только появление.
        property real shown: 1
        NumberAnimation { id: appear; target: frame; property: "shown"; from: 0; to: 1; duration: root.reducedMotion ? 0 : Theme.motionDuration; easing.type: Easing.OutCubic }
        x: root.popupX - root.margins.left
        y: root.popupY - root.margins.top
        width: root.panelWidth
        height: root.panelHeight
        Behavior on height {
            enabled: root.animateHeight && root.visible && frame.shown === 1 && !root.reducedMotion
            NumberAnimation { duration: Theme.motionDuration; easing.type: Easing.OutCubic }
        }
        radius: root.radius
        color: root.surfaceColor
        border.width: 1
        border.color: Theme.border
        opacity: shown
        scale: 0.97 + 0.03 * shown
        transformOrigin: root.fromBottom ? Item.Bottom : Item.Top
        FocusScope {
            id: body
            anchors.fill: parent
            anchors.margins: root.padding
            focus: true
            Keys.onEscapePressed: root.close()
        }
    }
    ]
}
