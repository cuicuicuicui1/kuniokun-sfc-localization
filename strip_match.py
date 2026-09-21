"""Match the band's 8x8 tiles against a blob (VRAM dump or the ROM font block).

Palette independent: the mapping pattern->colour must be a function (same index
=> same RGB) and colour->pattern injective (same RGB => same index), so a tile
can only match if it is the actual source.
"""
import sys
from PIL import Image

def tile_pattern(px, x0, y0):
    """(rgb tuple list, colour ids) for an 8x8 block."""
    rgb = []
    for y in range(8):
        for x in range(8):
            rgb.append(px[x0 + x, y0 + y])
    ids = {}
    pat = []
    for c in rgb:
        if c not in ids:
            ids[c] = len(ids)
        pat.append(ids[c])
    return pat, rgb

def decode2(b, off):
    out = []
    for y in range(8):
        lo = b[off + y * 2]; hi = b[off + y * 2 + 1]
        for x in range(8):
            bit = 7 - x
            out.append(((lo >> bit) & 1) | (((hi >> bit) & 1) << 1))
    return out

def decode4(b, off):
    out = []
    for y in range(8):
        p0 = b[off + y * 2]; p1 = b[off + y * 2 + 1]
        p2 = b[off + 16 + y * 2]; p3 = b[off + 16 + y * 2 + 1]
        for x in range(8):
            bit = 7 - x
            out.append(((p0 >> bit) & 1) | (((p1 >> bit) & 1) << 1)
                       | (((p2 >> bit) & 1) << 2) | (((p3 >> bit) & 1) << 3))
    return out

def compatible(pat, rgb, idx):
    """pat = screenshot colour ids, idx = tile index pattern."""
    p2c, c2p = {}, {}
    for a, b, c in zip(pat, rgb, idx):
        if b in p2c and p2c[b] != c:
            return False
        p2c[b] = c
        if c in c2p and c2p[c] != a:
            return False
        c2p[c] = a
    return True

def scan(blob, pat, rgb, bpp):
    step = 16 if bpp == 2 else 32
    dec = decode2 if bpp == 2 else decode4
    hits = []
    for off in range(0, len(blob) - step + 1, step):
        if compatible(pat, rgb, dec(blob, off)):
            hits.append(off // step)
    return hits

def main():
    png, ytop = sys.argv[1], int(sys.argv[2])
    blobs = [(n, open(p, 'rb').read()) for n, p in
             (a.split('=') for a in sys.argv[3:])]
    im = Image.open(png).convert('RGB'); px = im.load()
    for col in range(0, 32):
        pat, rgb = tile_pattern(px, col * 8, ytop)
        line = 'col%02d x=%3d ' % (col, col * 8)
        for name, blob in blobs:
            h2 = scan(blob, pat, rgb, 2)
            h4 = scan(blob, pat, rgb, 4)
            line += '%s: 2bpp=%s 4bpp=%s  ' % (name, h2[:4], h4[:4])
        print(line)

main()
