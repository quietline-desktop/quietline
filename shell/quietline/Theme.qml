pragma Singleton
import QtQuick

// Единственный источник цветов, шрифтов, размеров и длительностей оболочки (см. DESIGN.md).
QtObject {
    readonly property color background: "#101616"
    readonly property color surface: "#202929"
    readonly property color raised: "#34443f"
    readonly property color hover: "#476052"
    readonly property color accent: "#c5ddc9"
    readonly property color accentText: "#13201a"
    readonly property color text: "#e9eee8"
    readonly property color muted: "#9faea5"
    readonly property color border: "#56685e"
    readonly property color danger: "#edb5ad"
    readonly property string sans: "IBM Plex Sans"
    readonly property string icons: "JetBrainsMono Nerd Font Mono"
    readonly property string mono: "IBM Plex Mono"
    readonly property int fontSize: 13
    readonly property int smallFontSize: 11
    readonly property int titleFontSize: 16
    readonly property int iconFontSize: 15
    readonly property int dockGlyphSize: 25
    readonly property int barHeight: 40
    readonly property int outerMargin: 12
    readonly property int controlRadius: 8
    readonly property int panelRadius: 12
    readonly property int dockRadius: 18
    readonly property int dockIconSize: 42
    readonly property int dockGap: 7
    readonly property int dockBottom: 14
    readonly property int motionDuration: 200
    readonly property int hoverDuration: 180
    readonly property int modeDuration: 420
    readonly property int hoverLift: 6
    readonly property real hoverScale: 1.12
}
