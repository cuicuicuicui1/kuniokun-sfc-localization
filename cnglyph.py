"""Final glyph rasteriser for the kuniokun patch (8x16 cell, SNES 2bpp).

Chosen by measurement (see fontcmp.py / separable.py): SimSun rendered at 12 px,
area-averaged over the em square into 8x16 and binarised with an adaptive
threshold to ~42% ink.

Why this one: over all 971 translated characters it gives 2.3 four-connected
fragments per glyph (the old msyh16/LANCZOS pipeline gave 7.2) and, after
simulating the user's 2.63x display blur, the closest pair of *different*
characters stays 1.44 apart (old pipeline: 0.00 - 日 and 田 rendered IDENTICAL).

Fallbacks, in order: unifont (16x16 bitmap, pair-merged to 8 wide) then STXihei.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

BASE = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon'
if BASE not in sys.path:
    sys.path.insert(0, BASE)

SIMSUN = 'C:/Windows/Fonts/simsun.ttc'
STXIHEI = 'C:/Windows/Fonts/stxihei.ttf'
PX = 12            # SimSun hinted at 12 px, refined by supersampling
SS = 16            # supersample factor
TARGET = 0.42      # ink fraction of the 8x16 cell
_cache = {}


def _simsun(ch):
    R = PX * SS
    f = ImageFont.truetype(SIMSUN, R)
    img = Image.new('L', (R, R), 0)
    ImageDraw.Draw(img).text((R / 2, R / 2), ch, fill=255, font=f, anchor='mm')
    small = img.resize((8, 16), Image.BOX)
    p = small.load()
    vals = [[p[x, y] for x in range(8)] for y in range(16)]
    lo, hi = 0.05, 0.95
    g = None
    for _ in range(24):
        mid = (lo + hi) / 2
        g = [[1 if vals[y][x] > 255 * mid else 0 for x in range(8)] for y in range(16)]
        if sum(map(sum, g)) / 128.0 > TARGET:
            lo = mid
        else:
            hi = mid
    return g


def _unifont(ch):
    from pixelfonts import load_unifont, pairmerge
    hx = load_unifont().get(ord(ch))
    if hx is None:
        return None
    b = bytes.fromhex(hx)
    n = len(b) // 16
    grid = [[(b[y * n + (x >> 3)] >> (7 - (x & 7))) & 1 for x in range(16)] for y in range(16)]
    return pairmerge(grid)


def _stxihei(ch):
    R = 32 * 8
    f = ImageFont.truetype(STXIHEI, R)
    img = Image.new('L', (R, R), 0)
    ImageDraw.Draw(img).text((R / 2, R / 2), ch, fill=255, font=f, anchor='mm')
    small = img.resize((8, 16), Image.BOX)
    p = small.load()
    vals = [[p[x, y] for x in range(8)] for y in range(16)]
    lo, hi = 0.05, 0.95
    g = None
    for _ in range(24):
        mid = (lo + hi) / 2
        g = [[1 if vals[y][x] > 255 * mid else 0 for x in range(8)] for y in range(16)]
        if sum(map(sum, g)) / 128.0 > TARGET:
            lo = mid
        else:
            hi = mid
    return g


def render16(ch):
    """-> 8x16 grid of 0/1 (top row first)."""
    if ch in _cache:
        return _cache[ch]
    if not ch.strip():                      # spaces are coded as $00, never pooled
        g = [[0] * 8 for _ in range(16)]
        _cache[ch] = g
        return g
    for fn in (_simsun, _unifont, _stxihei):
        try:
            g = fn(ch)
        except Exception:
            g = None
        if g is not None and any(map(any, g)):
            _cache[ch] = g
            return g
    raise SystemExit('no renderer produces a glyph for %r' % ch)


def renderer_name(ch):
    for name, fn in (('simsun', _simsun), ('unifont', _unifont), ('stxihei', _stxihei)):
        try:
            g = fn(ch)
        except Exception:
            g = None
        if g is not None and any(map(any, g)):
            return name
    return None


if __name__ == '__main__':
    import json
    from fontlab import metrics
    chars = set()
    for v in json.load(open(os.path.join(BASE, 'cn_translation.json'), encoding='utf-8')).values():
        chars.update(v)
    # control-code placeholders in the json are not real characters
    chars = sorted(c for c in chars if c not in '{}' and c.strip())
    tot = dict(ink=0.0, comp=0, iso=0, fwrow=0, runs=0.0)
    fb = {}
    for ch in chars:
        fb.setdefault(renderer_name(ch), []).append(ch)
        m = metrics(render16(ch))
        for k in tot:
            tot[k] += m[k]
    n = float(len(chars))
    print('charges: %d' % len(chars))
    print('ink %.2f comp %.1f iso %.1f fwrow %.1f runs %.2f'
          % tuple(tot[k] / n for k in ('ink', 'comp', 'iso', 'fwrow', 'runs')))
    for k, v in fb.items():
        print('%-8s %4d  %s' % (k, len(v), ''.join(v[:40])))

# ---------------------------------------------------------------- 16x16 (2019 redesign)
_cache16 = {}


def _unifont16(ch):
    """GNU Unifont's native 16x16 bitmap for ch, or None. Half-width rows are centred."""
    from pixelfonts import load_unifont
    hx = load_unifont().get(ord(ch))
    if hx is None:
        return None
    b = bytes.fromhex(hx)
    if len(b) == 16:                      # 8 px wide row
        row = [[(b[y] >> (7 - x)) & 1 for x in range(8)] for y in range(16)]
        out = [[0] * 16 for _ in range(16)]
        for y in range(16):
            for x in range(8):
                out[y][x + 4] = row[y][x]
        return out
    if len(b) != 32:
        return None
    return [[(b[y * 2 + (x >> 3)] >> (7 - (x & 7))) & 1 for x in range(16)] for y in range(16)]


