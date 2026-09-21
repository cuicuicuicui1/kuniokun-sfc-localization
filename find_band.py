"""Identify which VRAM tiles produce the coloured band above the dialogue box.

Inputs: the user's 1:1 screenshot (F12) and the snes9x freeze taken at the same
moment (Shift+F1).  Steps:

  1. find the band rectangle in the screenshot (rows/cols holding the band's
     characteristic colours)
  2. find CGRAM inside the freeze's PPU block
  3. brute force: every 8x8 tile in VRAM, 4bpp and 2bpp, x every palette, and
     report the ones that reproduce a block of the band pixel for pixel

    python find_band.py <screenshot.png> <freeze> [outdir]
"""
import sys
import os
from collections import Counter

from PIL import Image

import read_frz

BAND = [(0, 198, 0), (214, 8, 0), (255, 222, 0), (0, 57, 165), (247, 255, 255)]


def rgb555(c):
    r, g, b = c
    return (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)


def find_band(im, x0=128):
    """Rows and columns of the screenshot that hold the band's colours."""
    w, h = im.size
    px = im.load()
    want = set(BAND)
    rows = []
    for y in range(h):
        n = sum(1 for x in range(x0, w) if px[x, y] in want)
        if n > 12:
            rows.append((y, n))
    return rows


def find_cgram(ppu, colours):
    """The 512 byte CGRAM: the window of the PPU block holding the most of the
    band's RGB555 values."""
    want = set(colours)
    best = (0, -1)
    for off in range(0, len(ppu) - 512, 2):
        n = 0
        for k in range(0, 512, 2):
            v = ppu[off + k] | (ppu[off + k + 1] << 8)
            if v in want:
                n += 1
        if n > best[1]:
            best = (off, n)
    return best


def cgram_colours(cgram, pal):
    out = []
    for k in range(16):
        v = cgram[pal * 32 + k * 2] | (cgram[pal * 32 + k * 2 + 1] << 8)
        out.append(((v & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3))
    return out


def tile_4bpp(vram, off):
    """64 pixel values 0..15."""
    out = []
    for y in range(8):
        row = []
        for p in range(2):
            b0 = vram[(off + y * 16 + p * 2) % len(vram)]
            b1 = vram[(off + y * 16 + p * 2 + 1) % len(vram)]
            bp0 = vram[(off + y * 16 + 8 + p * 2) % len(vram)]
            bp1 = vram[(off + y * 16 + 8 + p * 2 + 1) % len(vram)]
            for i in range(7, -1, -1):
                row.append(((b0 >> i) & 1) | (((b1 >> i) & 1) << 1)
                           | (((bp0 >> i) & 1) << 2) | (((bp1 >> i) & 1) << 3))
        out.append(row)
    return out


def tile_2bpp(vram, off):
    out = []
    for y in range(8):
        b0 = vram[(off + y * 2) % len(vram)]
        b1 = vram[(off + y * 2 + 1) % len(vram)]
        row = []
        for i in range(7, -1, -1):
            row.append(((b0 >> i) & 1) | (((b1 >> i) & 1) << 1))
        out.append(row)
    return out


def block(im, x, y):
    px = im.load()
    return [[px[x + i, y + j] for i in range(8)] for j in range(8)]


def main():
    shot, frz = sys.argv[1], sys.argv[2]
    outdir = sys.argv[3] if len(sys.argv) > 3 else 'hw'
    im = Image.open(shot).convert('RGB')
    rows = find_band(im)
    print('band rows (y, hits):', rows)
    if not rows:
        print('no band rows found')
        return
    ys = [y for y, _ in rows]
    top, bot = ys[0], ys[-1]
    px = im.load()
    want = set(BAND)
    xs = [x for x in range(128, im.size[0])
          if any(px[x, y] in want for y in range(top, bot + 1))]
    print('band rect: x %d..%d  y %d..%d' % (xs[0], xs[-1], top, bot))

    sec = dict((t, b) for t, _, b in read_frz.sections(frz))
    vram = sec['VRA']
    ppu = sec['PPU']
    print('sections:', sorted(sec), 'VRAM', len(vram), 'PPU', len(ppu))
    colours = set(rgb555(c) for c in set(im.crop((xs[0], top, xs[-1] + 1,
                                                  bot + 1)).getdata()))
    off, hits = find_cgram(ppu, colours)
    print('CGRAM at PPU+%d (%d colour hits of %d)' % (off, hits, len(colours)))
    cgram = ppu[off:off + 512]
    for pal in range(8):
        cs = cgram_colours(cgram, pal)
        common = [c for c in cs if rgb555(c) in colours]
        if common:
            print('  palette %d shares %d colours with the band: %s'
                  % (pal, len(common), common))

    # The band starts at the top of the strip: take the first 8x8 block that is
    # entirely inside it and entirely opaque.
    bx = ((xs[0] + 7) // 8) * 8
    by = ((top + 7) // 8) * 8
    if by + 8 > bot:
        by = max(top, bot - 7)
    blk = block(im, bx, by)
    print('probe block at (%d,%d):' % (bx, by))
    for row in blk:
        print('   ', ' '.join('%02X%02X%02X' % c for c in row))

    found = []
    for pal in range(8):
        cs = cgram_colours(cgram, pal)
        for t in range(0, len(vram) - 32, 16):
            for bpp, fn in ((4, tile_4bpp), (2, tile_2bpp)):
                if bpp == 4 and t % 32:
                    continue
                pat = fn(vram, t)
                ok = True
                for y in range(8):
                    for x in range(8):
                        if cs[pat[y][x]] != blk[y][x]:
                            ok = False
                            break
                    if not ok:
                        break
                if ok:
                    found.append((t, bpp, pal))
    print('exact matches: %d' % len(found))
    for t, bpp, pal in found[:40]:
        print('   VRAM byte $%04X  tile %d (from $C000: %d)  %dbpp palette %d'
              % (t, t // 32 if bpp == 4 else t // 16, (t - 0xC000) // 16
                 if t >= 0xC000 else -1, bpp, pal))

    # Also dump what the box's own map rows hold, for reference.
    print()
    print('VRAM $F000..$F1FF as words (the box map area):')
    for r in range(32):
        words = [vram[0xF000 + (r * 32 + c) * 2] | (vram[0xF000 + (r * 32 + c) * 2 + 1] << 8)
                 for c in range(32)]
        print('  row %2d: %s' % (r, ' '.join('%04X' % w for w in words)))


if __name__ == '__main__':
    main()
