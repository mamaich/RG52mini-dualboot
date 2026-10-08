#!/usr/bin/env python3
"""Кадры меню выбора ОС для u-boot RG52 Mini.

    python3 make-menu.py [каталог-вывода]

Рисует альбомный кадр 1280x720, поворачивает его на 90° по часовой стрелке
(панель портретная, 720x1280, так же лежит logo.bmp) и сохраняет 8-битным
BMP со сжатием RLE8: такой формат загрузчик понимает (так сделаны картинки
GammaOS), а файл выходит в десятки килобайт вместо 2,7 МБ.

Имена — те, что ищет board/rockchip/evb_rk3562/rg52_bootmenu.c:
    bootmenu_<n>.bmp    три пункта, выделен n (0 GammaOS, 1 dArkOS, 2 eMMC)
    bootmenu_<n>t.bmp   то же с подсказкой про автозапуск (пункт по умолчанию)
    bootmenu2_<n>[t].bmp  то же без пункта eMMC (на FAT GammaOS нет
                        файла bootmenu_emmc — выключен переключатель в Toolbox)
Рядом кладутся preview_*.png для просмотра на ПК.

Надписи на экране — по-английски (как и весь вывод на устройстве).
"""
import glob
import os
import struct
import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
TIMEOUT_S = 5

BG = (16, 17, 20)
CARD = (34, 36, 42)
CARD_SEL = (255, 166, 0)
TEXT = (235, 235, 235)
TEXT_DIM = (150, 152, 160)
TEXT_SEL = (20, 20, 22)
SUB_SEL = (70, 45, 0)

ITEMS = [
    ("GammaOS Next", "Android 14"),
    ("dArkOS", "Linux  ·  EmulationStation"),
    ("Internal memory", "firmware on the eMMC"),
]

FONT_DIR = "/usr/share/fonts/truetype/dejavu"


def font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


F_TITLE = font("DejaVuSans-Bold.ttf", 44)
F_ITEM = font("DejaVuSans-Bold.ttf", 46)
F_SUB = font("DejaVuSans.ttf", 26)
F_HINT = font("DejaVuSans.ttf", 26)
F_TIMER = font("DejaVuSans.ttf", 28)


def draw_frame(items, sel, countdown):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)

    d.text((W // 2, 70), "Choose a system", font=F_TITLE, fill=TEXT,
           anchor="mm")

    card_w, card_h, gap = 760, 130, 26
    x0 = (W - card_w) // 2
    # блок карточек — по центру между заголовком и подсказками
    y0 = 140 + (3 - len(items)) * (card_h + gap) // 2
    for i, (name, sub) in enumerate(items):
        y = y0 + i * (card_h + gap)
        selected = i == sel
        d.rounded_rectangle((x0, y, x0 + card_w, y + card_h), radius=22,
                            fill=CARD_SEL if selected else CARD)
        d.text((x0 + 48, y + 46), name, font=F_ITEM,
               fill=TEXT_SEL if selected else TEXT, anchor="lm")
        d.text((x0 + 48, y + 96), sub, font=F_SUB,
               fill=SUB_SEL if selected else TEXT_DIM, anchor="lm")
        if selected:
            # стрелка-указатель слева от карточки
            cx, cy = x0 - 34, y + card_h // 2
            d.polygon([(cx - 14, cy - 18), (cx + 12, cy), (cx - 14, cy + 18)],
                      fill=CARD_SEL)

    if countdown:
        d.text((W // 2, y0 + len(items) * (card_h + gap) + 16),
               f"Starts automatically in {TIMEOUT_S} seconds",
               font=F_TIMER, fill=CARD_SEL, anchor="mm")

    d.text((W // 2, H - 44),
           "Up / Down or Vol + / -  to choose      A, Start or Power  to boot",
           font=F_HINT, fill=TEXT_DIM, anchor="mm")
    return im


def rle8(rows, width):
    """Строки снизу вверх -> поток RLE8 (только кодированные серии)."""
    out = bytearray()
    for row in rows:
        x = 0
        while x < width:
            v = row[x]
            n = 1
            while x + n < width and n < 255 and row[x + n] == v:
                n += 1
            out += bytes((n, v))
            x += n
        out += b"\x00\x00"          # конец строки
    out[-2:] = b"\x00\x01"          # последний конец строки -> конец картинки
    return bytes(out)


def save_bmp_rle8(im, path):
    """im — режим P (палитра <= 256 цветов)."""
    w, h = im.size
    pal = im.getpalette()[:256 * 3]
    pal += [0] * (256 * 3 - len(pal))
    px = im.tobytes()
    rows = [px[(h - 1 - y) * w:(h - y) * w] for y in range(h)]
    data = rle8(rows, w)

    palette = b"".join(struct.pack("<BBBB", pal[i * 3 + 2], pal[i * 3 + 1],
                                   pal[i * 3], 0) for i in range(256))
    off = 14 + 40 + len(palette)
    hdr = struct.pack("<2sIHHI", b"BM", off + len(data), 0, 0, off)
    info = struct.pack("<IiiHHIIiiII", 40, w, h, 1, 8, 1, len(data),
                       2835, 2835, 256, 0)
    with open(path, "wb") as f:
        f.write(hdr + info + palette + data)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "out")
    os.makedirs(out, exist_ok=True)
    for name in glob.glob(os.path.join(out, "*")):
        os.remove(name)
    frames = [(prefix, items, sel, countdown)
              for prefix, items in (("bootmenu", ITEMS),
                                    ("bootmenu2", ITEMS[:2]))
              for sel in range(len(items))
              for countdown in (False, True)]
    for prefix, items, sel, countdown in frames:
        land = draw_frame(items, sel, countdown)
        suffix = "t" if countdown else ""
        land.save(os.path.join(out, f"preview_{prefix}_{sel}{suffix}.png"))
        # 90° по часовой стрелке, как logo.bmp
        port = land.transpose(Image.Transpose.ROTATE_270)
        pal = port.quantize(colors=64, method=Image.Quantize.MEDIANCUT,
                            dither=Image.Dither.NONE)
        name = os.path.join(out, f"{prefix}_{sel}{suffix}.bmp")
        save_bmp_rle8(pal, name)
        print(f"{name}: {os.path.getsize(name)} байт")


if __name__ == "__main__":
    main()
