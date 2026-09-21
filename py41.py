"""py41: 16x16 pixel template match against BizHawk screenshots.

For every character asked for, build the 16x16 ink mask from the *builder's own*
renderer (cnglyph.render16x16) and slide it over the dialogue area of each PNG
produced by hw/v41.lua.  Reports the best position and the number of mismatching
pixels (0 = EXACT).  Pure pixel comparison, no eyeballing.
"""
import glob
import os
import sys

from PIL import Image

import cnglyph

TAG = os.getenv("HW_TAG", "v41")
BOX = (16, 174, 200, 214)          # x0, y0, x1, y1 search window (native pixels)
CHARS = os.getenv("HW_CHARS", "猪肉包一个大阪啊")

def mask_of(ch):
    g = cnglyph.render16x16(ch)
    rows = []
    for y in range(16):
        rows.append([1 if g[y][x] else 0 for x in range(16)])
    return rows

def screen_ink(px, x, y):
    r, g, b = px[x, y][:3]
    return 1 if (r + g + b) > 150 else 0

def best_match(img, mask, x0, x1, y0, y1):
    px = img.load()
    W, H = img.size
    x1 = min(x1, W - 16)
    y1 = min(y1, H - 16)
    best = None
    for oy in range(y0, y1 + 1):
        for ox in range(x0, x1 + 1):
            bad = 0
            for y in range(16):
                mr = mask[y]
                sy = oy + y
                for x in range(16):
                    if mr[x] != screen_ink(px, ox + x, sy):
                        bad += 1
                        if best is not None and bad >= best[0]:
                            break
                if best is not None and bad >= best[0]:
                    break
            if best is None or bad < best[0]:
                best = (bad, ox, oy)
                if bad == 0:
                    return best
    return best

def main():
    files = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "hw",
                                          "%s_f*.png" % TAG)))
    if not files:
        print("no screenshots for tag %s" % TAG)
        return 1
    masks = [(ch, mask_of(ch)) for ch in CHARS]
    for f in files:
        img = Image.open(f).convert("RGB")
        out = []
        for ch, m in masks:
            ink = sum(sum(r) for r in m)
            bad, ox, oy = best_match(img, m, BOX[0], BOX[2], BOX[1], BOX[3])
            out.append("%s:%s@(%d,%d)/%d" % (ch, "EXACT" if bad == 0 else "best%d" % bad, ox, oy, ink))
        print(os.path.basename(f), " ".join(out))
    return 0

if __name__ == "__main__":
    sys.exit(main())