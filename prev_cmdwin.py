from PIL import Image
import numpy as np
import cnglyph

LABELS = [(0, 1, '使用气力'), (0, 12, '使用道具'), (1, 1, '装备'),
          (1, 10, '状态'), (1, 21, '扔掉')]
ROWS, COLS = 2, 26
CW, CH = 8, 16

def draw8(scale=4):
    img = np.zeros((ROWS*CH, COLS*CW), dtype=np.uint8)
    for r, c, txt in LABELS:
        p = c
        for ch in txt:
            g = cnglyph.render16(ch)
            for y in range(16):
                for x in range(8):
                    if g[y][x]:
                        img[r*CH+y, p*CW+x] = 1
            p += 1
    return Image.fromarray(img*255).resize((COLS*CW*scale, ROWS*CH*scale), Image.NEAREST)

def draw16(scale=4):
    W, H = COLS*8, ROWS*16*2
    img = np.zeros((H, W), dtype=np.uint8)
    for r, c, txt in LABELS:
        p = c
        for ch in txt:
            g = cnglyph.render16x16(ch)
            for y in range(16):
                for x in range(16):
                    if g[y][x]:
                        img[r*32+y, p*8+x] = 1
            p += 2
    return Image.fromarray(img*255).resize((W*scale, H*scale), Image.NEAREST)

a, b = draw8(), draw16()
w = max(a.size[0], b.size[0])
s = Image.new('L', (w, a.size[1]+b.size[1]+20), 40)
s.paste(a, (0, 0)); s.paste(b, (0, a.size[1]+20))
s.save('hw/cmdwin_preview.png')
print('8x16', a.size, '16x16', b.size)
