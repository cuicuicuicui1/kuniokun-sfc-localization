"""Objective legibility proxy: character separability.

For every candidate pipeline, render all 971 translated glyphs, then simulate
what the user's display does (2.634x BILINEAR upscale -> area-average back down,
i.e. blur + eye integration) and measure how far each glyph stays from its
nearest neighbour among all the other glyphs.

A renderer that breaks strokes into speckle collapses different characters onto
each other (small nearest-neighbour distances) - that is what "looks like
garbage" means objectively.  Also reports binary-glyph (pre-blur) distances.
"""
import json
import os
import sys

import numpy as np
from PIL import Image

BASE = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon'
sys.path.insert(0, BASE)
import fontcmp as F                                     # noqa: E402

SCALE = 2.634          # user's snes9x window scale (674/256)


def perceived(g):
    """8x16 binary grid -> blurred 8x16 float grid (display + eye model)."""
    im = Image.new('L', (8, 16), 0)
    px = im.load()
    for y in range(16):
        for x in range(8):
            if g[y][x]:
                px[x, y] = 255
    up = im.resize((int(round(8 * SCALE)), int(round(16 * SCALE))), Image.BILINEAR)
    back = up.resize((8, 16), Image.BOX)
    return np.asarray(back, dtype=np.float64) / 255.0


def analyse(name, fn, chars, cache):
    vecs, raw = [], []
    for ch in chars:
        key = (name, ch)
        if key not in cache:
            g = fn(ch)
            if g is None:
                cache[key] = None
            else:
                cache[key] = (np.array(g, dtype=np.float64).ravel(), perceived(g).ravel())
        v = cache[key]
        if v is None:
            continue
        raw.append(v[0])
        vecs.append(v[1])
    raw = np.array(raw)
    V = np.array(vecs)
    out = {}
    for label, M in (('binary', raw), ('blurred', V)):
        n = M.shape[0]
        # pairwise L2 via |a-b|^2 = |a|^2+|b|^2-2ab ; chunked to stay light
        sq = (M * M).sum(1)
        best = np.full(n, np.inf)
        for i in range(0, n, 128):
            blk = M[i:i + 128]
            d2 = sq[i:i + 128, None] + sq[None, :] - 2.0 * blk.dot(M.T)
            np.fill_diagonal(d2[:, i:i + 128], np.inf)
            best[i:i + 128] = d2.min(1)
        d = np.sqrt(np.maximum(best, 0))
        out[label] = (float(d.mean()), float(np.percentile(d, 5)), float(d.min()))
    return out, len(raw)


def main():
    chars = F.load_chars()
    print('chars: %d   (blur model: %.3fx bilinear, as the user display)' % (len(chars), SCALE))
    print('%-32s %8s %8s %8s | %8s %8s %8s' %
          ('pipeline', 'nn-mean', 'nn-p5', 'nn-min', 'bl-mean', 'bl-p5', 'bl-min'))
    cache = {}
    for name, fn in F.PIPES:
        res, n = analyse(name, fn, chars, cache)
        b = res['binary']
        v = res['blurred']
        print('%-32s %8.2f %8.2f %8.2f | %8.3f %8.3f %8.3f'
              % (name, b[0], b[1], b[2], v[0], v[1], v[2]))
    print()
    print('nn-*: distance to nearest other character (binary, Hamming-ish)')
    print('bl-*: same after the display blur (0..1 scale). min = most confusable pair.')


if __name__ == '__main__':
    main()