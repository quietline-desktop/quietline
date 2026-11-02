import QtQuick

// Колесо мыши и тачпад над элементом панели: сигнал `step(direction)` на каждые накопленные
// 120 единиц дельты (одно деление колеса); вниз — `1`, вверх — `-1`.
WheelHandler {
    property real accumulated: 0
    signal step(int direction)
    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
    onWheel: event => {
        accumulated += event.angleDelta.y;
        while (Math.abs(accumulated) >= 120) {
            var direction = accumulated > 0 ? -1 : 1;
            accumulated += direction * 120;
            step(direction);
        }
    }
}
