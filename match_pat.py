"""Palette independent tile matching.

For a block of the screenshot, try every 8x8 tile in VRAM (16 byte steps, 2bpp
and 4bpp) and keep the ones whose *pixel index pattern* can be mapped to the
block's colours by some palette, i.e.

    pattern value -> colour  is a function (the palette)
    colour -> pattern value  is injective (a colour never stands for two values)

That needs no CGRAM at all (the freeze does not seem to carry it where I looked).

    python match_pat.py <shot.png> <freeze> <x> <y> [x2 y2 ...]
"""
import sys
from collections import Counter

from PIL import Image

import read_frz
from find_band import tile_4bpp, tile_2bpp


def match(blk, vram, bpp, off):
    pat = tile_2bpp(vram, off) if bpp == 2 else tile_4bpp(vram, off)
    fwd = {}
    rev = {}
    for y in range(8):
        for x in range(8):
            v, c = pat[y][x], blk[y][x]
            if fwd.setdefault(v, c) != c:
                return None
            if rev.setdefault(c, v) != v:
                return None
    return len(fwd)


def main():
    shot, frz = sys.argv[1], sys.argv[2]
    probes = [(int(sys.argv[i]), int(sys.argv[i + 1]))
              for i in range(3, len(sys.argv) - 1, 2)]
    im = Image.open(shot).convert('RGB')
    px = im.load()
    sec = dict((t, b) for t, _, b in read_frz.sections(frz))
    vram = sec['VRA']
    for bx, by in probes:
        blk = [[px[bx + i, by + j] for i in range(8)] for j in range(8)]
        print('probe (%d,%d):' % (bx, by))
        for row in blk:
            print('   ', ' '.join('%02X%02X%02X' % c for c in row))
        hits = Counter()
        for off in range(0, len(vram) - 32, 16):
            for bpp in (2, 4):
                n = match(blk, vram, bpp, off)
                if n is not None and n > 1:
                    hits[(off, bpp, n)] += 1
        if not hits:
            print('    NO MATCH')
        for (off, bpp, n), _ in hits.most_common(12):
            print('    VRAM $%04X (%dbpp, %d distinct values)  from $C000: tile %d'
                  % (off, bpp, n, (off - 0xC000) // 16 if off >= 0xC000 else -1))


if __name__ == '__main__':
    main()