def _simsun16(ch, thr=0.25):
    """Outline fallback: 16 px SimSun, area-averaged, fixed threshold."""
    R = 16 * SS
    f = ImageFont.truetype(SIMSUN, R)
    img = Image.new('L', (R, R), 0)
    ImageDraw.Draw(img).text((R / 2, R / 2), ch, fill=255, font=f, anchor='mm')
    p = img.resize((16, 16), Image.BOX).load()
    return [[1 if p[x, y] > 255 * thr else 0 for x in range(16)] for y in range(16)]


def close_box_bottom(g):
    """Clear the stray row Unifont leaves under a box-bottom glyph.

    Unifont's 日 白 石 苦 否 出 ... carry the box's bottom line on row 14 and the
    two side strokes still on row 15, so the box reads as open at the bottom.
    Measured over the 966 hanzi the patch draws: 62 glyphs have exactly this
    shape (row 15's ink is a subset of a solid row 14), clearing row 15 closes
    every one of them, and no other glyph in the set is touched.  GLYPH_STRAY=0
    turns it off.
    """
    if os.environ.get('GLYPH_STRAY', '1') == '0':
        return g
    r14, r15 = g[14], g[15]
    if not any(r15) or not any(r14):
        return g
    cols = [x for x in range(16) if r14[x]]
    if cols[-1] - cols[0] + 1 != len(cols) or len(cols) < 5:
        return g                          # row 14 is not one solid run
    if any(r15[x] for x in range(16) if not r14[x]):
        return g                          # row 15 reaches past it
    g[15] = [0] * 16
    return g


def render16x16(ch):
    """-> 16x16 grid of 0/1 (top row first).

    Unifont is a bitmap font designed at exactly 16x16, so its glyphs keep their
    stroke structure (a downsampled outline font such as SimSun loses it: at this
    size 警 collapses into one solid blob, and 日/田 even render identically).
    """
    if ch in _cache16:
        return _cache16[ch]
    if not ch.strip():                    # spaces are coded as $00, never pooled
        g = [[0] * 16 for _ in range(16)]
    else:
        g = _unifont16(ch)
        if g is None or not any(map(any, g)):
            g = _simsun16(ch)
        close_box_bottom(g)
    _cache16[ch] = g
    return g


def renderer16x16_name(ch):
    """Which source actually produced the glyph for ch."""
    if not ch.strip():
        return 'blank'
    g = _unifont16(ch)
    if g is not None and any(map(any, g)):
        return 'unifont'
    return 'simsun'
