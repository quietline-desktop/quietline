import QtQuick
import Quickshell
import Quickshell.Wayland

// «Не засыпать»: пока `active`, оболочка держит запрет простоя Wayland, и hypridle не
// блокирует сеанс, не гасит экран и не усыпляет компьютер. Запрету нужно окно — прозрачный
// слой 1×1 с пустой маской ввода. Состояние не сохраняется: после перезапуска оболочки режим выключен.
Scope {
    id: root
    property bool active: false
    function toggle() { active = !active; }
    PanelWindow {
        id: holder
        anchors { top: true; left: true }
        implicitWidth: 1
        implicitHeight: 1
        color: "transparent"
        mask: Region {}
        exclusionMode: ExclusionMode.Ignore
        exclusiveZone: 0
        WlrLayershell.layer: WlrLayer.Background
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    }
    IdleInhibitor {
        enabled: root.active
        window: holder
    }
}
