"""Count saturated pixels per row in the scene band of every screenshot.

The coloured band is a horizontal strip of label-glyph fragments - saturated
red/white/green/blue bars - drawn over flat pavement, in the rows just above the
dialogue box.  Pavement is desaturated blue-grey, so counting high saturation
pixels per row finds the band without depending on frame timing (the two runs
are a frame or two apart in their palette fade, so raw diffs are noisy).

    python bandscan.py <tag> [y0 y1] [thresh]
"""
import sys, glob, os, re, collections
from PIL import Image

HW = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
tag = sys.argv[1]
Y0 = int(sys.argv[2]) if len(sys.argv) > 2 else 88
Y1 = int(sys.argv[3]) if len(sys.argv) > 3 else 180
TH = int(sys.argv[4]) if len(sys.argv) > 4 else 90

rows = collections.Counter()
worst = []
for p in sorted(glob.glob(HW + tag + '_f*')):
    m = re.search(r'_f(\d+)$', os.path.basename(p))
    if not m:
        continue
    n = m.group(1)
    im = Image.open(p).convert('RGB')
    px = im.load()
    for y in range(Y0, Y1 + 1):
        c = 0
        for x in range(im.size[0]):
            r, g, b = px[x, y]
            if max(r, g, b) - min(r, g, b) > TH:
                c += 1
        if c:
            rows[y] += 1
            if c >= 60:
                worst.append((n, y, c))
print('%s: frames scanned' % tag)
print('rows with any saturated pixels (count = frames):')
for y in sorted(rows):
    print('   y=%3d  %d frames' % (y, rows[y]))
print('rows with >=60 saturated pixels: %d occurrences' % len(worst))
for n, y, c in worst[:20]:
    print('   frame %s  y=%d  %d px' % (n, y, c))
