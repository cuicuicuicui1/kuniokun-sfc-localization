"""Recover the title screen's tilemap without trusting CGRAM or the PPU registers.

Each screen block and each candidate tile is reduced to a *partition* of its 64
pixels (which pixels share a colour / share a colour index).  A tile matches a
block when the two partitions are identical, which is invariant under any
palette assignment.  All 64 pixel phases are tried, because a BG scroll need not
be a multiple of eight.
"""
import os
import sys

import numpy as np
from PIL import Image

import titlelayer as tl

HW = tl.HW
W, H = 256, 224


def canon_bytes(a):
    """Relabel by first appearance (row-major) and return the labels as bytes."""
    flat = a.reshape(-1)
    order = {}
    out = bytearray(len(flat))
    for i in range(len(flat)):
        v = int(flat[i])
        k = order.get(v)
        if k is None:
            k = len(order)
            order[v] = k
        out[i] = k
    return bytes(out), len(order)


def main():
    tag, shot = sys.argv[1], sys.argv[2]
    charbase = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x6000
    bpp = int(sys.argv[4]) if len(sys.argv) > 4 else 4
    y0lim = int(sys.argv[5]) if len(sys.argv) > 5 else 0
    vram, _ = tl.load(tag)
    tiles = tl.decode_all(vram, charbase, bpp)
    index = {}
    for t in range(len(tiles)):
        key, n = canon_bytes(tiles[t])
        index.setdefault((key, n), []).append(t)
    print('tiles at %04X: %d  distinct patterns: %d' % (charbase, len(tiles), len(index)))

    ref = np.asarray(Image.open(shot).convert('RGB'))
    best = None
    for py in range(8):
        for px in range(8):
            hits = {}
            uniq = amb = miss = 0
            for by in range(y0lim // 8, (H - 8 - py) // 8 + 1):
                for bx in range(0, (W - 8 - px) // 8 + 1):
                    blk = ref[by * 8 + py:by * 8 + py + 8, bx * 8 + px:bx * 8 + px + 8]
                    key, n = canon_bytes(blk)
                    cand = index.get((key, n))
                    if cand is None:
                        miss += 1
                    elif len(cand) == 1:
                        uniq += 1
                        hits[(by, bx)] = cand[0]
                    else:
                        amb += 1
                        hits[(by, bx)] = cand[0]
            print('phase (%d,%d): unique %3d  ambiguous %3d  miss %3d' % (px, py, uniq, amb, miss))
            if best is None or uniq > best[0]:
                best = (uniq, px, py, dict(hits))
    uniq, px, py, hits = best
    print('--- best phase (%d,%d) with %d unique blocks ---' % (px, py, uniq))
    for by in range(H // 8):
        print(' '.join(('%4d' % hits[(by, bx)]) if (by, bx) in hits else '   .' for bx in range(W // 8)))
    np.save(os.path.join(HW, '%s_hits_c%04X_b%d.npy' % (tag, charbase, bpp)),
            np.array([[hits.get((by, bx), -1) for bx in range(W // 8)] for by in range(H // 8)]))


if __name__ == '__main__':
    main()