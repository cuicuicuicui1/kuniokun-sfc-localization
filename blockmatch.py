"""Match every 8x8 block of the title screenshot against the VRAM tiles, so the
tilemap can be recovered without knowing the BG registers.

For each screen block we search all 1024 tiles at a given character base and all
8 palettes of CGRAM for the tile that reproduces the block pixel for pixel.
Blocks that match tell us the tile index and palette the map word must hold.
"""
import os
import sys

import numpy as np
from PIL import Image

import titlelayer as tl

HW = tl.HW
W, H = 256, 224


def main():
    tag = sys.argv[1]
    shot = sys.argv[2]
    charbase = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x6000
    bpp = int(sys.argv[4]) if len(sys.argv) > 4 else 4

    vram, cgram = tl.load(tag)
    cg = tl.cgram_rgb(cgram)
    tiles = tl.decode_all(vram, charbase, bpp)
    ref = np.asarray(Image.open(shot).convert('RGB'))
    print('ref size', ref.shape, 'charbase %04X bpp %d' % (charbase, bpp))

    # palette p rendered rgb for tile t: cg[p*16 + idx]
    cols, rows = W // 8, H // 8
    grid = np.full((rows, cols), -1, dtype=np.int32)
    pal_grid = np.full((rows, cols), -1, dtype=np.int32)
    amb = 0
    for by in range(rows):
        for bx in range(cols):
            blk = ref[by * 8:(by + 1) * 8, bx * 8:(bx + 1) * 8]
            best = None
            for p in range(8):
                rgb = cg[p * 16 + tiles]              # (1024, 8, 8, 3)
                m = (rgb == blk[None, :, :, :]).all(axis=3).all(axis=2).all(axis=1)
                hit = np.flatnonzero(m)
                if len(hit) == 0:
                    continue
                if best is None:
                    best = (hit[0], p, len(hit))
                else:
                    if hit[0] == best[0]:
                        best = (best[0], best[1], best[2] + len(hit))
                    else:
                        amb += 1
            if best is not None:
                grid[by, bx] = best[0]
                pal_grid[by, bx] = best[1]
    n = (grid >= 0).sum()
    print('blocks matched %d/%d   ambiguous %d' % (n, rows * cols, amb))
    for label, g in (('tile', grid), ('pal', pal_grid)):
        print('--- %s ---' % label)
        for by in range(rows):
            print(' '.join(('%4d' % g[by, bx]) if g[by, bx] >= 0 else '   .' for bx in range(cols)))
    np.save(os.path.join(HW, tag + '_grid.npy'), grid)
    np.save(os.path.join(HW, tag + '_palgrid.npy'), pal_grid)


if __name__ == '__main__':
    main()