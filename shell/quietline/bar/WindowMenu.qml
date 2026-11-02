import QtQuick
import Quickshell
import ".."
import "../controls"
import "../logic/Models.js" as Models

// Меню окна под названием активного приложения: свернуть, развернуть, перенести на пространство
// монитора, закрыть окно, выйти из приложения. Окно (`window` из `DesktopModel.windows`) задаёт
// панель при открытии, поэтому фокус меню не меняет цель. Как в меню Quietline, при открытии
// строка не подсвечена; стрелка вниз выбирает первую строку.
Column {
    id: root
    required property var desktop
    required property var engine
    property var window: null
    property string appName: ""
    // Номера для «На пространство» и номер текущего пространства окна.
    property var targets: []
    property int currentNumber: 0
    signal done()
    spacing: 0
    readonly property var entry: window ? Models.desktopFor(window.appId || window.className, desktop.entries) : null
    function takeFocus() { root.forceActiveFocus(); }
    Keys.onDownPressed: minimizeRow.forceActiveFocus(Qt.TabFocusReason)
    Keys.onUpPressed: quitRow.forceActiveFocus(Qt.TabFocusReason)

    component Row_: ShellMenuItem {
        width: root.width
        enabled: !!root.window
        Keys.onDownPressed: nextItemInFocusChain(true).forceActiveFocus(Qt.TabFocusReason)
        Keys.onUpPressed: nextItemInFocusChain(false).forceActiveFocus(Qt.TabFocusReason)
    }
    component Separator: Item {
        width: root.width; height: 11
        Rectangle { anchors.centerIn: parent; width: parent.width - 20; height: 1; color: Theme.hairline }
    }

    Row_ {
        id: minimizeRow
        symbol: "minimize"; text: Lang.s.windowMinimize
        onTriggered: { root.done(); root.desktop.minimize(root.window); }
    }
    Row_ {
        symbol: "crop_square"; text: Lang.s.windowMaximize
        onTriggered: { root.done(); root.desktop.toggleMaximize(root.window); }
    }
    Separator {}
    Text {
        renderType: Text.CurveRendering
        leftPadding: 10
        height: 22
        verticalAlignment: Text.AlignVCenter
        text: Lang.s.windowMoveTo
        color: Theme.text2
        font.family: Theme.sans; font.pixelSize: Theme.smallFontSize
    }
    Flow {
        x: 6
        width: root.width - 12
        spacing: 2
        bottomPadding: 2
        Repeater {
            model: root.targets
            delegate: ShellButton {
                required property int modelData
                implicitWidth: 24; implicitHeight: 24
                text: String(modelData)
                hint: Lang.f(Lang.s.barWorkspaceHint, modelData)
                font.pixelSize: Theme.smallFontSize; font.weight: Font.DemiBold
                selected: modelData === root.currentNumber
                enabled: !!root.window && modelData !== root.currentNumber && root.engine.ready && !root.engine.busy
                onClicked: {
                    root.done();
                    root.desktop.focusWindow(root.window);
                    root.engine.moveWindow(modelData);
                }
            }
        }
    }
    Separator {}
    Row_ {
        symbol: "close"; text: Lang.s.windowClose
        onTriggered: { root.done(); root.desktop.closeWindow(root.window); }
    }
    Row_ {
        id: quitRow
        symbol: "logout"; text: Lang.f(Lang.s.windowQuit, root.appName)
        onTriggered: {
            root.done();
            root.desktop.quit(root.entry ? root.entry.id : Models.normalizedId(root.window.appId || root.window.className));
        }
    }
}
