"""py27.py -- compare the displayed pixels of a dialogue cell with the glyph pool.

The Lua side (hw/v27.lua) saved two screenshots one frame apart, with the VRAM
tile used by the first dialogue's 5th column cell replaced by a solid pattern in
between.  The pixels that differ between the two shots are therefore exactly
that cell's rectangle on screen; the pixels inside that rectangle in the first
shot must be the character whose glyph was built into the pool.

Everything here is numeric comparison - no looking at pictures.
"""
import sys
from PIL import Image

A = Image.open('hw/v27a_A.png').convert('RGB')
B = Image.open('hw/v27a_B.png').convert('RGB')
print('screenshots', A.size, B.size)
pa, pb = A.load(), B.load()
W, H = A.size

diff = [(x, y) for y in range(H) for x in range(W) if pa[x, y] != pb[x, y]]
if not diff:
    sys.exit('no pixel changed after poking the tile -- the cell is not displayed')
xs = [p[0] for p in diff]
ys = [p[1] for p in diff]
x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
print('diff pixels %d  bbox x %d..%d  y %d..%d  (%dx%d)'
      % (len(diff), x0, x1, y0, y1, x1 - x0 + 1, y1 - y0 + 1))

# the tile 0x9C of the first dialogue is the glyph of the 5th column cell, which
# identify_scene.py resolved to U+732A (the pool offset is the build formula)
rom = open('kuniokun_cn.smc', 'rb').read()
POOL = 0x108000 + 6 * 0x8000 + 0x3F * 32
g = rom[POOL:POOL + 32]
print('pool bytes @0x%06X: %s' % (POOL, g.hex(' ')))
expected = [[(g[r * 2 + t * 16 + (c >> 3)] >> (7 - (c & 7))) & 1
             for c in range(8)] for r in range(16) for t in (0, 1)] if False else None

# 16 words, two stacked 8x8 tiles, 2bpp, MSB leftmost: word r = rows -> bits
bits = []
for r in range(16):
    tile = r // 8
    row = r % 8
    lo = g[tile * 16 + row * 2]
    hi = g[tile * 16 + row * 2 + 1]
    bits.append([((hi >> (7 - c)) & 1) * 2 + ((lo >> (7 - c)) & 1) for c in range(8)])

print('expected glyph (1 = stroke, 2 = shadow/anti-alias colour, . = empty):')
for r in range(16):
    print('   ' + ''.join('.o#'[bits[r][c]] for c in range(8)))

# the cell rectangle: the poke changed exactly that cell, so take the bbox and
# check its size and the lit pixels inside it
if (x1 - x0 + 1, y1 - y0 + 1) != (8, 16):
    print('WARNING: bbox is not one 8x16 cell -- other tiles share this tile number')
    print('         diff columns:', sorted(set(xs)), 'rows:', sorted(set(ys)))


def bright(px):
    return sum(px) > 300


mismatch = 0
rows_txt = []
for r in range(16):
    y = y0 + r
    line = ''
    for c in range(8):
        x = x0 + c
        lit = bright(pa[x, y])
        want = bits[r][c] != 0
        line += '#' if lit else '.'
        if lit != want:
            mismatch += 1
    rows_txt.append(line)
print('displayed pixels inside that cell:')
for t in rows_txt:
    print('   ' + t)
print('mismatching pixels: %d of %d' % (mismatch, 8 * 16))
print('RESULT:', 'DISPLAYED GLYPH MATCHES THE POOL' if mismatch == 0 else 'MISMATCH')