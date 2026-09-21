"""Render tiles lo..hi from a font base as a labelled PNG grid."""
import sys
from PIL import Image, ImageDraw

rom = open(sys.argv[1], 'rb').read()
base = int(sys.argv[2], 0)
lo = int(sys.argv[3], 0)
hi = int(sys.argv[4], 0)
out = sys.argv[5]
cols = int(sys.argv[6]) if len(sys.argv) > 6 else 8
S = 4
cw, ch = 8 * S, 8 * S + 14
rows = (hi - lo + cols) // cols
img = Image.new('RGB', (cols * cw, rows * ch), (255, 255, 255))
d = ImageDraw.Draw(img)
PAL = [(255, 255, 255), (170, 170, 170), (85, 85, 85), (0, 0, 0)]
for i, t in enumerate(range(lo, hi + 1)):
    off = base + t * 16
    if off + 16 > len(rom):
        continue
    cx = (i % cols) * cw
    cy = (i // cols) * ch
    for y in range(8):
        b0 = rom[off + y * 2]
        b1 = rom[off + y * 2 + 1]
        for x in range(8):
            bit = 7 - x
            c = ((b0 >> bit) & 1) | (((b1 >> bit) & 1) << 1)
            d.rectangle([cx + x * S, cy + y * S, cx + x * S + S - 1, cy + y * S + S - 1],
                        fill=PAL[c])
    d.text((cx + 2, cy + 8 * S + 1), '%02X' % t, fill=(0, 0, 200))
    d.rectangle([cx, cy, cx + cw - 1, cy + ch - 1], outline=(255, 0, 0))
img.save(out)
print('wrote', out, img.size)
