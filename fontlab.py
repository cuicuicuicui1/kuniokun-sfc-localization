"""Glyph rendering lab: compare 8x16 rasterisation pipelines for the kuniokun patch.

Quality proxies measured per glyph:
  ink    - fraction of inked pixels (1 px strokes on a 8x16 grid land near .35-.45)
  comp   - 4-connected components (too many = speckle/broken strokes)
  iso    - isolated pixels with no 4-neighbour
  fwrow  - rows where all 8 columns are inked (merged strokes)
  runs   - mean horizontal run length of ink (stroke thickness proxy)
"""
import sys
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, 'C:/Users/<user>/.zcode/workspace/default/sfc-recon')
from cnfont8 import render8x16

MSYH = 'C:/Windows/Fonts/msyh.ttc'
SIMHEI = 'C:/Windows/Fonts/simhei.ttf'
SIMSUN = 'C:/Windows/Fonts/simsun.ttc'
DENG = 'C:/Windows/Fonts/deng.ttf'
STXIHEI = 'C:/Windows/Fonts/stxihei.ttf'

CHARS = list('大阪啊襲擊櫻宮鐵魔闇警護讓鬪戰鬪鬱灣聽書賣讀寫誰歷史')


def em_grid(ch, fontpath, px, out_w=8, out_h=16, thresh=0.30, index=0,
            bold=0, ss=1):
    """Render ch at a high-res em square (px*ss) and area-average down to
    out_w x out_h, then binarise at `thresh` coverage.  `bold` dilates the
    source by that many output pixels."""
    R = px * ss
    f = ImageFont.truetype(fontpath, R, index=index)
    img = Image.new('L', (R, R), 0)
    d = ImageDraw.Draw(img)
    d.text((R / 2, R / 2), ch, fill=255, font=f, anchor='mm')
    if bold:
        from PIL import ImageFilter
        r = max(1, int(round(bold * R / out_w)))
        img = img.filter(ImageFilter.MaxFilter(2 * r + 1))
    small = img.resize((out_w, out_h), Image.BOX)
    p = small.load()
    g = [[1 if p[x, y] > 255 * thresh else 0 for x in range(out_w)] for y in range(out_h)]
    return g


def despeckle(g, min_neigh=1):
    out = [row[:] for row in g]
    for y in range(16):
        for x in range(8):
            if not g[y][x]:
                continue
            n = 0
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                xx, yy = x + dx, y + dy
                if 0 <= xx < 8 and 0 <= yy < 16 and g[yy][xx]:
                    n += 1
            if n <= min_neigh:
                out[y][x] = 0
    return out


def adaptive(ch, fontpath, px, index=0, bold=0, target=0.40, lo=0.08, hi=0.60, ss=8):
    g = None
    for _ in range(24):
        mid = (lo + hi) / 2
        g = em_grid(ch, fontpath, px, thresh=mid, index=index, bold=bold, ss=ss)
        ink = sum(map(sum, g)) / 128.0
        if ink > target:
            lo = mid
        else:
            hi = mid
    return g


def metrics(g):
    ink = sum(map(sum, g)) / 128.0
    seen = [[False] * 8 for _ in range(16)]
    comp = 0
    for y0 in range(16):
        for x0 in range(8):
            if g[y0][x0] and not seen[y0][x0]:
                comp += 1
                st = [(x0, y0)]
                seen[y0][x0] = True
                while st:
                    x, y = st.pop()
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        xx, yy = x + dx, y + dy
                        if 0 <= xx < 8 and 0 <= yy < 16 and g[yy][xx] and not seen[yy][xx]:
                            seen[yy][xx] = True
                            st.append((xx, yy))
    iso = 0
    for y in range(16):
        for x in range(8):
            if g[y][x]:
                n = sum(1 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                        if 0 <= x + dx < 8 and 0 <= y + dy < 16 and g[y + dy][x + dx])
                if n == 0:
                    iso += 1
    fwrow = sum(1 for y in range(16) if all(g[y]))
    runs = []
    for y in range(16):
        r = 0
        for x in range(9):
            if x < 8 and g[y][x]:
                r += 1
            else:
                if r:
                    runs.append(r)
                r = 0
    return dict(ink=ink, comp=comp, iso=iso, fwrow=fwrow,
                runs=(sum(runs) / len(runs) if runs else 0.0))


def show(g, label, m):
    print('--- %s  ink=%.2f comp=%d iso=%d fwidth_rows=%d mean_run=%.2f'
          % (label, m['ink'], m['comp'], m['iso'], m['fwrow'], m['runs']))
    for row in g:
        print('    ' + ''.join('#' if v else '.' for v in row))


PIPES = [
    ('current  (msyh16 bbox->8 lanczos t140 w1.12)',
     lambda ch: render8x16(ch, MSYH, 16, 140, 1.12)),
    ('msyh32 em-box area t.30',
     lambda ch: em_grid(ch, MSYH, 32, thresh=0.30, ss=8)),
    ('msyh32 em-box area adaptive .40',
     lambda ch: adaptive(ch, MSYH, 32, target=0.40, ss=8)),
    ('simhei32 em-box area adaptive .40',
     lambda ch: adaptive(ch, SIMHEI, 32, target=0.40, ss=8)),
    ('simhei48 em-box area adaptive .40',
     lambda ch: adaptive(ch, SIMHEI, 48, target=0.40, ss=8)),
    ('simsun12 em-box area adaptive .40',
     lambda ch: adaptive(ch, SIMSUN, 12, target=0.40, ss=16)),
    ('deng32 em-box area adaptive .40',
     lambda ch: adaptive(ch, DENG, 32, target=0.40, ss=8)),
    ('stxihei32 em-box area adaptive .40',
     lambda ch: adaptive(ch, STXIHEI, 32, target=0.40, ss=8)),
    ('msyh32 em-box bold1 adaptive .40',
     lambda ch: adaptive(ch, MSYH, 32, bold=1, target=0.40, ss=8)),
]


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    chars = [c for c in CHARS if only is None or c in only]
    tot = {name: dict(ink=0.0, comp=0, iso=0, fwrow=0, runs=0.0) for name, _ in PIPES}
    for ch in chars:
        for name, fn in PIPES:
            m = metrics(fn(ch))
            for k in tot[name]:
                tot[name][k] += m[k]
    n = float(len(chars))
    print('=== averaged over %d glyphs ===' % len(chars))
    print('%-45s %6s %7s %6s %8s %8s' % ('pipeline', 'ink', 'comp', 'iso', 'fwrow', 'run'))
    for name, _ in PIPES:
        t = tot[name]
        print('%-45s %6.2f %7.1f %6.1f %8.1f %8.2f'
              % (name, t['ink'] / n, t['comp'] / n, t['iso'] / n, t['fwrow'] / n, t['runs'] / n))
    for ch in chars[:4]:
        for name, fn in PIPES:
            g = fn(ch)
            show(g, '%s :: %s' % (ch, name), metrics(g))
        print()


if __name__ == '__main__':
    main()