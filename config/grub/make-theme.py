#!/usr/bin/env python3
"""Собирает тему меню GRUB Quietline в каталог OUTDIR.

Пишет обои `background.png` (те же значения, что у `shell/quietline/greeter/Wallpaper.qml`),
капсулу выбранного пункта `select_*.png` и прозрачную рамку обычного `item_*.png`, подложку консоли `terminal_box_*.png`, шрифты
`.pf2` через `grub-mkfont` (Inter и JetBrains Mono с латиницей, кириллицей, стрелками и
знаками препинания) и темы `theme-ru.txt` / `theme-en.txt` из шаблона `theme.txt.in`.
Имена шрифтов в темах берутся из самих `.pf2`. Нужны только стандартная библиотека Python,
`grub-mkfont` и `fc-query`.

Запуск: `make-theme.py OUTDIR [--inter Inter.ttc] [--mono JetBrainsMono-Regular.ttf]`.
"""

import argparse
import math
import struct
import subprocess
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
WIDTH, HEIGHT = 1920, 1200

# Тексты темы на языках экранов установщика; `%d` — секунды до загрузки.
TEXTS = {
    "ru": {
        "hint": "↑ ↓ — выбор  ·  Enter — загрузить  ·  E — изменить  ·  C — консоль",
        "timeout": "Загрузка через %d с",
    },
    "en": {
        "hint": "↑ ↓ — select  ·  Enter — boot  ·  E — edit  ·  C — console",
        "timeout": "Booting in %d s",
    },
}

# Обои: диагональный градиент 160° и размытые пятна — как в Wallpaper.qml. Пятна сверху вниз
# по порядку наложения: центр и радиусы в долях экрана, цвет и непрозрачность в центре;
# к 60 % радиуса пятно прозрачно.
GRADIENT = [(0.0, (0x14, 0x1A, 0x3C)), (0.4, (0x1B, 0x1F, 0x52)), (1.0, (0x0E, 0x12, 0x30))]
BLOBS = [
    (0.70, 0.30, 0.60, 0.50, (80, 120, 255), 0.55),
    (0.20, 0.80, 0.50, 0.60, (40, 140, 255), 0.45),
    (0.88, 0.78, 0.40, 0.35, (200, 80, 160), 0.35),
    (0.35, 0.25, 0.30, 0.25, (255, 120, 120), 0.18),
]

ACCENT = (0x0A, 0x84, 0xFF, 255)
CAPSULE_RADIUS = 12
# Поле текста консоли gfxterm заливает чёрным сам, тема его цвет не задаёт: поля вокруг тоже
# чёрные, так что консоль занимает весь экран.
TERMINAL = (0, 0, 0, 255)
# Поля консоли вокруг текста: совпадают с terminal-left и terminal-top темы.
TERMINAL_PAD_X, TERMINAL_PAD_Y = 48, 40

# Шрифты: ключ подстановки в шаблоне, файл, начертание, кегль.
FONTS = [
    ("FONT_BRAND", "inter", "SemiBold", 26),
    ("FONT_ITEM", "inter", "Regular", 23),
    ("FONT_SELECTED", "inter", "Medium", 23),
    ("FONT_HINT", "inter", "Regular", 20),
    ("FONT_TIMEOUT", "inter", "Medium", 22),
    ("FONT_MONO", "mono", "Regular", 21),
]
# Латиница, Latin-1 и Latin Extended-A, кириллица, тире, многоточие, кавычки, стрелки;
# моноширинному шрифту консоли — ещё рамки и блоки.
RANGE_TEXT = "0x20-0x7E,0xA0-0x17F,0x400-0x45F,0x2010-0x2026,0x2039-0x203A,0x2190-0x2193"
RANGE_MONO = RANGE_TEXT + ",0x2500-0x259F"

# Матрица Байера 4×4: сдвиг до ±0,5 уровня убирает полосы в плавных градиентах.
BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


