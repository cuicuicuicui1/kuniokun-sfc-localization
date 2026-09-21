"""py28.py -- pixel-level proof: the screen pixels inside the dialogue cells are
the Chinese glyph bytes from the pool, not the Japanese font.

Inputs (from two deterministic BizHawk runs, hw/v28.lua):
  hw/v28n_A.png / hw/v28n_C.png  -- frames 1398 / 1399, no poke
  hw/v28p_A.png / hw/v28p_B.png  -- frames 1398 / 1399, tile 0x9C filled with FF
                                     right after the first shot of run 2
The game animates by itself, so the poke's own effect is
    (pixels that differ between A and B)  minus  (pixels that differ A to C).
Each isolated island of changed pixels is then compared against both the pool
glyph and the original Japanese font tile of that number.
"""
from PIL import Image

rom = open('kuniokun_cn.smc', 'rb').read()


def load(p):
    return Image.open(p).convert('RGB').load()


def diff(p1, p2):
    W, H = 256, 224
    return {(x, y) for y in range(H) for x in range(W) if p1[x, y] != p2[x, y]}


A = load('hw/v28p_A.png')
B = load('hw/v28p_B.png')
An = load('hw/v28n_A.png')
C = load('hw/v28n_C.png')

print('cross-run determinism: frame 1398 of both runs differs in %d pixels'
      % len(diff(A, An)))
d_game = diff(An, C)
d_poke = diff(A, B)
print('game alone changes %d pixels in one frame; game+poke changes %d'
      % (len(d_game), len(d_poke)))
iso = d_poke - d_game
print('isolated poke effect: %d pixels' % len(iso))
if not iso:
    raise SystemExit('poke changed nothing on screen -- these tiles are not displayed')

# island grouping: same row, adjacent columns
rem = set(iso)
islands = []
while rem:
    seed = min(rem, key=lambda p: (p[1], p[0]))
    stack = [seed]
    isl = set()
    while stack:
        p = stack.pop()
        if p not in rem:
            continue
        rem.discard(p)
        isl.add(p)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (p[0] + dx, p[1] + dy)
            if q in rem:
                stack.append(q)
    islands.append(isl)

islands.sort(key=lambda s: -len(s))
print('%d island(s)' % len(islands))


def mask_of(buf32):
    bits = []
    for r in range(16):
        t, row = r // 8, r % 8
        lo, hi = buf32[t * 16 + row * 2], buf32[t * 16 + row * 2 + 1]
        bits.append([((hi >> (7 - c)) & 1) * 2 + ((lo >> (7 - c)) & 1) for c in range(8)])
    return bits


POOL_ZHU = rom[0x108000 + 6 * 0x8000 + 0x3F * 32:0x108000 + 6 * 0x8000 + 0x3F * 32 + 32]
ORIG_9C = rom[0x0F8000 + 0x9C * 16:0x0F8000 + 0x9C * 16 + 16] + rom[0x0F8000 + 0x9D * 16:0x0F8000 + 0x9D * 16 + 16]


def show(bits, name):
    print('  %s' % name)
    for r in bits:
        print('     ' + ''.join('.o#'[v] for v in r))


show(mask_of(POOL_ZHU), 'pool glyph of the 5th cell (tile pair 0x9C/0x9D)')
show(mask_of(ORIG_9C), 'original Japanese font, same tile pair')

for n, isl in enumerate(islands):
    xs = [p[0] for p in isl]
    ys = [p[1] for p in isl]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    print('island %d: %d px  bbox x %d..%d  y %d..%d  (%dx%d)'
          % (n, len(isl), x0, x1, y0, y1, x1 - x0 + 1, y1 - y0 + 1))
    if (x1 - x0 + 1, y1 - y0 + 1) != (8, 16):
        print('   not a character cell')
        continue
    for label, ref in (('pool', mask_of(POOL_ZHU)), ('orig', mask_of(ORIG_9C))):
        bad = 0
        for r in range(16):
            for c in range(8):
                lit = sum(A[x0 + c, y0 + r]) > 300
                if lit != (ref[r][c] != 0):
                    bad += 1
        print('   vs %s glyph: %d/128 pixels differ%s'
              % (label, bad, '   <== MATCH' if bad == 0 else ''))
    print('   on-screen pixels:')
    for r in range(16):
        print('     ' + ''.join('#' if sum(A[x0 + c, y0 + r]) > 300 else '.' for c in range(8)))