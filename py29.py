"""py29.py -- find the Chinese glyphs on the visible screen by template match.

No simulator pokes: for every frame captured by hw/v29.lua, slide the expected
8x16 masks of the first dialogue's five characters over the whole 256x224 screen
and count mismatching "lit" pixels.  A perfect match is direct proof that those
pixels on screen are the built glyphs.  The brightest mask is used, so a match
cannot be a coincidence of blank areas.
"""
import glob
import os
import re
from PIL import Image

rom = open('kuniokun_cn.smc', 'rb').read()


def mask_of(buf32):
    bits = []
    for r in range(16):
        t, row = r // 8, r % 8
        lo, hi = buf32[t * 16 + row * 2], buf32[t * 16 + row * 2 + 1]
        bits.append([((hi >> (7 - c)) & 1) * 2 + ((lo >> (7 - c)) & 1) for c in range(8)])
    return bits


CELLS = [('zhu', 6, 0x3F), ('rou', 8, 0x49), ('bao', 1, 0x01), ('yi', 0, 0x15), ('ge', 0, 0x29)]
masks = {}
for name, page, slot in CELLS:
    off = 0x108000 + page * 0x8000 + slot * 32
    m = mask_of(rom[off:off + 32])
    lit = sum(1 for r in m for v in r if v)
    masks[name] = (m, lit)
    print('%s: %d lit pixels of 128' % (name, lit))

W, H = 256, 224
pat = os.getenv('HW_TAG', 'v29')
files = sorted(glob.glob('hw/%s*_f*.png' % pat))
print('%d frames' % len(files))
for path in files:
    f = int(re.search(r'_f(\d+)\.png$', path).group(1))
    px = Image.open(path).convert('RGB').load()
    lit = [[sum(px[x, y]) > 300 for x in range(W)] for y in range(H)]
    out = []
    for name, page, slot in CELLS:
        m, _ = masks[name]
        best, spot = 999, None
        for y0 in range(H - 15):
            for x0 in range(W - 7):
                bad = 0
                for r in range(16):
                    row = lit[y0 + r]
                    mr = m[r]
                    for c in range(8):
                        if row[x0 + c] != (mr[c] != 0):
                            bad += 1
                            if bad >= best:
                                break
                    if bad >= best:
                        break
                if bad < best:
                    best, spot = bad, (x0, y0)
                    if best == 0:
                        break
            if best == 0:
                break
        out.append('%s:%s@%s' % (name, 'EXACT' if best == 0 else 'best%d' % best, spot))
    print('F=%d  %s' % (f, '  '.join(out)))