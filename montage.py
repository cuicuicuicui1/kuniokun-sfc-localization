"""montage.py - stitch a run's screenshots into one grid image so a single Read shows the whole sequence."""
import glob
import os
import re
import sys
from PIL import Image

HW = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw'

tag = sys.argv[1]
scale = float(sys.argv[2]) if len(sys.argv) > 2 else 0.45
files = sorted(glob.glob(HW + '/' + tag + '_f*.png'), key=lambda p: int(re.search(r'_f(\d+)', p).group(1)))
if not files:
    print('no frames for', tag)
    raise SystemExit
ims = []
for f in files:
    im = Image.open(f).convert('RGB')
    im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    ims.append((os.path.basename(f), im))
w, h = ims[0][1].size
cols = 4
rows = (len(ims) + cols - 1) // cols
sheet = Image.new('RGB', (w * cols + (cols + 1) * 4, h * rows + (rows + 1) * 4), (30, 30, 30))
for i, (name, im) in enumerate(ims):
    c, r = i % cols, i // cols
    sheet.paste(im, (4 + c * (w + 4), 4 + r * (h + 4)))
out = HW + '/montage_' + tag + '.png'
sheet.save(out)
print(out, sheet.size, len(ims), 'frames:', ', '.join(n.split('_')[-1].replace('.png', '') for n, _ in ims))