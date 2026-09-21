"""cropsheet.py - crop the dialog-box area from several screenshots and stack them at high zoom.

usage: python cropsheet.py out.png scale x y w h file1 file2 ...
"""
import sys
from PIL import Image, ImageDraw

out, scale = sys.argv[1], float(sys.argv[2])
x, y, w, h = (int(v) for v in sys.argv[3:7])
files = sys.argv[7:]
tiles = []
for f in files:
    im = Image.open(f).convert('RGB').crop((x, y, x + w, y + h))
    im = im.resize((int(w * scale), int(h * scale)), Image.NEAREST)
    tiles.append((f.split('/')[-1], im))
tw, th = tiles[0][1].size
sheet = Image.new('RGB', (tw + 8, (th + 18) * len(tiles) + 8), (40, 40, 40))
d = ImageDraw.Draw(sheet)
for i, (name, im) in enumerate(tiles):
    yy = 4 + i * (th + 18)
    d.text((4, yy), name, fill=(255, 255, 0))
    sheet.paste(im, (4, yy + 14))
sheet.save(out)
print(out, sheet.size, [n for n, _ in tiles])