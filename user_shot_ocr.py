"""Bit-accurate decode of the user's message window, with local geometry search.

For each candidate (ox, oy, threshold) we sample the 8x16 character cells of the
message window with nearest-pixel reads -- the SNES picture has no anti-aliasing, so
nearest sampling keeps the exact 2bpp pen/background levels -- and count how many
cells match a known bitmap *exactly*:
  * one of my Chinese pool glyphs  (=> the screen shows my patch working)
  * one of the 256 original Japanese font glyphs (=> something drew raw bytes)
No match at all for the best geometry would mean the screen shows a third tile set.

The native control frame (hw/v29a_f01390.png, proven pixel exact) is the sanity check:
at (0, 0) it must score its five pool cells.
"""
import os, sys
from PIL import Image
from decode_shot import load_tables

BASE = os.path.dirname(os.path.abspath(__file__))
NATIVE = os.path.join(BASE, 'hw/v29a_f01390.png')
USER = ("C:/Users/<user>/.zcode/cli/image-cache/"
        "sess_2d6e90fa-48ba-457c-9ffa-65d2cb3a2d7a/image-29129c7e5361e3776ae9e09dd4a1ea0f.png")
TEXT_X0, TEXT_Y0 = 24, 183


def cell_mask(px, ox, oy, sx, sy, col, row, thresh):
    """nearest-pixel sampled 8x16 mask: 1 where the cell pixel is pen coloured"""
    rows = []
    for j in range(16):
        line = []
        for i in range(8):
            nx, ny = TEXT_X0 + col * 8 + i, TEXT_Y0 + row * 16 + j
            x = int(ox + (nx + 0.5) * sx)
            y = int(oy + (ny + 0.5) * sy)
            line.append(1 if px[x, y] > thresh else 0)
        rows.append(line)
    return rows


def decode(px, tabs, cfg, cols=range(20), rows=range(2)):
    pool_label, char_of, orig_label = tabs
    ox, oy, sx, sy, thresh = cfg
    out = []
    for r in rows:
        for c in cols:
            m = cell_mask(px, ox, oy, sx, sy, c, r, thresh)
            n = sum(sum(x) for x in m)
            if n < 5:
                continue
            bits = bytes(sum(m, []))
            p = pool_label.get(bits)
            o = orig_label.get(bits)
            out.append((c, r, m, n, p, o))
    return out


def main():
    slots, pages, pool_label, char_of, orig_label = load_tables()
    tabs = (pool_label, char_of, orig_label)

    nat = Image.open(NATIVE).convert('L').load()
    ctrl = decode(nat, tabs, (0, 0, 1.0, 1.0, 96), cols=range(12))
    print('control native frame at (0,0,1,1,96): %d exact matches' % len(ctrl))
    for c, r, m, n, p, o in ctrl:
        print('   col=%d row=%d ink=%3d %s' % (c, r, n,
              'POOL (%d,%02X)=%s' % (p[0], p[1], char_of.get(p, '?')) if p is not None
              else ('ORIG $%02X' % o if o is not None else 'neither')))

    im = Image.open(USER).convert('L')
    px = im.load()
    print('searching geometry on the user screenshot (%.0f x %.0f)' % im.size)
    best = None
    for ox in range(170, 186):
        for oy in range(45, 61):
            for th in (80, 100, 120, 140, 160):
                hits = decode(px, tabs, (ox, oy, 2.633, 2.634, th), cols=range(20))
                if best is None or len(hits) > len(best[1]):
                    best = ((ox, oy, 2.633, 2.634, th), hits)
    cfg, hits = best
    print('best cfg (ox, oy, sx, sy, thresh) = %s -> %d exact cells' % (cfg, len(hits)))
    pools = [h for h in hits if h[4] is not None]
    orig = [h for h in hits if h[4] is None and h[5] is not None]
    neither = [h for h in hits if h[4] is None and h[5] is None]
    print('  pool matches  : %s' % [(h[0], h[1], char_of.get(h[4], '?'), h[4]) for h in pools])
    print('  orig matches  : %s' % [(h[0], h[1], '$%02X' % h[5]) for h in orig])
    print('  unknown cells : %s' % [(h[0], h[1], h[3]) for h in neither])
    print('--- bitmap of every cell with ink (pen = #), geometry as above ---')
    for c, r, m, n, p, o in hits:
        lab = ('POOL %s %s' % (char_of.get(p, '?'), p) if p is not None else
               ('ORIG $%02X' % o if o is not None else 'unknown'))
        print('  cell col=%d row=%d  %s' % (c, r, lab))
        for row_bits in m:
            print('     ' + ''.join('#' if v else '.' for v in row_bits))


if __name__ == '__main__':
    main()