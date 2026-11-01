pragma Singleton
import QtQuick

// Единственный источник цветов, шрифтов, размеров и длительностей оболочки: вариант B
// (docs/design/quiet-line-b.html). Поверхности полупрозрачные, размывает их Hyprland.
QtObject {
    // Текст и акценты.
    readonly property color text: "#f2f2f5"
    readonly property color text2: Qt.rgba(235 / 255, 235 / 255, 245 / 255, 0.62)
    readonly property color text3: Qt.rgba(235 / 255, 235 / 255, 245 / 255, 0.34)
    readonly property color accent: "#0a84ff"
    readonly property color accentForeground: "#ffffff"
    readonly property color danger: "#ff453a"
    readonly property color success: "#30d158"
    readonly property color closeButton: "#e5484d"
    // Поверхности: панель, всплывающие окна, окна по центру (поиск, буфер), окно «Настройки».
    readonly property color barSurface: Qt.rgba(22 / 255, 22 / 255, 26 / 255, 0.50)
    readonly property color popupSurface: Qt.rgba(32 / 255, 32 / 255, 36 / 255, 0.80)
    readonly property color solidSurface: Qt.rgba(32 / 255, 32 / 255, 36 / 255, 0.88)
    readonly property color dockSurface: Qt.rgba(40 / 255, 40 / 255, 46 / 255, 0.5)
    readonly property color windowSurface: "#1f1f23"
    readonly property color sidebarSurface: "#28282d"
    readonly property color scrim: Qt.rgba(0, 0, 0, 0.28)
    // Заливки поверх поверхностей и линии.
    readonly property color fill: Qt.rgba(1, 1, 1, 0.07)
    readonly property color fill2: Qt.rgba(1, 1, 1, 0.11)
    readonly property color fillHover: Qt.rgba(1, 1, 1, 0.14)
    readonly property color fillStrong: Qt.rgba(1, 1, 1, 0.20)
    readonly property color hairline: Qt.rgba(1, 1, 1, 0.08)
    readonly property color border: Qt.rgba(1, 1, 1, 0.11)
    readonly property color shadow: Qt.rgba(0, 0, 0, 0.42)
    // Шрифты: текст — Inter, значки — Material Symbols Rounded (лигатуры), моно — предпросмотр.
    readonly property string sans: "Inter"
    readonly property string symbols: "Material Symbols Rounded"
    readonly property string mono: "JetBrains Mono"
    readonly property int fontSize: 13
    readonly property int smallFontSize: 12
    readonly property int captionFontSize: 11
    readonly property int titleFontSize: 15
    readonly property int headlineFontSize: 20
    readonly property int iconSize: 17
    // Размеры.
    readonly property int barHeight: 30
    readonly property int barItemHeight: 24
    readonly property int popupGap: 4
    readonly property int screenMargin: 6
    readonly property int radiusSmall: 6
    readonly property int radiusControl: 8
    readonly property int radiusRow: 9
    readonly property int radiusModule: 12
    readonly property int radiusPopup: 14
    readonly property int radiusCard: 16
    readonly property int radiusLarge: 18
    readonly property int radiusDock: 20
    readonly property int menuRowHeight: 26
    readonly property int listRowHeight: 44
    readonly property int dockIconSize: 48
    readonly property int dockGap: 6
    readonly property int dockBottom: 6
    readonly property int dockPadding: 8
    // Движение: длительности и кривая выезда; при «уменьшении движения» — 0.
    readonly property int fastDuration: 120
    readonly property int motionDuration: 180
    readonly property int slideDuration: 320
    readonly property int modeDuration: 320
    readonly property var emphasizedCurve: [0.2, 0.9, 0.3, 1, 1, 1]
    readonly property real hoverLift: 4
    readonly property real hoverScale: 1.06
}
