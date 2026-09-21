"""Which VRAM tile + palette is displayed at a given screen block?

Brute force: every 8x8 tile in VRAM (16 byte steps, 2bpp and 4bpp) x every one
of the eight palettes in CGRAM, matched against a block of the screenshot.

    python match_tile.py <shot.png> <freeze> <x> <y> [x2 y2 ...]
"""
import sys
from collections import Counter

from PIL import Image

import read_frz
from find_band import rgb555, find_cgram, cgram_colours, tile_4bpp, tile_2bpp


def main():
    shot, frz = sys.argv[1], sys.argv[2]
    probes = [(int(sys.argv[i]), int(sys.argv[i + 1]))
              for i in range(3, len(sys.argv) - 1, 2)]
    im = Image.open(shot).convert('RGB')
    px = im.load()
    sec = dict((t, b) for t, _, b in read_frz.sections(frz))
    vram = sec['VRA']
    ppu = sec['PPU']
    colours = set(rgb555(px[x, y]) for x in range(im.size[0])
                  for y in range(im.size[1]))
    off, hits = find_cgram(ppu, colours)
    cgram = ppu[off:off + 512]
    print('CGRAM at PPU+%d' % off)

    for bx, by in probes:
        blk = [[px[bx + i, by + j] for i in range(8)] for j in range(8)]
        print('probe (%d,%d):' % (bx, by))
        for row in blk:
            print('   ', ' '.join('%02X%02X%02X' % c for c in row))
        found = Counter()
        for pal in range(8):
            cs = cgram_colours(cgram, pal)
            for t in range(0, len(vram) - 32, 16):
                for bpp, fn in ((2, tile_2bpp), (4, tile_4bpp)):
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
                        found[(t, bpp, pal)] += 1
        if not found:
            print('    NO MATCH')
        for (t, bpp, pal), n in found.most_common(12):
            print('    VRAM $%04X (%dbpp, palette %d)  tile index %d  from $C000 %d'
                  % (t, bpp, pal, t // 16, (t - 0xC000) // 16))


if __name__ == '__main__':
    main()
