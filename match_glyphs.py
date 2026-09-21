"""Match glyph cells in the user's snes9x screenshot against
(a) my Chinese glyph pool, and (b) the original JP font.

The screenshot is a non-integer upscale (674/256 = 2.633) => snes9x filtered it,
so exact bitmap comparison cannot work.  Instead each cell is sampled as an
area-averaged grayscale 8x16 matrix and compared by normalized correlation.
"""
import sys
from PIL import Image

sys.path.insert(0, 'C:/Users/<user>/.zcode/workspace/default/sfc-recon')
import decode_shot as ds

SHOT = ("C:/Users/<user>/.zcode/cli/image-cache/"
        "sess_2d6e90fa-48ba-457c-9ffa-65d2cb3a2d7a/"
        "image-29129c7e5361e3776ae9e09dd4a1ea0f.png")

slots, pages, pool_label, char_of, orig_label = ds.load_tables()

# ---- collect every candidate glyph as a binary 8x16 mask -------------------
CAND = []          # (label, flat list of 128 0/1)
for key, label in pool_label.items():
    CAND.append(('POOL ' + str(label), key))
for key, label in orig_label.items():
    CAND.append(('ORIG ' + str(label), key))


def norm(v):
    m = sum(v) / len(v)
    d = [x - m for x in v]
    n = sum(x * x for x in d) ** 0.5
    if n == 0:
        return None
    return [x / n for x in d]


CANDN = []
for name, bits in CAND:
    nv = norm([float(b) for b in bits])
    if nv:
        CANDN.append((name, nv))
print('candidate glyphs (pool %d + orig %d) -> usable %d'
      % (len(pool_label), len(orig_label), len(CANDN)))


def sample_cell(px, ox, oy, s, col, row):
    """Area-averaged grayscale 8x16 cell in native coords."""
    x0 = ox + s * (24 + col * 8)
    y0 = oy + s * (183 + row * 16)
    out = []
    for gy in range(16):
        for gx in range(8):
            ax0 = x0 + s * gx
            ay0 = y0 + s * gy
            ax1 = ax0 + s
            ay1 = ay0 + s
            tot = 0.0
            cnt = 0
            for yy in range(int(ay0), int(ay1 - 1e-9) + 1):
                if yy < 0 or yy >= 642:
                    continue
                for xx in range(int(ax0), int(ax1 - 1e-9) + 1):
                    if xx < 0 or xx >= 1028:
                        continue
                    tot += px[xx, yy]
                    cnt += 1
            out.append(tot / cnt if cnt else 0.0)
    return out


def best_match(vec, topn=3):
    nv = norm(vec)
    if nv is None:
        return []
    res = []
    for name, cv in CANDN:
        dot = sum(a * b for a, b in zip(nv, cv))
        res.append((dot, name))
    res.sort(reverse=True)
    return res[:topn]


def main():
    im = Image.open(SHOT).convert('L')
    px = im.load()
    s = 2.633
    # geometry search: maximise the best correlation found on text-bearing cells
    best = None
    for oxi in range(174, 182):
        for oyi in (x / 4.0 for x in range(196, 216)):
            score = 0.0
            hits = 0
            for row in range(0, 3):
                for col in range(0, 26):
                    v = sample_cell(px, oxi, oyi, s, col, row)
                    rng = max(v) - min(v)
                    if rng < 25:
                        continue          # blank cell
                    hits += 1
                    b = best_match(v, 1)
                    if b:
                        score += b[0][0]
            avg = (score / hits) if hits else -9
            if best is None or avg > best[0]:
                best = (avg, oxi, oyi, hits)
            print('ox=%d oy=%.2f  cells=%d avgcorr=%.3f' % (oxi, oyi, hits, avg))
    print()
    print('BEST GEOMETRY: avgcorr=%.3f ox=%d oy=%.2f cells=%d' % best)
    avg, ox, oy, hits = best
    print()
    print('--- per-cell best matches at that geometry ---')
    for row in range(0, 3):
        for col in range(0, 26):
            v = sample_cell(px, ox, oy, s, col, row)
            rng = max(v) - min(v)
            line = 'row%d col%02d rng=%3d ' % (row, col, rng)
            if rng < 25:
                print(line + '(blank)')
                continue
            b = best_match(v, 3)
            line += ' | '.join('%s %.3f' % (n, d) for d, n in b)
            print(line)


if __name__ == '__main__':
    main()