def png(path: Path, width: int, height: int, rows: list[bytes], alpha: bool) -> None:
    """Пишет PNG 8 бит на канал: строки — байты RGB или RGBA без байта фильтра."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    header = struct.pack(">IIBBBBB", width, height, 8, 6 if alpha else 2, 0, 0, 0)
    raw = b"".join(b"\x00" + row for row in rows)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
                     + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def gradient_color(t: float) -> tuple[float, float, float]:
    for (t0, c0), (t1, c1) in zip(GRADIENT, GRADIENT[1:]):
        if t <= t1:
            k = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            return tuple(a + (b - a) * k for a, b in zip(c0, c1))
    return tuple(float(v) for v in GRADIENT[-1][1])


def background(path: Path) -> None:
    angle = math.radians(160)
    dx, dy = math.sin(angle), -math.cos(angle)
    half = (abs(WIDTH * dx) + abs(HEIGHT * dy)) / 2
    # Пятна рисуются снизу вверх: последнее в списке — первым.
    blobs = []
    for cx, cy, rx, ry, rgb, a in reversed(BLOBS):
        column = [((x + 0.5 - cx * WIDTH) / (rx * WIDTH)) ** 2 for x in range(WIDTH)]
        blobs.append((cy * HEIGHT, ry * HEIGHT, rgb, a, column))
    rows = []
    for y in range(HEIGHT):
        row = bytearray(WIDTH * 3)
        py = y + 0.5
        spots = [(((py - cy) / ry) ** 2, rgb, a, column) for cy, ry, rgb, a, column in blobs]
        bayer = BAYER[y % 4]
        for x in range(WIDTH):
            t = ((x + 0.5 - WIDTH / 2) * dx + (py - HEIGHT / 2) * dy + half) / (2 * half)
            r, g, b = gradient_color(t)
            for dy2, rgb, a, column in spots:
                d2 = column[x] + dy2
                if d2 < 0.36:
                    k = a * (1 - math.sqrt(d2) / 0.6)
                    r += (rgb[0] - r) * k
                    g += (rgb[1] - g) * k
                    b += (rgb[2] - b) * k
            shift = bayer[x % 4] / 16 - 0.47
            i = x * 3
            row[i] = min(255, max(0, round(r + shift)))
            row[i + 1] = min(255, max(0, round(g + shift)))
            row[i + 2] = min(255, max(0, round(b + shift)))
        rows.append(bytes(row))
    png(path, WIDTH, HEIGHT, rows, alpha=False)


def solid(path: Path, width: int, height: int, rgba: tuple[int, int, int, int]) -> None:
    png(path, width, height, [bytes(rgba) * width] * height, alpha=True)


def corner(path: Path, radius: int, rgba: tuple[int, int, int, int], flip_x: bool, flip_y: bool) -> None:
    """Угол капсулы radius×radius со сглаживанием 4×4 выборки на пиксель."""
    rows = []
    for y in range(radius):
        row = bytearray()
        for x in range(radius):
            inside = 0
            for sy in range(4):
                for sx in range(4):
                    # Координаты от центра скругления: он у внутреннего угла картинки.
                    px = radius - (x + (sx + 0.5) / 4)
                    py = radius - (y + (sy + 0.5) / 4)
                    inside += px * px + py * py <= radius * radius
            row += bytes(rgba[:3]) + bytes([round(rgba[3] * inside / 16)])
        rows.append(bytes(row))
    if flip_y:
        rows.reverse()
    if flip_x:
        rows = [b"".join(row[i:i + 4] for i in range(len(row) - 4, -4, -4)) for row in rows]
    png(path, radius, radius, rows, alpha=True)


def nine_slice(outdir: Path, prefix: str, rgba: tuple[int, int, int, int]) -> None:
    """Рамка из девяти картинок для GRUB: скруглённые углы, поля CAPSULE_RADIUS и центр."""
    r = CAPSULE_RADIUS
    corner(outdir / f"{prefix}_nw.png", r, rgba, flip_x=False, flip_y=False)
    corner(outdir / f"{prefix}_ne.png", r, rgba, flip_x=True, flip_y=False)
    corner(outdir / f"{prefix}_sw.png", r, rgba, flip_x=False, flip_y=True)
    corner(outdir / f"{prefix}_se.png", r, rgba, flip_x=True, flip_y=True)
    solid(outdir / f"{prefix}_n.png", 1, r, rgba)
    solid(outdir / f"{prefix}_s.png", 1, r, rgba)
    solid(outdir / f"{prefix}_w.png", r, 1, rgba)
    solid(outdir / f"{prefix}_e.png", r, 1, rgba)
    solid(outdir / f"{prefix}_c.png", 1, 1, rgba)


def terminal_box(outdir: Path) -> None:
    """Подложка консоли: чёрные поля вокруг текста."""
    sizes = {"nw": (TERMINAL_PAD_X, TERMINAL_PAD_Y), "n": (1, TERMINAL_PAD_Y), "ne": (TERMINAL_PAD_X, TERMINAL_PAD_Y),
             "w": (TERMINAL_PAD_X, 1), "c": (1, 1), "e": (TERMINAL_PAD_X, 1),
             "sw": (TERMINAL_PAD_X, TERMINAL_PAD_Y), "s": (1, TERMINAL_PAD_Y), "se": (TERMINAL_PAD_X, TERMINAL_PAD_Y)}
    for name, (w, h) in sizes.items():
        solid(outdir / f"terminal_box_{name}.png", w, h, TERMINAL)


def face(font: Path, style: str) -> tuple[int, str]:
    """Номер начертания в файле шрифта и имя семейства по имени стиля (`fc-query`)."""
    listing = subprocess.run(["fc-query", "-f", "%{index}\t%{style[0]}\t%{family[0]}\n", str(font)],
                             check=True, capture_output=True, text=True).stdout
    for line in listing.splitlines():
        index, name, family = line.split("\t")
        if name == style:
            return int(index), family
    raise SystemExit(f"error: style {style!r} not found in {font}")


def pf2_name(path: Path) -> str:
    """Имя шрифта из раздела NAME файла `.pf2` — по нему тема GRUB находит шрифт."""
    data = path.read_bytes()
    offset = 0
    while offset + 8 <= len(data):
        kind = data[offset:offset + 4]
        size = struct.unpack(">I", data[offset + 4:offset + 8])[0]
        if kind == b"NAME":
            return data[offset + 8:offset + 8 + size].rstrip(b"\x00").decode()
        if kind == b"CHIX":
            break
        offset += 8 + size
    raise SystemExit(f"error: no font name in {path}")


def fonts(outdir: Path, files: dict[str, Path]) -> dict[str, str]:
    """Шрифты `.pf2`. `grub-mkfont` называет начертание только по флагам жирный/курсив, поэтому
    у Medium и SemiBold имя семейства задаётся явно: «Inter Medium Regular 23»."""
    names = {}
    for key, kind, style, size in FONTS:
        source = files[kind]
        index, family = face(source, style)
        target = outdir / f"{family.replace(' ', '').lower()}-{style.lower()}-{size}.pf2"
        command = ["grub-mkfont", "-s", str(size), "-i", str(index),
                   "-r", RANGE_MONO if kind == "mono" else RANGE_TEXT, "-o", str(target)]
        if style != "Regular":
            command += ["-n", f"{family} {style}"]
        # Предупреждения FreeType о неподдерживаемых свойствах OpenType не мешают сборке.
        result = subprocess.run(command + [str(source)], capture_output=True, text=True)
        if result.returncode != 0:
            sys.stderr.write(result.stderr)
            raise SystemExit(f"error: grub-mkfont failed for {source} {style} {size}")
        names[key] = pf2_name(target)
    if len(set(names.values())) != len(names):
        raise SystemExit(f"error: GRUB font names collide: {names}")
    return names


def themes(outdir: Path, names: dict[str, str]) -> None:
    template = (HERE / "theme.txt.in").read_text()
    for lang, texts in TEXTS.items():
        text = template.replace("@HINT@", texts["hint"]).replace("@TIMEOUT@", texts["timeout"])
        for key, name in names.items():
            text = text.replace(f"@{key}@", name)
        if "@" in text:
            raise SystemExit(f"error: unfilled placeholder in theme-{lang}.txt")
        (outdir / f"theme-{lang}.txt").write_text(text)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Quietline GRUB theme.")
    parser.add_argument("outdir", type=Path)
    parser.add_argument("--inter", type=Path, default=Path("/usr/share/fonts/inter/Inter.ttc"))
    parser.add_argument("--mono", type=Path, default=Path("/usr/share/fonts/TTF/JetBrainsMono-Regular.ttf"))
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)
    names = fonts(args.outdir, {"inter": args.inter, "mono": args.mono})
    background(args.outdir / "background.png")
    # Капсула выбранного пункта и прозрачная рамка обычного с теми же полями.
    nine_slice(args.outdir, "select", ACCENT)
    nine_slice(args.outdir, "item", (0, 0, 0, 0))
    terminal_box(args.outdir)
    themes(args.outdir, names)
    print(f"GRUB theme written to {args.outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
