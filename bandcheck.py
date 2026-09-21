"""Diff two screenshot sets taken with the same save and the same input.

Any row the patch disturbs shows up as a frame that differs from the original at
the same index, so this is a real detector for the coloured band (the previous
Lua one never worked: client.getpixel does not exist in this EmuHawk build).

    python bandcheck.py <tagA> <tagB> [band_y0 band_y1]
"""
import sys, os, glob, re
from PIL import Image

A, B = sys.argv[1], sys.argv[2]
Y0 = int(sys.argv[3]) if len(sys.argv) > 3 else 96
Y1 = int(sys.argv[4]) if len(sys.argv) > 4 else 174
HW = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'


def frames(tag):
    out = {}
    for p in glob.glob(HW + tag + '_f*'):
        m = re.search(r'_f(\d+)$', os.path.basename(p))
        if m:
            out[m.group(1)] = p
    return out


fa, fb = frames(A), frames(B)
common = sorted(set(fa) & set(fb))
print('%s: %d frames, %s: %d frames, common: %d' % (A, len(fa), B, len(fb), len(common)))
if not common:
    raise SystemExit('no common frames')

diffband = []
diffother = []
for name in common:
    ia = Image.open(fa[name]).convert('RGB')
    ib = Image.open(fb[name]).convert('RGB')
    pa, pb = ia.load(), ib.load()
    nb = no = 0
    rows = set()
    for y in range(ia.size[1]):
        for x in range(ia.size[0]):
            if pa[x, y] != pb[x, y]:
                if Y0 <= y <= Y1:
                    nb += 1
                    rows.add(y)
                else:
                    no += 1
    if nb:
        diffband.append((name, nb, sorted(rows)[:6]))
    if no:
        diffother.append((name, no))

print('frames differing in the band rows %d..%d : %d' % (Y0, Y1, len(diffband)))
for n, c, r in diffband[:12]:
    print('   %s  %d px  rows %s' % (n, c, r))
print('frames differing outside the band     : %d' % len(diffother))
for n, c in diffother[:12]:
    print('   %s  %d px' % (n, c))
