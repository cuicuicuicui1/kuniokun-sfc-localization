"""Candidate 16x16 rasterisers for the kuniokun patch, compared by measurement.

The 16x16 cell is 2 screen cells wide (tile columns) so a Chinese character is
drawn as 4 tiles: TL, BL, TR, BR.

Pipelines
  uni     GNU Unifont native 16x16 bitmap (crisp grid, rough shapes)
  sun16   SimSun 16px supersampled -> area average -> adaptive threshold
  sun17   SimSun 17px, same
  msyh16  Microsoft YaHei 16px, same
  hei16   STXihei 16px, same
  ark11   Ark Pixel 12px CJK bitmap (11x11) centred in 16x16 (crisp, small)

Metrics: ink fraction / 4-connected components / isolated pixels / full-width
rows / mean horizontal run (fontlab.metrics, generalised to 16x16).
Separability: every glyph through the user's 2.634x display blur, then the
distance to the nearest *different* character (bigger = easier to tell apart).
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon'
if BASE not in sys.path:
    sys.path.insert(0, BASE)

SIMSUN = 'C:/Windows/Fonts/simsun.ttc'
MSYH = 'C:/Windows/Fonts/msyh.ttc'
STXIHEI = 'C:/Windows/Fonts/stxihei.ttf'
W = H = 16
SS = 16
SCALE = 2.634
TARGET = 0.30


def _soft(ch, fontpath, px, target=TARGET, w=W, h=H):
    R = px * SS
    f = ImageFont.truetype(fontpath, R)
    img = Image.new('L', (R, R), 0)
    ImageDraw.Draw(img).text((R / 2, R / 2), ch, fill=255, font=f, anchor='mm')
    small = img.resize((w, h), Image.BOX)
    p = small.load()
    vals = [[p[x, y] for x in range(w)] for y in range(h)]
    lo, hi = 0.05, 0.95
    g = None
    for _ in range(24):
        mid = (lo + hi) / 2
        g = [[1 if vals[y][x] > 255 * mid else 0 for x in range(w)] for y in range(h)]
        if sum(map(sum, g)) / float(w * h) > target:
            lo = mid
        else:
            hi = mid
    return g


def _unifont_grid():
    from pixelfonts import load_unifont
    return load_unifont()


_UNI = None


def p_uni(ch):
    global _UNI
    if _UNI is None:
        _UNI = _unifont_grid()
    hx = _UNI.get(ord(ch))
    if hx is None:
        return None
    b = bytes.fromhex(hx)
    if len(b) == 16:                    # half-width row (8 px wide)
        grid = [[(b[y] >> (7 - x)) & 1 for x in range(8)] for y in range(16)]
        out = [[0] * 16 for _ in range(16)]
        for y in range(16):
            for x in range(8):
                out[y][x + 4] = grid[y][x]
        return out
    if len(b) != 32:
        return None
    return [[(b[y * 2 + (x >> 3)] >> (7 - (x & 7))) & 1 for x in range(16)] for y in range(16)]


def _ark_grid():
    from pixelfonts import load_bdf, bits_of_bdf
    return load_bdf(os.path.join(BASE, 'fonts', 'ark-pixel-12px-monospaced-zh_cn.bdf'))


_ARK = None


def p_ark11(ch):
    """Ark 12px CJK body (11x11) dropped into a 16x16 cell, bottom aligned."""
    global _ARK
    if _ARK is None:
        _ARK = _ark_grid()
    bits = _ARK.get(ord(ch))
    if bits is None:
        return None
    from pixelfonts import bits_of_bdf
    g = bits_of_bdf(bits, 8, 12)
    ih = len(g)
    iw = len(g[0]) if g else 0
    if iw > 16 or ih > 16:
        return None
    out = [[0] * 16 for _ in range(16)]
    ox = (16 - iw) // 2
    oy = 16 - ih
    for y in range(ih):
        for x in range(iw):
            out[oy + y][ox + x] = g[y][x]
    return out


def p_sun16(ch):
    return _soft(ch, SIMSUN, 16)


def p_sun17(ch):
    return _soft(ch, SIMSUN, 17)


def p_msyh16(ch):
    return _soft(ch, MSYH, 16)


def p_hei16(ch):
    return _soft(ch, STXIHEI, 16)


PIPES = [
    ('uni16 native', p_uni),
    ('sun16 area ad.30', p_sun16),
    ('sun17 area ad.30', p_sun17),
    ('msyh16 area ad.30', p_msyh16),
    ('hei16 area ad.30', p_hei16),
    ('ark11 centred', p_ark11),
]


def metrics(g):
    ink = sum(map(sum, g)) / 128.0
    seen = [[False] * W for _ in range(H)]
    comp = 0
    for y0 in range(H):
        for x0 in range(W):
            if g[y0][x0] and not seen[y0][x0]:
                comp += 1
                st = [(x0, y0)]
                seen[y0][x0] = True
                while st:
                    x, y = st.pop()
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        xx, yy = x + dx, y + dy
                        if 0 <= xx < W and 0 <= yy < H and g[yy][xx] and not seen[yy][xx]:
                            seen[yy][xx] = True
                            st.append((xx, yy))
    iso = 0
    for y in range(H):
        for x in range(W):
            if g[y][x]:
                n = sum(1 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                        if 0 <= x + dx < W and 0 <= y + dy < H and g[y + dy][x + dx])
                if n == 0:
                    iso += 1
    fwrow = sum(1 for y in range(H) if all(g[y]))
    runs = []
    for y in range(H):
        r = 0
        for x in range(W + 1):
            if x < W and g[y][x]:
                r += 1
            else:
                if r:
                    runs.append(r)
                r = 0
    return dict(ink=ink, comp=comp, iso=iso, fwrow=fwrow,
                runs=(sum(runs) / len(runs) if runs else 0.0))


def perceived(g, w=W, h=H, scale=SCALE):
    im = Image.new('L', (w, h), 0)
    px = im.load()
    for y in range(h):
        for x in range(w):
            if g[y][x]:
                px[x, y] = 255
    up = im.resize((int(round(w * scale)), int(round(h * scale))), Image.BILINEAR)
    back = up.resize((w, h), Image.BOX)
    return np.asarray(back, dtype=np.float64) / 255.0


def sepstats(vector_list):
    M = np.array(vector_list)
    n = M.shape[0]
    sq = (M * M).sum(1)
    best = np.full(n, np.inf)
    for i in range(0, n, 128):
        blk = M[i:i + 128]
        d2 = sq[i:i + 128, None] + sq[None, :] - 2.0 * blk.dot(M.T)
        np.fill_diagonal(d2[:, i:i + 128], np.inf)
        best[i:i + 128] = d2.min(1)
    d = np.sqrt(np.maximum(best, 0))
    return float(d.mean()), float(np.percentile(d, 5)), float(d.min())


def show(g):
    return '\n'.join('    ' + ''.join('#' if v else '.' for v in row) for row in g)


def load_chars():
    tr = json.load(open(os.path.join(BASE, 'cn_translation.json'), encoding='utf-8'))
    chars = set()
    for v in tr.values():
        chars.update(v)
    # drop the {..} control-code placeholders
    out = set()
    for c in chars:
        if c in '{} ':
            continue
        out.add(c)
    return sorted(out)


def main():
    chars = load_chars()
    print('characters: %d' % len(chars))
    res = {}
    for name, fn in PIPES:
        miss = []
        tot = dict(ink=0.0, comp=0.0, iso=0.0, fwrow=0.0, runs=0.0)
        vecs = []
        n = 0
        for ch in chars:
            g = fn(ch)
            if g is None or not any(map(any, g)):
                miss.append(ch)
                continue
            m = metrics(g)
            for k in tot:
                tot[k] += m[k]
            vecs.append(perceived(g).ravel())
            n += 1
        avg = {k: v / n for k, v in tot.items()}
        bmean, bp5, bmin = sepstats(vecs)
        res[name] = (avg, bmean, bp5, bmin, miss, fn)
        print('%-20s n=%4d ink %.2f comp %4.1f iso %3.1f fwrow %3.1f runs %.2f | blur sep mean %.2f p5 %.2f min %.2f | missing %d %s'
              % (name, n, avg['ink'], avg['comp'], avg['iso'], avg['fwrow'], avg['runs'],
                 bmean, bp5, bmin, len(miss), ''.join(miss[:12])))

    demo = '大阪啊猪肉包一个日田襲鐵調'
    for ch in demo:
        print('\n===== %s (U+%04X)' % (ch, ord(ch)))
        for name, fn in PIPES:
            g = fn(ch)
            if g is None or not any(map(any, g)):
                print('  %s: MISSING' % name)
                continue
            m = metrics(g)
            print('  %-20s ink %.2f comp %d iso %d fw %d' % (name, m['ink'], m['comp'], m['iso'], m['fwrow']))
            print(show(g))


if __name__ == '__main__':
    main()