"""Render the ORIGINAL Japanese font (ROM 0x0F8000, 2bpp tiles) as it is drawn
on screen: for each code, rows 0-7 come from tile FB[code] and rows 8-15 from
tile FA[code].  Produces a contact sheet so the glyphs the engine can still
draw can be read off directly."""
import sys
from PIL import Image, ImageDraw

ROM = 'dl/roms/kuniokun__SF8127.smc'
FONT = 0x0F8000
FA_OFF = 0x01FA9E
FB_OFF = 0x01FB9E

d = open(ROM, 'rb').read()
FA = d[FA_OFF:FA_OFF + 256]
FB = d[FB_OFF:FB_OFF + 256]


def tile(t):
    """8x8 tile, 2bpp, SNES interleaved: byte index y*2+p."""
    px = [[0] * 8 for _ in range(8)]
    base = FONT + t * 16
    for y in range(8):
        b0 = d[base + y * 2]
        b1 = d[base + y * 2 + 1]
        for x in range(8):
            bit = 7 - x
            px[y][x] = ((b0 >> bit) & 1) | (((b1 >> bit) & 1) << 1)
    return px


def glyph(code):
    return tile(FB[code]) + tile(FA[code])


SCALE = 3
CW, CH = 8 * SCALE, 16 * SCALE
COLS = 16
codes = list(range(0x00, 0xE0))
rows = (len(codes) + COLS - 1) // COLS
PAD = 18
img = Image.new('RGB', (COLS * (CW + 4) + 4, rows * (CH + PAD + 4) + 4), (24, 24, 32))
dr = ImageDraw.Draw(img)
for i, c in enumerate(codes):
    gx = 4 + (i % COLS) * (CW + 4)
    gy = 4 + (i // COLS) * (CH + PAD + 4)
    g = glyph(c)
    for y in range(16):
        for x in range(8):
            v = g[y][x]
            col = [(20, 20, 24), (80, 200, 255), (255, 210, 90), (255, 90, 90)][v & 3]
            dr.rectangle([gx + x * SCALE, gy + y * SCALE,
                          gx + x * SCALE + SCALE - 1, gy + y * SCALE + SCALE - 1], fill=col)
    dr.text((gx + 2, gy + CH + 2), '%02X' % c, fill=(200, 200, 200))

out = sys.argv[1] if len(sys.argv) > 1 else 'hw/font_orig.png'
img.save(out)
print('wrote', out, img.size, 'codes 00-DF')

# also: which codes map to a blank glyph (both tiles empty)?
blank = []
for c in range(256):
    if all(v == 0 for row in glyph(c) for v in row):
        blank.append(c)
print('blank codes: %s' % ' '.join('%02X' % c for c in blank))
