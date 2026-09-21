"""Decode the user's emulator screenshot by anchoring the geometry on the dialog box frame.

The message box frame is drawn at fixed engine coordinates, so its bounding box in a
scaled window screenshot divided by its bounding box in a native 256x224 screenshot
gives the exact scale, and the corner difference gives the offset.  Then every 8x16
character cell of the message window can be sampled and matched against my Chinese
glyph pool (exact bit match => char) or the original Japanese font.

Evidence quality: a correct geometry makes many cells match *exactly*; the native
frame is the control (it must score its known five pool cells).
"""
import os, sys
from collections import Counter
from PIL import Image
from decode_shot import load_tables, mask_from_pool32, as_bits

BASE = os.path.dirname(os.path.abspath(__file__))
NATIVE = os.path.join(BASE, 'hw/v29a_f01390.png')
USER = ("C:/Users/<user>/.zcode/cli/image-cache/"
        "sess_2d6e90fa-48ba-457c-9ffa-65d2cb3a2d7a/image-29129c7e5361e3776ae9e09dd4a1ea0f.png")
TEXT_X0, TEXT_Y0 = 24, 183


def frame_candidates(im, tol=40):
    """find a colour whose pixels form a thin rectangle outline (the message box frame)"""
    px = im.convert('RGB').load()
    w, h = im.size
    c = Counter()
    for y in range(h // 3, h):
        for x in range(w):
            r, g, b = px[x, y]
            if max(r, g, b) - min(r, g, b) > 40 and b > 90:
                c[(r // 24 * 24, g // 24 * 24, b // 24 * 24)] += 1
    out = []
    for (r0, g0, b0), n in c.most_common(8):
        if n < 200:
            continue
        xs, ys = [], []
        for y in range(h):
            for x in range(w):
                r, g, b = px[x, y]
                if abs(r - r0) <= tol and abs(g - g0) <= tol and abs(b - b0) <= tol:
                    xs.append(x); ys.append(y)
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        per = 2 * ((x1 - x0) + (y1 - y0))
        out.append(((r0, g0, b0), n, (x0, y0, x1, y1), n / float(per) if per else 0))
    return out


def analyse(path):
    im = Image.open(path)
    print('== %s %s' % (os.path.basename(path), im.size))
    for col, n, box, ratio in frame_candidates(im):
        print('   colour %-17s n=%-6d bbox=%-24s pixels/perimeter=%.2f'
              % (str(col), n, str(box), ratio))
    return im


def cell_mask(px, ox, oy, sx, sy, col, row, thresh=96):
    rows = []
    for j in range(16):
        line = []
        for i in range(8):
            nx, ny = TEXT_X0 + col * 8 + i, TEXT_Y0 + row * 16 + j
            x0 = int(round(ox + nx * sx)); x1 = max(x0 + 1, int(round(ox + (nx + 1) * sx)))
            y0 = int(round(oy + ny * sy)); y1 = max(y0 + 1, int(round(oy + (ny + 1) * sy)))
            lit = tot = 0
            for y in range(y0, y1):
                for x in range(x0, x1):
                    tot += 1
                    if px[x, y] > thresh:
                        lit += 1
            line.append(1 if tot and lit * 2 >= tot else 0)
        rows.append(line)
    return rows


def decode(im, cfg, tabs, rows=range(2), cols=range(26)):
    pool_label, char_of, orig_label = tabs
    px = im.convert('L').load()
    ox, oy, sx, sy = cfg
    out = []
    for r in rows:
        for c in cols:
            m = cell_mask(px, ox, oy, sx, sy, c, r)
            if sum(sum(x) for x in m) < 5:
                continue
            bits = as_bits(m)
            p = pool_label.get(bits)
            o = orig_label.get(bits)
            out.append((c, r, m, p, o))
    return out


def render(m):
    return '\n'.join('      ' + ''.join('#' if v else '.' for v in row) for row in m)


def main():
    slots, pages, pool_label, char_of, orig_label = load_tables()
    tabs = (pool_label, char_of, orig_label)
    analyse(NATIVE)
    analyse(USER)
    # native control: identity geometry must decode the five known glyphs
    nat = Image.open(NATIVE).convert('L')
    hits = decode(nat, (0, 0, 1.0, 1.0), tabs)
    print('control: native frame identity geometry -> %d exact cells' % len(hits))
    for c, r, m, p, o in hits:
        print('   col=%d row=%d %s' % (c, r,
              'POOL (%d,%02X)=%s' % (p[0], p[1], char_of.get(p, '?')) if p else
              ('ORIG $%02X' % o if o is not None else 'neither')))


if __name__ == '__main__':
    main()