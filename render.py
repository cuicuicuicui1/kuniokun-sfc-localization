#!/usr/bin/env python3
"""Render arbitrary ROM regions as tile sheets so we can visually identify fonts."""
import os, sys
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from recon2 import decode_tile2bpp, decode_tile4bpp

def render(body, offsets, bpt, dec, ntiles, cols, scale, path, gap=4):
    """offsets: list of (label, off). Stacks each region as its own band."""
    rows = (ntiles + cols - 1) // cols
    bandw = cols * 8 * scale
    bandh = rows * 8 * scale
    W = bandw
    H = len(offsets) * (bandh + gap)
    img = Image.new('L', (W, H), 210)
    px = img.load()
    ybase = 0
    for label, off in offsets:
        for t in range(ntiles):
            o = off + t * bpt
            if o + bpt > len(body): break
            g = dec(body, o)
            cx = (t % cols) * 8 * scale
            cy = ybase + (t // cols) * 8 * scale
            for y in range(8):
                for x in range(8):
                    v = g[y][x]
                    lum = 255 if v == 0 else (0 if v >= 3 else 255 - v * 85)
                    for dy in range(scale):
                        for dx in range(scale):
                            px[cx + x*scale + dx, cy + y*scale + dy] = lum
        ybase += bandh + gap
    img.save(path)
    print('%s  bands=%s' % (os.path.basename(path), [l for l, _ in offsets]))

if __name__ == '__main__':
    path = sys.argv[1]
    raw = open(path, 'rb').read()
    ch = 512 if len(raw) % 32768 == 512 else 0
    body = raw[ch:]
    # argv: tag bpt off1 off2 ...
    tag = sys.argv[2]; bpt = int(sys.argv[3])
    offs = [('0x%06X' % int(a, 16), int(a, 16)) for a in sys.argv[4:]]
    dec = decode_tile2bpp if bpt == 16 else decode_tile4bpp
    render(body, offs, bpt, dec, 256, 32, 3, 'view_%s_%dbpp.png' % (tag, bpt * 0 + (2 if bpt == 16 else 4)))