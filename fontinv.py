"""Render the original 8x16 font the way the engine does: FA[code] is the tile
under FB[code], i.e. the code picks a top tile and a bottom tile.
"""
import numpy as np
from PIL import Image

rom = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()
FONT = 0x0F8000
FA = 0x01FA9E
FB = 0x01FB9E


def tile(n):
    b = rom[FONT + n * 16:FONT + n * 16 + 16]
    a = np.frombuffer(b, dtype=np.uint8).astype(np.uint16)
    out = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        p0, p1 = a[y * 2], a[y * 2 + 1]
        for x in range(8):
            out[y, x] = (((p1 >> (7 - x)) & 1) << 1) | ((p0 >> (7 - x)) & 1)
    return out


fa = rom[FA:FA + 256]
fb = rom[FB:FB + 256]
used = set()
sheet = np.zeros((16 * 16, 16 * 8), dtype=np.uint8)
for code in range(256):
    t, b = fb[code], fa[code]
    used.add(t)
    used.add(b)
    r, c = code // 16, code % 16
    sheet[r * 16:r * 16 + 8, c * 8:(c + 1) * 8] = tile(t)
    sheet[r * 16 + 8:r * 16 + 16, c * 8:(c + 1) * 8] = tile(b)
Image.fromarray(sheet * 85).resize((16 * 8 * 2, 16 * 16 * 2), Image.NEAREST).save('hw/font_inventory.png')
print('font tiles referenced:', len(used), 'of 256')
free = sorted(set(range(256)) - used)
print('tiles NOT referenced by any code:', len(free), free[:40])
