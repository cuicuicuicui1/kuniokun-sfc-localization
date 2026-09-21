"""Compare candidate 8x16 CJK rasterisers over the whole translation (971 chars).

Metrics per glyph (see fontlab.metrics): ink, comp (4-connected pieces),
iso (isolated px), fwrow (merged full-width rows), runs (stroke thickness).

Also renders sample dialog lines (ground truth known) to PNG at 1x and at the
2.63x bilinear scale the user's snes9x window applies, so the *legibility* of
each pipeline can be checked against text we already know.
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

BASE = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon'
sys.path.insert(0, BASE)
from fontlab import metrics, adaptive, em_grid           # noqa: E402
from pixelfonts import (load_unifont, load_bdf, bits_of_bdf, pairmerge,
                        drop_cols, stretch_rows, place, _ARK12)  # noqa: E402
from cnfont8 import render8x16                            # noqa: E402

STXIHEI = 'C:/Windows/Fonts/stxihei.ttf'
MSYH = 'C:/Windows/Fonts/msyh.ttc'
OUT = os.path.join(BASE, 'fontcmp')

SS = 8          # supersample factor for bit-grid rescaling


def bits_to_img(g):
    h, w = len(g), len(g[0])
    im = Image.new('L', (w * SS, h * SS), 0)
    px = im.load()
    for y in range(h):
        for x in range(w):
            if g[y][x]:
                for dy in range(SS):
                    for dx in range(SS):
                        px[x * SS + dx, y * SS + dy] = 255
    return im


def scale_adaptive(g, out_w, out_h, target=0.42, lo=0.05, hi=0.95, iters=22):
    """Area-average a 0/1 grid into out_w x out_h, adaptive threshold."""
    small = bits_to_img(g).resize((out_w, out_h), Image.BOX)
    p = small.load()
    vals = [[p[x, y] for x in range(out_w)] for y in range(out_h)]
    for _ in range(iters):
        mid = (lo + hi) / 2
        cur = [[1 if vals[y][x] > 255 * mid else 0 for x in range(out_w)] for y in range(out_h)]
        ink = sum(map(sum, cur)) / float(out_w * out_h)
        if ink > target:
            lo = mid
        else:
            hi = mid
    return cur


def bottom_align(g, out_w=8, out_h=16):
    """Place a shorter grid in the lower part of the cell (kana sit low too)."""
    h, w = len(g), len(g[0])
    out = [[0] * out_w for _ in range(out_h)]
    oy = out_h - h
    ox = max(0, (out_w - w) // 2)
    for y in range(min(h, out_h)):
        for x in range(min(w, out_w)):
            out[oy + y][ox + x] = g[y][x]
    return out


def drop_cols_smart(g, out_w=8):
    """Drop the emptiest columns first (keeps vertical strokes alive)."""
    g = [row[:] for row in g]
    w = len(g[0])
    order = sorted(range(w), key=lambda x: (
        sum(row[x] for row in g),                 # fewer inked px first
        abs(x - (w - 1) / 2.0)))                  # then prefer outer columns
    drop = set(order[:w - out_w])
    return [[row[x] for x in range(w) if x not in drop] for row in g]


def drop_rows_smart(g, out_h):
    h = len(g)
    order = sorted(range(h), key=lambda y: (sum(g[y]), abs(y - (h - 1) / 2.0)))
    drop = set(order[:h - out_h])
    return [g[y][:] for y in range(h) if y not in drop]


# --------------------------------------------------------------- pipelines
def p_cur(ch):
    return render8x16(ch, MSYH, 16, 140, 1.12)


def p_soft16(ch, font=STXIHEI, px=32, target=0.42):
    return adaptive(ch, font, px, target=target, ss=8)


def p_soft_small(ch, out_h, font=STXIHEI, px=32, target=0.42):
    g = em_grid(ch, font, px, out_w=8, out_h=out_h, thresh=0.5, ss=8)
    # em_grid binarises with a fixed thresh; redo it adaptively at this box
    base = em_grid(ch, font, px, out_w=16, out_h=out_h, thresh=0.5, ss=8)
    _ = g
    return None if base is None else base


def p_soft11(ch):
    """STXihei, glyph box 8x11 (aspect 1:1.375), bottom aligned."""
    R = 32 * 8
    f = ImageFont.truetype(STXIHEI, R)
    img = Image.new('L', (R, R), 0)
    ImageDraw.Draw(img).text((R / 2, R / 2), ch, fill=255, font=f, anchor='mm')
    small = img.resize((8, 11), Image.BOX)
    p = small.load()
    vals = [[p[x, y] for x in range(8)] for y in range(11)]
    lo, hi = 0.05, 0.95
    for _ in range(22):
        mid = (lo + hi) / 2
        cur = [[1 if vals[y][x] > 255 * mid else 0 for x in range(8)] for y in range(11)]
        ink = sum(map(sum, cur)) / 88.0
        if ink > 0.42:
            lo = mid
        else:
            hi = mid
    return bottom_align(cur)


def _soft_box(ch, out_w, out_h, font=STXIHEI, px=32, target=0.42):
    R = px * 8
    f = ImageFont.truetype(font, R)
    img = Image.new('L', (R, R), 0)
    ImageDraw.Draw(img).text((R / 2, R / 2), ch, fill=255, font=f, anchor='mm')
    small = img.resize((out_w, out_h), Image.BOX)
    p = small.load()
    vals = [[p[x, y] for x in range(out_w)] for y in range(out_h)]
    lo, hi = 0.05, 0.95
    for _ in range(22):
        mid = (lo + hi) / 2
        cur = [[1 if vals[y][x] > 255 * mid else 0 for x in range(out_w)] for y in range(out_h)]
        ink = sum(map(sum, cur)) / float(out_w * out_h)
        if ink > target:
            lo = mid
        else:
            hi = mid
    return cur


def p_soft_box11(ch):
    return bottom_align(_soft_box(ch, 8, 11))


def p_soft_box12(ch):
    return bottom_align(_soft_box(ch, 8, 12))


def p_uni16(ch):
    hx = load_unifont().get(ord(ch))
    if hx is None:
        return None
    b = bytes.fromhex(hx)
    n = len(b) // 16
    grid = [[(b[y * n + (x >> 3)] >> (7 - (x & 7))) & 1 for x in range(16)] for y in range(16)]
    return pairmerge(grid)


def p_uni11(ch):
    hx = load_unifont().get(ord(ch))
    if hx is None:
        return None
    b = bytes.fromhex(hx)
    n = len(b) // 16
    grid = [[(b[y * n + (x >> 3)] >> (7 - (x & 7))) & 1 for x in range(16)] for y in range(16)]
    return bottom_align(scale_adaptive(grid, 8, 11))


def p_ark_raw(ch):
    g = load_bdf(_ARK12).get(ord(ch))
    return None if g is None else bits_of_bdf(*g)


def p_ark11(ch):
    g = p_ark_raw(ch)
    return None if g is None else bottom_align(drop_cols_smart(g, 8))


def p_ark16(ch):
    g = p_ark_raw(ch)
    if g is None:
        return None
    return place(stretch_rows(drop_cols_smart(g, 8), 16), 8, 16)


def p_ark16_wide(ch):
    """ark12 -> 8x16 but squeeze horizontally by area average (smooth)."""
    g = p_ark_raw(ch)
    return None if g is None else scale_adaptive(g, 8, 16, target=0.42)


def p_uni_ark11(ch):
    """ark12 for covered chars, unifont for the rest (all bottom aligned 8x11)."""
    g = p_ark11(ch)
    return p_uni11(ch) if g is None else g


PIPES = [
    ('cur  msyh16 lanczos t140 w1.12', p_cur),
    ('soft16 stxihei32 area ad.42', p_soft16),
    ('soft_box11 stxihei area', p_soft_box11),
    ('soft_box12 stxihei area', p_soft_box12),
    ('uni16 unifont pairmerge', p_uni16),
    ('uni11 unifont area 8x11', p_uni11),
    ('ark11 ark12 drop-cols 8x11', p_ark11),
    ('ark16 ark12 drop+stretch', p_ark16),
    ('ark16w ark12 area 8x16', p_ark16_wide),
]


def load_chars():
    seen = set()
    for v in json.load(open(os.path.join(BASE, 'cn_translation.json'), encoding='utf-8')).values():
        for ch in v:
            if 0x4e00 <= ord(ch) <= 0x9fff:
                seen.add(ch)
    return sorted(seen)


def main():
    os.makedirs(OUT, exist_ok=True)
    chars = load_chars()
    print('glyph count: %d' % len(chars))
    rows = []
    for name, fn in PIPES:
        tot = dict(ink=0.0, comp=0, iso=0, fwrow=0, runs=0.0)
        miss = 0
        worst = []
        for ch in chars:
            g = fn(ch)
            if g is None or not any(map(any, g)):
                miss += 1
                continue
            m = metrics(g)
            for k in tot:
                tot[k] += m[k]
            worst.append((m['comp'], ch))
        n = float(len(chars) - miss)
        worst.sort(reverse=True)
        rows.append((name, miss, [tot[k] / n for k in ('ink', 'comp', 'iso', 'fwrow', 'runs')], worst[:6]))
    print('%-32s %5s %6s %6s %6s %6s %6s   worst(comp)' % ('pipeline', 'miss', 'ink', 'comp', 'iso', 'fwrow', 'run'))
    for name, miss, vals, worst in rows:
        print('%-32s %5d %6.2f %6.1f %6.1f %6.1f %6.2f   %s'
              % (name, miss, vals[0], vals[1], vals[2], vals[3], vals[4],
                 ' '.join('%s:%d' % (c, k) for k, c in worst)))

    # ASCII samples for the problem glyphs
    sample = '大阪襲鐵警護讓鬱'
    for ch in sample:
        print()
        for name, fn in PIPES:
            g = fn(ch)
            if g is None:
                print('=== %s :: %-32s no coverage' % (ch, name))
                continue
            m = metrics(g)
            print('=== %s :: %-32s ink=%.2f comp=%d iso=%d fw=%d' % (ch, name, m['ink'], m['comp'], m['iso'], m['fwrow']))
            for row in g:
                print('    ' + ''.join('#' if v else '.' for v in row))


if __name__ == '__main__':
    main()