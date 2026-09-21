"""Render the game's own text stream as images so it can be read directly.

The renderer at ROM 0x00FC8E maps a text byte 'code' to two tile indices:
    cell = [ FB[code] ][ FA[code] ]   (two consecutive tilemap entries)
so a character occupies a 16x8 area: overlay tile FB[code] and tile FA[code].
We render that overlay as a single 8x8 glyph cell (dakuten sits on the base).
"""
import sys
from PIL import Image, ImageDraw

ROM = 'dl/roms/kuniokun__SF8127.smc'
FONT = 0x0F8000
FA = 0x01FA9E
FB = 0x01FB9E

d = open(ROM, 'rb').read()
fa = d[FA:FA + 256]
fb = d[FB:FB + 256]


def glyph_bits(tile):
    """Return 8 rows of 8 bits (value 1..3) for a 2bpp row-interleaved tile."""
    base = FONT + tile * 16
    rows = []
    for y in range(8):
        p0 = d[base + y * 2]
        p1 = d[base + y * 2 + 1]
        row = 0
        for x in range(8):
            b = ((p0 >> (7 - x)) & 1) | (((p1 >> (7 - x)) & 1) << 1)
            row = (row << 1) | (1 if b else 0)
        rows.append(row)
    return rows


GLYPH = [glyph_bits(t) for t in range(256)]


def draw_cell(px, cell, x0, y0, s, marks):
    """Draw one character cell: overlay FB tile over FA tile."""
    rows = list(GLYPH[cell[1]])
    if cell[0]:
        for y in range(8):
            rows[y] |= GLYPH[cell[0]][y]
    for y in range(8):
        for x in range(8):
            if (rows[y] >> (7 - x)) & 1:
                for dy in range(s):
                    for dx in range(s):
                        px[x0 + x * s + dx, y0 + y * s + dy] = (0, 0, 0)
    if marks:
        for dx in range(s * 8):
            px[x0 + dx, y0 + s * 8 - 1] = (220, 0, 0)


def render_stream(off, length, path, per_row=40, scale=4):
    """Walk a code stream from ROM offset, emitting one cell per character."""
    cells = []
    i = 0
    while i < length:
        c = d[off + i]
        if c == 0xF2:
            nxt = d[off + i + 1]
            cells.append((0, 0, 'ctrl F2%02X' % nxt))
            i += 2
            continue
        cells.append((fb[c], fa[c], '%02X' % c))
        i += 1

    nrow = (len(cells) + per_row - 1) // per_row
    cw, ch = 8 * scale, 8 * scale + 4
    img = Image.new('RGB', (per_row * cw, nrow * ch), (255, 255, 255))
    px = img.load()
    for k, (b, a, tag) in enumerate(cells):
        r, col = divmod(k, per_row)
        draw_cell(px, (b, a), col * cw, r * ch, scale, tag.startswith('ctrl'))
    img.save(path)
    return cells


if __name__ == '__main__':
    off = int(sys.argv[1], 0)
    ln = int(sys.argv[2], 0)
    tag = sys.argv[3]
    per = int(sys.argv[4]) if len(sys.argv) > 4 else 40
    sc = int(sys.argv[5]) if len(sys.argv) > 5 else 4
    cells = render_stream(off, ln, 'txt_%s.png' % tag, per, sc)
    print('rendered %d cells -> txt_%s.png' % (len(cells), tag))
    print('codes:', ' '.join(t for _, _, t in cells[:80]))
