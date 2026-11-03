pragma Singleton
import QtQuick
import Quickshell.Hyprland
import "logic/Models.js" as Models

// Единственный источник цветов, шрифтов, размеров и длительностей оболочки: вариант B
// (docs/design/quiet-line-b.html, светлая тема — quiet-line-b-light.html). Цвета зависят от темы
// `Appearance.light`; поверхности полупрозрачные, размывает их Hyprland. Экран блокировки
// цветов отсюда не берёт.
QtObject {
    readonly property bool light: Appearance.light
    // Текст и акценты.
    readonly property color text: light ? "#1d1d1f" : "#f2f2f5"
    readonly property color text2: light ? Qt.rgba(60 / 255, 60 / 255, 67 / 255, 0.68) : Qt.rgba(235 / 255, 235 / 255, 245 / 255, 0.62)
    readonly property color text3: light ? Qt.rgba(60 / 255, 60 / 255, 67 / 255, 0.38) : Qt.rgba(235 / 255, 235 / 255, 245 / 255, 0.34)
    // Основной текст карточки уведомления.
    readonly property color textBody: light ? Qt.rgba(29 / 255, 29 / 255, 31 / 255, 0.82) : Qt.rgba(235 / 255, 235 / 255, 245 / 255, 0.82)
    // Текст и значок поверх заливки цвета `text` (молния в батарее).
    readonly property color textInverse: light ? "#ffffff" : "#1c1c20"
    readonly property color accent: light ? "#007aff" : "#0a84ff"
    readonly property color accentForeground: "#ffffff"
    // Второстепенный текст и значки на акценте; обводка фокуса на акценте.
    readonly property color accentForeground2: Qt.rgba(1, 1, 1, 0.8)
    readonly property color accentRing: Qt.rgba(1, 1, 1, 0.5)
    // Плитка значка на акцентной подсветке (выбранный раздел «Настроек»).
    readonly property color selectedTile: Qt.rgba(1, 1, 1, 0.24)
    // Рамка поля ввода в фокусе.
    readonly property color focusRing: light ? Qt.rgba(0, 122 / 255, 1, 0.7) : Qt.rgba(10 / 255, 132 / 255, 1, 0.7)
    readonly property color danger: light ? "#ff3b30" : "#ff453a"
    readonly property color success: light ? "#34c759" : "#30d158"
    // Предупреждение: низкий заряд, индикатор микрофона и записи экрана.
    readonly property color warning: light ? "#ff9500" : "#ff9f0a"
    // Поверхности: панель, всплывающие окна, окна по центру (поиск, буфер), окно «Настройки».
    // В тёмной теме панели фона нет: текст стоит прямо на обоях.
    readonly property color barSurface: light ? Qt.rgba(246 / 255, 246 / 255, 248 / 255, 0.62) : "transparent"
    readonly property color popupSurface: light ? Qt.rgba(246 / 255, 246 / 255, 248 / 255, 0.82) : Qt.rgba(32 / 255, 32 / 255, 36 / 255, 0.80)
    readonly property color solidSurface: light ? Qt.rgba(246 / 255, 246 / 255, 248 / 255, 0.90) : Qt.rgba(32 / 255, 32 / 255, 36 / 255, 0.88)
    readonly property color solidSurfaceHover: light ? Qt.rgba(232 / 255, 232 / 255, 236 / 255, 0.95) : Qt.rgba(48 / 255, 48 / 255, 54 / 255, 0.92)
    readonly property color dialogSurface: light ? Qt.rgba(246 / 255, 246 / 255, 248 / 255, 0.97) : Qt.rgba(32 / 255, 32 / 255, 36 / 255, 0.97)
    readonly property color tooltipSurface: light ? Qt.rgba(246 / 255, 246 / 255, 248 / 255, 0.95) : Qt.rgba(30 / 255, 30 / 255, 34 / 255, 0.94)
    // Кружок с крестиком над карточкой уведомления.
    readonly property color badgeSurface: light ? Qt.rgba(236 / 255, 236 / 255, 240 / 255, 0.97) : Qt.rgba(60 / 255, 60 / 255, 66 / 255, 0.96)
    readonly property color dockSurface: light ? Qt.rgba(250 / 255, 250 / 255, 252 / 255, 0.5) : Qt.rgba(40 / 255, 40 / 255, 46 / 255, 0.5)
    readonly property color dockBorder: light ? Qt.rgba(1, 1, 1, 0.55) : Qt.rgba(1, 1, 1, 0.14)
    readonly property color dockSeparator: light ? Qt.rgba(0, 0, 0, 0.14) : Qt.rgba(1, 1, 1, 0.18)
    // Точка запущенного приложения под значком дока.
    readonly property color dockIndicator: light ? Qt.rgba(0, 0, 0, 0.55) : Qt.rgba(1, 1, 1, 0.8)
    readonly property color windowSurface: light ? "#ffffff" : "#1f1f23"
    readonly property color sidebarSurface: light ? "#f3f3f6" : "#28282d"
    readonly property color sidebarDivider: light ? Qt.rgba(0, 0, 0, 0.08) : Qt.rgba(0, 0, 0, 0.35)
    readonly property color scrim: light ? Qt.rgba(0, 0, 0, 0.18) : Qt.rgba(0, 0, 0, 0.28)
    // Заливки поверх поверхностей и линии.
    readonly property color fill: light ? Qt.rgba(0, 0, 0, 0.045) : Qt.rgba(1, 1, 1, 0.07)
    readonly property color fill2: light ? Qt.rgba(0, 0, 0, 0.07) : Qt.rgba(1, 1, 1, 0.11)
    readonly property color fillHover: light ? Qt.rgba(0, 0, 0, 0.09) : Qt.rgba(1, 1, 1, 0.14)
    readonly property color fillStrong: light ? Qt.rgba(0, 0, 0, 0.14) : Qt.rgba(1, 1, 1, 0.20)
    // Подложка выбранного сегмента.
    readonly property color segmentSelected: light ? "#ffffff" : Qt.rgba(1, 1, 1, 0.20)
    readonly property color hairline: light ? Qt.rgba(0, 0, 0, 0.08) : Qt.rgba(1, 1, 1, 0.08)
    readonly property color border: light ? Qt.rgba(0, 0, 0, 0.10) : Qt.rgba(1, 1, 1, 0.11)
    // Обводка групп настроек и уведомлений и модулей пункта управления и календаря.
    readonly property color groupBorder: light ? Qt.rgba(0, 0, 0, 0.05) : Qt.rgba(1, 1, 1, 0.05)
    readonly property color moduleBorder: light ? Qt.rgba(0, 0, 0, 0.04) : Qt.rgba(1, 1, 1, 0.04)
    // Нижний край стопки уведомлений одного приложения.
    readonly property color stackEdge: light ? Qt.rgba(0, 0, 0, 0.04) : Qt.rgba(1, 1, 1, 0.045)
    readonly property color shadow: light ? Qt.rgba(0, 0, 0, 0.18) : Qt.rgba(0, 0, 0, 0.42)
    // Ползунки, показатели и полоса прокрутки.
    readonly property color track: light ? Qt.rgba(0, 0, 0, 0.09) : Qt.rgba(1, 1, 1, 0.12)
    readonly property color sliderFill: light ? Qt.rgba(29 / 255, 29 / 255, 31 / 255, 0.72) : "#eef0f4"
    readonly property color knob: "#ffffff"
    readonly property color knobBorder: Qt.rgba(0, 0, 0, 0.12)
    readonly property color scrollHandle: light ? Qt.rgba(0, 0, 0, 0.22) : Qt.rgba(1, 1, 1, 0.22)
    readonly property color scrollHandleActive: light ? Qt.rgba(0, 0, 0, 0.45) : Qt.rgba(1, 1, 1, 0.45)
    // Индикатор громкости и яркости.
    readonly property color osdTrack: light ? Qt.rgba(0, 0, 0, 0.12) : Qt.rgba(1, 1, 1, 0.18)
    readonly property color osdFill: light ? "#1d1d1f" : "#ffffff"
    // Обводка батареи на панели.
    readonly property color batteryOutline: light ? Qt.rgba(0, 0, 0, 0.5) : Qt.rgba(1, 1, 1, 0.5)
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
    // Тип отрисовки текста: при целом масштабе — нативный с хинтингом, при дробном или неизвестном — кривыми.
    // Масштаб берётся у окна Quickshell элемента (`QsWindow.window`), а вне окон Quickshell (экран
    // блокировки) — у монитора `screenName` (`Screen.name`) в Hyprland.
    function textRenderType(window, screenName) {
        return Models.integerScale(window ? window.devicePixelRatio : monitorScale(screenName)) ? Text.NativeRendering : Text.CurveRendering;
    }
    // Масштаб монитора `name` в Hyprland; 0 — монитор не найден.
    function monitorScale(name) {
        var monitor = name ? Hyprland.monitors.values.find(item => item.name === name) : null;
        return monitor ? monitor.scale : 0;
    }
}
