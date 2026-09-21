"""Recover the title screen's tilemap without trusting CGRAM.

CGRAM reads through BizHawk's SNES domain came back near-empty, so colours are
unusable.  Instead each screen block and each candidate tile is reduced to a
*partition* of its 64 pixels (which pixels share a colour / share a colour
index).  A tile matches a block when the two partitions are identical, which is
invariant under any palette assignment -- and the palette can be recovered
afterwards from the size of the partition.
"""
import os
import sys

import numpy as np
from PIL import Image

import titlelayer as tl

HW = tl.HW
W, H = 256, 224


def canon(a):
    """Relabel values by order of first appearance, row-major."""
    flat = a.reshape(-1)
    order = {}
    out = np.empty(flat.shape, dtype=np.int32)
    for i, v in enumerate(flat):
        k = order.get(int(v))
        if k is None:
            k = len(order)
            order[int(v)] = k
        out[i] = k
    return out.reshape(a.shape), len(order)


def block_canon(blk):
    """Canonical ids per pixel plus the actual colour of each id."""
    flat = blk.reshape(-1, 3)
    seen = {}
    ids = np.empty(64, dtype=np.int32)
    cols = []
    for i in range(64):
        c = (int(flat[i][0]), int(flat[i][1]), int(flat[i][2]))
        k = seen.get(c)
        if k is None:
            k = len(seen)
            seen[c] = k
            cols.append(c)
        ids[i] = k
    return ids.reshape(8, 8), cols


def main():
    tag, shot = sys.argv[1], sys.argv[2]
    charbase = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x6000
    bpp = int(sys.argv[4]) if len(sys.argv) > 4 else 4
    phase = int(sys.argv[5]) if len(sys.argv) > 5 else 0
    vram, _ = tl.load(tag)
    tiles = tl.decode_all(vram, charbase, bpp)
    tcanon = []
    for t in range(1024):
        c, n = canon(tiles[t])
        tcanon.append((c, n, tiles[t]))
    ref = np.asarray(Image.open(shot).convert('RGB'))
    cols, rows = W // 8, H // 8

    grid = np.full((rows, cols), -1, dtype=np.int32)
    ncol = np.zeros((rows, cols), dtype=np.int32)
    ambig = 0
    for by in range(rows):
        for bx in range(cols):
            y0 = by * 8 + phase
            x0 = bx * 8 + phase
            if y0 + 8 > H or x0 + 8 > W:
                continue
            b, bcols = block_canon(ref[y0:y0 + 8, x0:x0 + 8])
            hits = [t for t in range(1024) if tcanon[t][1] == len(bcols) and np.array_equal(tcanon[t][0], b)]
            if len(hits) == 1:
                grid[by, bx] = hits[0]
                ncol[by, bx] = len(bcols)
            elif len(hits) > 1:
                ambig += 1
                grid[by, bx] = hits[0]
                ncol[by, bx] = len(bcols)
    n = (grid >= 0).sum()
    print('phase %d: unique %d  ambiguous %d  blank %d' % (phase, n - ambig, ambig, rows * cols - n))
    if n:
        print('--- tile (row = block row) ---')
        for by in range(rows):
            print(' '.join(('%4d' % grid[by, bx]) if grid[by, bx] >= 0 else '   .' for bx in range(cols)))
        print('--- colour count per block ---')
        for by in range(rows):
            print(' '.join(('%4d' % ncol[by, bx]) if grid[by, bx] >= 0 else '   .' for bx in range(cols)))
        np.save(os.path.join(HW, '%s_grid_p%d.npy' % (tag, phase)), grid)
        np.save(os.path.join(HW, '%s_ncol_p%d.npy' % (tag, phase)), ncol)


if __name__ == '__main__':
    main()