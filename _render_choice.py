"""Render a VRAM map region as a PNG using 2bpp tiles from a char base.

    python _render_choice.py <vram.bin> <mapword_hex> <rows> <cols> <out.png> [charbyte_hex]
"""
import sys
from PIL import Image

v = open(sys.argv[1], 'rb').read()
base = int(sys.argv[2], 16)
rows = int(sys.argv[3])
cols = int(sys.argv[4])
out = sys.argv[5]
char = int(sys.argv[6], 16) if len(sys.argv) > 6 else 0xC000

PAL = [(255, 255, 255), (170, 170, 170), (85, 85, 85), (0, 0, 0)]
img = Image.new('RGB', (cols * 8, rows * 8), PAL[0])
px = img.load()
for r in range(rows):
    for c in range(cols):
        w = base + r * 32 + c
        lo = v[2 * w]
        hi = v[2 * w + 1]
        t = lo | ((hi & 1) << 8)
        vf = (hi >> 7) & 1
        hf = (hi >> 6) & 1
        off = char + t * 16
        if off + 16 > len(v):
            continue
        for y in range(8):
            b0 = v[off + y * 2]
            b1 = v[off + y * 2 + 1]
            for x in range(8):
                bit = 7 - x
                col = ((b0 >> bit) & 1) | (((b1 >> bit) & 1) << 1)
                yy = 7 - y if vf else y
                xx = 7 - x if hf else x
                px[c * 8 + xx, r * 8 + yy] = PAL[col]
img = img.resize((cols * 8 * 3, rows * 8 * 3), Image.NEAREST)
img.save(out)
print('wrote', out)
