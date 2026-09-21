"""Find which blob a screenshot row's 8x8 tiles come from, trying every
horizontal alignment (the field BG scroll need not be tile aligned)."""
import sys
from PIL import Image

def tile_pat(px, x0, y0):
    rgb = [px[x0 + x, y0 + y] for y in range(8) for x in range(8)]
    ids, pat = {}, []
    for c in rgb:
        if c not in ids: ids[c] = len(ids)
        pat.append(ids[c])
    return pat, rgb

def dec2(b, o):
    out = []
    for y in range(8):
        lo, hi = b[o + y*2], b[o + y*2 + 1]
        for x in range(8):
            bit = 7 - x
            out.append(((lo >> bit) & 1) | (((hi >> bit) & 1) << 1))
    return out

def dec4(b, o):
    out = []
    for y in range(8):
        p0, p1 = b[o + y*2], b[o + y*2 + 1]
        p2, p3 = b[o + 16 + y*2], b[o + 16 + y*2 + 1]
        for x in range(8):
            bit = 7 - x
            out.append(((p0 >> bit) & 1) | (((p1 >> bit) & 1) << 1)
                       | (((p2 >> bit) & 1) << 2) | (((p3 >> bit) & 1) << 3))
    return out

def ok(pat, rgb, idx):
    p2c, c2p = {}, {}
    for a, b, c in zip(pat, rgb, idx):
        if p2c.get(b, c) != c or c2p.get(c, a) != a: return False
        p2c[b] = c; c2p[c] = a
    return True

def scan(blob, pat, rgb, bpp, limit=6):
    step, dec = (16, dec2) if bpp == 2 else (32, dec4)
    hits = []
    for o in range(0, len(blob) - step + 1, step):
        if ok(pat, rgb, dec(blob, o)):
            hits.append(o // step)
            if len(hits) >= limit: break
    return hits

png, ytop = sys.argv[1], int(sys.argv[2])
blobs = [(a.split('=')[0], open(a.split('=')[1], 'rb').read()) for a in sys.argv[3:]]
im = Image.open(png).convert('RGB'); px = im.load()
for dx in range(8):
    hits2 = {n: 0 for n, _ in blobs}; hits4 = {n: 0 for n, _ in blobs}
    sample = {}
    for col in range(1, 31):            # skip the two edge tiles
        pat, rgb = tile_pat(px, col * 8 + dx, ytop)
        for n, blob in blobs:
            h2 = scan(blob, pat, rgb, 2, 3); h4 = scan(blob, pat, rgb, 4, 3)
            if h2: hits2[n] += 1; sample.setdefault(('2', n), (col, h2))
            if h4: hits4[n] += 1; sample.setdefault(('4', n), (col, h4))
    print('dx=%d  2bpp: %s   4bpp: %s' % (dx, hits2, hits4))
    for k, v in sorted(sample.items()):
        print('     sample %s %s col%d -> %s' % (k[0], k[1], v[0], v[1]))
