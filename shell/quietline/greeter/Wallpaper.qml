import QtQuick

// Обои Quietline: тёмно-синий диагональный градиент и размытые цветные пятна, как в макетах
// варианта B. Те же значения рисует `config/grub/make-theme.py` для фона меню GRUB.
Canvas {
    id: root
    // Пятна сверху вниз по порядку наложения (первое — верхнее): центр и радиусы в долях
    // экрана, цвет RGB и непрозрачность в центре; к 60 % радиуса пятно прозрачно.
    readonly property var blobs: [
        { x: 0.70, y: 0.30, rx: 0.60, ry: 0.50, rgb: [80, 120, 255], a: 0.55 },
        { x: 0.20, y: 0.80, rx: 0.50, ry: 0.60, rgb: [40, 140, 255], a: 0.45 },
        { x: 0.88, y: 0.78, rx: 0.40, ry: 0.35, rgb: [200, 80, 160], a: 0.35 },
        { x: 0.35, y: 0.25, rx: 0.30, ry: 0.25, rgb: [255, 120, 120], a: 0.18 }
    ]
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onPaint: {
        var ctx = getContext("2d");
        var w = width, h = height;
        // Градиент под углом 160° (0° — вверх, по часовой стрелке), длина линии — как в CSS.
        var angle = 160 * Math.PI / 180;
        var dx = Math.sin(angle), dy = -Math.cos(angle);
        var half = (Math.abs(w * dx) + Math.abs(h * dy)) / 2;
        var base = ctx.createLinearGradient(w / 2 - dx * half, h / 2 - dy * half, w / 2 + dx * half, h / 2 + dy * half);
        base.addColorStop(0, "#141a3c");
        base.addColorStop(0.4, "#1b1f52");
        base.addColorStop(1, "#0e1230");
        ctx.fillStyle = base;
        ctx.fillRect(0, 0, w, h);
        for (var i = blobs.length - 1; i >= 0; i--) {
            var blob = blobs[i];
            var rgb = blob.rgb[0] + "," + blob.rgb[1] + "," + blob.rgb[2];
            ctx.save();
            ctx.translate(blob.x * w, blob.y * h);
            ctx.scale(blob.rx * w, blob.ry * h);
            var spot = ctx.createRadialGradient(0, 0, 0, 0, 0, 1);
            spot.addColorStop(0, "rgba(" + rgb + "," + blob.a + ")");
            spot.addColorStop(0.6, "rgba(" + rgb + ",0)");
            ctx.fillStyle = spot;
            ctx.fillRect(-1, -1, 2, 2);
            ctx.restore();
        }
    }
}
