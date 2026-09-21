"""Render known dialogue lines through each candidate pipeline and upscale them
the way the user's snes9x window does (2.634x bilinear), so legibility can be
judged on text we already know the ground truth of."""
import os
import sys

from PIL import Image

BASE = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon'
sys.path.insert(0, BASE)
import fontcmp as F                                    # noqa: E402

OUT = os.path.join(BASE, 'fontcmp')
INK = (115, 123, 255)          # CGRAM idx1 = $73DF (near-white with blue tint)
BG = (0, 0, 0)

# ground-truth lines (from cn_translation.json / the user's screenshot)
LINES = {
    'user_line': '大阪啊大阪啊',
    'dense': '鐵拳制裁警護讓鬱襲擊櫻宮闇',
    'normal': '我是一個人，要買豬肉包一個！',
    'menu': '道具　武器　防具　記錄　離開',
}


def cell_canvas(text, gfn, col0=0, row0=0):
    im = Image.new('RGB', (256, 224), BG)
    px = im.load()
    for i, ch in enumerate(text):
        x0 = 24 + (col0 + i) * 8
        y0 = 183 + row0 * 16
        g = gfn(ch)
        if g is None:
            continue
        for y in range(16):
            for x in range(8):
                if g[y][x]:
                    xx, yy = x0 + x, y0 + y
                    if 0 <= xx < 256 and 0 <= yy < 224:
                        px[xx, yy] = INK
    return im


def main():
    pipelines = [(n, f) for n, f in F.PIPES if n.split()[0] in
                 ('cur', 'soft16', 'soft_box12', 'uni16', 'ark11')]
    for lname, text in LINES.items():
        tiles = []
        for pname, fn in pipelines:
            native = cell_canvas(text, fn)
            w = 256
            h = 224
            # crop around the text line for the sheet
            y0, y1 = 179, 201
            crop = native.crop((20, y0, 24 + 8 * min(len(text), 27) + 8, y1))
            s = 3
            tiles.append((pname, crop.resize((crop.width * s, crop.height * s), Image.NEAREST)))
        W = max(t[1].width for t in tiles) + 40
        H = sum(t[1].height + 6 for t in tiles)
        sheet = Image.new('RGB', (W, H), (20, 20, 20))
        from PIL import ImageDraw
        d = ImageDraw.Draw(sheet)
        y = 0
        for pname, im in tiles:
            sheet.paste(im, (0, y))
            d.text((im.width + 6, y + im.height // 2), pname, fill=(200, 200, 200))
            y += im.height + 6
        sheet.save(os.path.join(OUT, 'sheet_%s_x3.png' % lname))
        # and the simulated snes9x window (2.634x bilinear)
        rows = []
        for pname, fn in pipelines:
            native = cell_canvas(text, fn)
            rows.append((pname, native.resize((int(256 * 2.634), int(224 * 2.634)), Image.BILINEAR)))
        W = max(r[1].width for r in rows)
        H = sum(r[1].height for r in rows)
        sim = Image.new('RGB', (W, H), (0, 0, 0))
        y = 0
        for pname, im in rows:
            sim.paste(im, (0, y))
            y += im.height
        sim.save(os.path.join(OUT, 'sim_%s.png' % lname))
        print('wrote', lname, sheet.size, sim.size)


if __name__ == '__main__':
    main()