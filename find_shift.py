"""Find the pixel shift between the screenshot and the freeze's tiles.

The layers are scrolled, so an 8 aligned probe in the screenshot need not line
up with the tile grid.  For every shift (dx, dy) in 0..7 this extracts the 8x8
block at (x+dx, y+dy) and reports how many VRAM tiles reproduce it.

    python find_shift.py <shot.png> <freeze> <x> <y>
"""
import sys
from collections import Counter

from PIL import Image

import read_frz
from match_pat import match


def main():
    shot, frz = sys.argv[1], sys.argv[2]
    x0, y0 = int(sys.argv[3]), int(sys.argv[4])
    im = Image.open(shot).convert('RGB')
    px = im.load()
    sec = dict((t, b) for t, _, b in read_frz.sections(frz))
    vram = sec['VRA']
    tiles = [(off, bpp) for off in range(0, len(vram) - 32, 16) for bpp in (2, 4)]
    for dy in range(8):
        row = []
        for dx in range(8):
            blk = [[px[x0 + dx + i, y0 + dy + j] for i in range(8)]
                   for j in range(8)]
            hits = [(off, bpp) for off, bpp in tiles
                    if (match(blk, vram, bpp, off) or 0) > 1]
            row.append(len(hits))
            if hits:
                print('  shift (%d,%d): %s' % (dx, dy, [('%04X' % o, b) for o, b in hits[:4]]))
        print('dy=%d counts %s' % (dy, row))


if __name__ == '__main__':
    main()
