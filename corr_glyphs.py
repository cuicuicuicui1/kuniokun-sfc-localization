"""Correlation matcher for 8x16 glyph cells, robust to the non-integer
upscaling/filtering in the user's snes9x screenshot.

Validated end-to-end: on my own native frame the 5 Chinese cells match the pool
glyphs with correlation 1.000, and the same geometry still recovers them
(0.95-1.00) after simulating the user's window scaling with NEAREST/BILINEAR/
BICUBIC resampling.

Usage:
  python corr_glyphs.py self     # sanity: my own native frame (s=1, ox=0, oy=0)
  python corr_glyphs.py sim      # my frame pushed through the window geometry
  python corr_glyphs.py user     # geometry search + decode of the user's shot
"""
import sys
import numpy as np
from PIL import Image

sys.path.insert(0, 'C:/Users/<user>/.zcode/workspace/default/sfc-recon')
import decode_shot as ds

MYFRAME = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/v29a_f01390.png'
SHOT = ("C:/Users/<user>/.zcode/cli/image-cache/"
        "sess_2d6e90fa-48ba-457c-9ffa-65d2cb3a2d7a/"
        "image-29129c7e5361e3776ae9e09dd4a1ea0f.png")

slots, pages, pool_label, char_of, orig_label = ds.load_tables()

NAMES, VECS = [], []
for bits, (_page, _s) in pool_label.items():
    label = char_of.get((_page, _s))
    if label is None:
        label = 'p%d/s%02X' % (_page, _s)
    NAMES.append('POOL %s' % label)
    VECS.append([float(b) for b in bits])
for bits, code in orig_label.items():
    NAMES.append('ORIG %02X' % code)
    VECS.append([float(b) for b in bits])

M = np.array(VECS, dtype=np.float64)
M -= M.mean(axis=1, keepdims=True)
nrm = np.sqrt((M * M).sum(axis=1, keepdims=True))
M = M / np.where(nrm == 0, 1.0, nrm)
print('candidates: pool=%d orig=%d' % (len(pool_label), len(orig_label)))


class Sampler(object):
    def __init__(self, path):
        im = Image.open(path).convert('L')
        self.w, self.h = im.size
        a = np.asarray(im, dtype=np.float64)
        # summed-area table for O(1) area averages
        self.sat = np.zeros((self.h + 1, self.w + 1))
        self.sat[1:, 1:] = a.cumsum(axis=0).cumsum(axis=1)

    def area(self, x0, y0, x1, y1):
        x0 = int(np.clip(round(x0), 0, self.w))
        x1 = int(np.clip(round(x1), 0, self.w))
        y0 = int(np.clip(round(y0), 0, self.h))
        y1 = int(np.clip(round(y1), 0, self.h))
        if x1 <= x0 or y1 <= y0:
            return 0.0
        s = (self.sat[y1, x1] - self.sat[y0, x1]
             - self.sat[y1, x0] + self.sat[y0, x0])
        return s / float((x1 - x0) * (y1 - y0))

    def cell(self, ox, oy, s, col, row):
        x0 = ox + s * (24 + col * 8)
        y0 = oy + s * (183 + row * 16)
        out = np.empty(128)
        k = 0
        for gy in range(16):
            ay0 = y0 + s * gy
            for gx in range(8):
                out[k] = self.area(x0 + s * gx, ay0, x0 + s * (gx + 1),
                                   ay0 + s)
                k += 1
        return out


def match(vec, topn=3):
    v = vec - vec.mean()
    n = np.sqrt((v * v).sum())
    if n == 0:
        return []
    dots = (M @ v) / n
    idx = np.argsort(-dots)[:topn]
    return [(float(dots[i]), NAMES[i]) for i in idx]


def scan(smp, ox, oy, s, rows=(0,), cols=range(0, 26), show=True, minrng=20):
    tot, n = 0.0, 0
    for row in rows:
        for col in cols:
            v = smp.cell(ox, oy, s, col, row)
            if v.max() - v.min() < minrng:
                if show:
                    print('  row%d col%02d (blank)' % (row, col))
                continue
            b = match(v, 3)
            n += 1
            tot += b[0][0]
            if show:
                print('  row%d col%02d | %s' % (row, col,
                      ' | '.join('%s %.3f' % (nm, d) for d, nm in b)))
    return (tot / n if n else -9.0), n


def geom_search(smp, oxs, oys, s, rows=(0,), cols=range(0, 26), minrng=20):
    bestg = None
    for ox in oxs:
        for oy in oys:
            avg, n = scan(smp, ox, oy, s, rows=rows, cols=cols, show=False,
                          minrng=minrng)
            if bestg is None or avg > bestg[0]:
                bestg = (avg, ox, oy, n)
    return bestg


def make_sim(resample, path):
    base = Image.open(MYFRAME).convert('L')
    s = 2.634
    win = base.resize((int(round(256 * s)), int(round(224 * s))), resample)
    canvas = Image.new('L', (1028, 642), 0)
    canvas.paste(win, (177, 52))
    canvas.save(path)
    return path


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'self'
    if mode == 'self':
        smp = Sampler(MYFRAME)
        print('=== my native frame (s=1 ox=0 oy=0) ===')
        scan(smp, 0, 0, 1.0, rows=(0,), cols=range(0, 13))
    elif mode == 'sim':
        for tag, rs in (('NEAREST', Image.NEAREST),
                        ('BILINEAR', Image.BILINEAR),
                        ('BICUBIC', Image.BICUBIC)):
            smp = Sampler(make_sim(rs, 'hw/sim_%s.png' % tag))
            print('=== simulated window (%s), ox=177 oy=52 s=2.634 ===' % tag)
            scan(smp, 177, 52, 2.634, rows=(0,), cols=range(0, 13))
            print()
    else:
        smp = Sampler(SHOT)
        oxs = [x / 8.0 for x in range(1384, 1456)]   # 173.0 .. 181.875
        oys = [x / 8.0 for x in range(392, 448)]     # 49.0 .. 55.875
        print('=== geometry search on user shot (%d x %d grid) ==='
              % (len(oxs), len(oys)))
        bestg = geom_search(smp, oxs, oys, 2.634)
        print('BEST: avg=%.3f ox=%.3f oy=%.3f cells=%d' % bestg)
        print()
        print('=== per-cell decode at best geometry ===')
        scan(smp, bestg[1], bestg[2], 2.634, rows=(0, 1))


if __name__ == '__main__':
    main()