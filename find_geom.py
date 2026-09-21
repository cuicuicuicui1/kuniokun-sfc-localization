"""Locate the character grid in a scaled emulator screenshot by brute force.

The screenshot's scale/offset are unknown, so instead of guessing we search for the
(sx, sy, dx, dy) that makes the largest number of character cells match a known
bitmap *exactly* -- either one of my Chinese pool glyphs or one of the 256 original
Japanese font glyphs.  A correct geometry produces many exact matches; a wrong one
produces none, so the winning configuration is self-validating.

Self test: hw/v29a_f01390.png is native 256x224 and was already proven pixel exact,
so (1,1,0,0) must score the five pool cells of 猪肉包一个 plus three original-font
cells (り き ':'), i.e. 5 + 3 = 8 exact cells.
"""
import sys, json, os
from PIL import Image
import cnbuild5 as cb
from decode_shot import mask_from_pool32, as_bits, load_tables

BASE = os.path.dirname(os.path.abspath(__file__))
NATIVE_W, NATIVE_H = 256, 224
TEXT_X0, TEXT_Y0 = 24, 183
USER = ("C:/Users/<user>/.zcode/cli/image-cache/"
        "sess_2d6e90fa-48ba-457c-9ffa-65d2cb3a2d7a/image-29129c7e5361e3776ae9e09dd4a1ea0f.png")


def cell_mask(px, ox, oy, sx, sy, col, row, thresh=96):
    """8x16 cell mask, sampling the scaled image through the cell's own pixel blocks"""
    rows = []
    for j in range(16):
        line = []
        for i in range(8):
            nx, ny = TEXT_X0 + col * 8 + i, TEXT_Y0 + row * 16 + j
            x0 = int(round(ox + nx * sx)); x1 = int(round(ox + (nx + 1) * sx))
            y0 = int(round(oy + ny * sy)); y1 = int(round(oy + (ny + 1) * sy))
            x1 = max(x1, x0 + 1); y1 = max(y1, y0 + 1)
            lit = tot = 0
            for y in range(y0, y1):
                for x in range(x0, x1):
                    tot += 1
                    if px[x, y] > thresh:
                        lit += 1
            line.append(1 if tot and lit * 2 >= tot else 0)
        rows.append(line)
    return rows


def score(px, tabs, cfg, rows=(0,), cols=range(26)):
    ox, oy, sx, sy = cfg
    pool_label, char_of, orig_label = tabs
    hits = []
    for row in rows:
        for col in cols:
            m = cell_mask(px, ox, oy, sx, sy, col, row)
            bits = as_bits(m)
            if sum(sum(r) for r in m) < 5:
                continue
            p = pool_label.get(bits)
            o = orig_label.get(bits)
            if p is not None:
                hits.append((col, row, 'POOL', p, m))
            elif o is not None:
                hits.append((col, row, 'ORIG', o, m))
    return hits


def main():
    slots, pages, pool_label, char_of, orig_label = load_tables()
    tabs = (pool_label, char_of, orig_label)
    print('pool glyph masks=%d mapped chars=%d original font masks=%d'
          % (len(pool_label), len(char_of), len(orig_label)))

    nat = Image.open(os.path.join(BASE, 'hw/v29a_f01390.png')).convert('L')
    hits = score(nat.load(), tabs, (0, 0, 1.0, 1.0), rows=range(2))
    print('self test native frame at (0,0,1,1): %d exact cells -> %s'
          % (len(hits), [(h[0], h[1], h[2], h[3] if h[2] == 'POOL' else '$%02X' % h[3])
                         for h in hits]))

    im = Image.open(USER).convert('L')
    px = im.load()
    print('searching %s %s ...' % (os.path.basename(USER), im.size))
    best = None
    for sx in [2.60 + 0.02 * i for i in range(-4, 5)]:
        for sy in [2.55 + 0.02 * i for i in range(-4, 5)]:
            for dx in range(-6, 7):
                for dy in range(-6, 7):
                    h = score(px, tabs, (177 + dx, 57 + dy, sx, sy),
                              rows=(0,), cols=range(14))
                    if best is None or len(h) > len(best[1]):
                        best = ((177 + dx, 57 + dy, sx, sy), h)
    cfg, hits = best
    print('best coarse cfg=%s exact cells in row 0 (cols 0..13): %d'
          % (tuple(round(v, 3) if isinstance(v, float) else v for v in cfg), len(hits)))
    for h in hits:
        print('   col=%d row=%d %s %s' % (h[0], h[1], h[2], h[3]))

    ox, oy, sx, sy = cfg
    refined = None
    for ax in [ox + i for i in range(-4, 5)]:
        for ay in [oy + i for i in range(-4, 5)]:
            for asx in [sx + 0.005 * i for i in range(-4, 5)]:
                for asy in [sy + 0.005 * i for i in range(-4, 5)]:
                    h = score(px, tabs, (ax, ay, asx, asy), rows=range(2))
                    if refined is None or len(h) > len(refined[1]):
                        refined = ((ax, ay, asx, asy), h)
    cfg2, hits2 = refined
    print('refined cfg=%s  exact cells=%d' % (tuple(round(v, 3) if isinstance(v, float) else v
                                                     for v in cfg2), len(hits2)))
    for h in hits2:
        label = ('POOL (%d,%02X)=%s' % (h[3][0], h[3][1], char_of.get(h[3], '?'))
                 if h[2] == 'POOL' else 'ORIG code $%02X' % h[3])
        print('   col=%2d row=%d  %s' % (h[0], h[1], label))
    if hits2:
        print('--- masks of the matched cells ---')
        for y in range(16):
            line = ''
            for h in hits2:
                line += ''.join('#' if v else '.' for v in h[4][y]) + ' '
            print('   ' + line)


if __name__ == '__main__':
    main()