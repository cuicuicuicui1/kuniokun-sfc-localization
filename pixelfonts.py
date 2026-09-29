"""Pixel-font renderers for the kuniokun 8x16 CJK cells.

Sources
  unifont  : GNU Unifont 16x16 bitmaps (complete CJK coverage, crude but crisp)
  ark12    : Ark Pixel 12px (OFL) hand-designed pixel glyphs, 11x11 CJK body
  soft     : high-res outline font area-averaged down (fallback, grey-ish)

Each renderer returns an 8x16 grid of 0/1 (1 = ink).
"""
from pathlib import Path
import gzip
import json
import os

BASE = str(Path(__file__).resolve().parent)
FONTS = os.path.join(BASE, 'fonts')

_src = {}


def load_unifont(path=None):
    path = path or os.path.join(FONTS, 'unifont.hex.gz')
    if 'uni' not in _src:
        g = {}
        for line in gzip.open(path, 'rt', encoding='utf-8', errors='replace'):
            line = line.strip()
            if line:
                cp, hx = line.split(':', 1)
                g[int(cp, 16)] = hx
        _src['uni'] = g
    return _src['uni']


def load_bdf(path):
    if path not in _src:
        glyphs = {}
        enc = bbx = rows = None
        for line in open(path, encoding='utf-8', errors='replace'):
            line = line.rstrip('\n')
            if line.startswith('ENCODING'):
                enc = int(line.split()[1])
            elif line.startswith('BBX'):
                bbx = tuple(int(v) for v in line.split()[1:5])
            elif line.startswith('BITMAP'):
                rows = []
            elif line.startswith('STARTCHAR'):
                enc = bbx = rows = None
            elif line.startswith('ENDCHAR'):
                if enc is not None and rows is not None:
                    glyphs[enc] = (bbx, rows)
                enc = bbx = rows = None
            elif rows is not None:
                rows.append(line)
        _src[path] = glyphs
    return _src[path]


def bits_of_bdf(bbx, rows):
    """-> list of rows of 0/1, width bbx[0]."""
    b = bytes.fromhex(''.join(rows))
    w, h = bbx[0], bbx[1]
    wb = (w + 7) // 8
    return [[(b[y * wb + (x >> 3)] >> (7 - (x & 7))) & 1 for x in range(w)] for y in range(h)]


# ---------------------------------------------------------------- transforms
def pairmerge(g):
    """16 wide -> 8 wide by OR-merging column pairs (crisp, no grey)."""
    return [[g[y][2 * x] | g[y][2 * x + 1] for x in range(8)] for y in range(len(g))]


def drop_cols(g, out_w=8):
    """Keep out_w of w columns, dropping evenly (crisp)."""
    w = len(g[0])
    if w <= out_w:
        keep = list(range(w)) + [w - 1] * (out_w - w)
    else:
        drop = set()
        for i in range(w - out_w):
            drop.add(int(round((i + 1) * w / (w - out_w + 1))) - 1)
        keep = [x for x in range(w) if x not in drop]
        while len(keep) > out_w:
            keep.pop(len(keep) // 2)
    return [[row[x] for x in keep] for row in g]


def stretch_rows(g, out_h=16):
    """Stretch h rows to out_h by duplicating rows evenly (crisp)."""
    h = len(g)
    if h == out_h:
        return [row[:] for row in g]
    if h > out_h:
        drop = set()
        for i in range(h - out_h):
            drop.add(int(round((i + 1) * h / (h - out_h + 1))) - 1)
        return [g[y][:] for y in range(h) if y not in drop]
    out = []
    for i in range(out_h):
        y = int(i * h / out_h)
        out.append(g[y][:])
    return out


def place(g, out_w=8, out_h=16):
    """Centre a grid in the output box."""
    h, w = len(g), len(g[0])
    out = [[0] * out_w for _ in range(out_h)]
    oy = max(0, (out_h - h) // 2)
    ox = max(0, (out_w - w) // 2)
    for y in range(min(h, out_h)):
        for x in range(min(w, out_w)):
            out[oy + y][ox + x] = g[y][x]
    return out


# ---------------------------------------------------------------- renderers
def r_unifont(ch, **kw):
    g = load_unifont()
    hx = g.get(ord(ch))
    if hx is None:
        return None
    b = bytes.fromhex(hx)
    n = len(b) // 16
    grid = [[(b[y * n + (x >> 3)] >> (7 - (x & 7))) & 1 for x in range(16)] for y in range(16)]
    return pairmerge(grid)


_ARK12 = os.path.join(FONTS, 'ark-pixel-12px-monospaced-zh_cn.bdf')


def r_ark12(ch, **kw):
    g = load_bdf(_ARK12).get(ord(ch))
    if g is None:
        return None
    grid = bits_of_bdf(*g)
    grid = drop_cols(grid, 8)          # 11/12 wide -> 8
    grid = stretch_rows(grid, 16)      # 11/12 tall -> 16
    return place(grid, 8, 16)


def r_ark12_sq(ch, **kw):
    """Ark Pixel glyph kept square: 11x11 -> 8x8 in the middle of the cell."""
    g = load_bdf(_ARK12).get(ord(ch))
    if g is None:
        return None
    grid = drop_cols(bits_of_bdf(*g), 8)
    return place(stretch_rows(grid, 8), 8, 16)


def r_soft(ch, fontpath=None, px=32, target=0.40, **kw):
    import sys
    sys.path.insert(0, BASE)
    from fontlab import adaptive
    return adaptive(ch, fontpath or 'C:/Windows/Fonts/stxihei.ttf', px, target=target)


RENDERERS = {
    'unifont_pm': r_unifont,
    'ark12_stretch': r_ark12,
    'ark12_square': r_ark12_sq,
    'soft_stxihei': r_soft,
}


def best(ch, prefer=('ark12_stretch', 'unifont_pm', 'soft_stxihei')):
    """First renderer that covers the character."""
    for name in prefer:
        g = RENDERERS[name](ch)
        if g is not None and any(map(any, g)):
            return name, g
    return None, None


if __name__ == '__main__':
    import sys
    chars = sys.argv[1] if len(sys.argv) > 1 else '大阪襲鐵'
    from fontlab import metrics
    for ch in chars:
        for name, fn in RENDERERS.items():
            g = fn(ch)
            if g is None:
                print('%-14s %s : no coverage' % (name, ch))
                continue
            m = metrics(g)
            print('--- %s :: %-14s ink=%.2f comp=%d iso=%d fwrow=%d run=%.2f'
                  % (ch, name, m['ink'], m['comp'], m['iso'], m['fwrow'], m['runs']))
            for row in g:
                print('    ' + ''.join('#' if v else '.' for v in row))
        print()