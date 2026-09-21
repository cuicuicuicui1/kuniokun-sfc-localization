from PIL import Image
import cnglyph
img = Image.open('hw/v41a_f01400.png').convert('RGB'); px = img.load()
def dump(ch, ox, oy):
    g = cnglyph.render16x16(ch)
    print('=== %s at (%d,%d)   mask | screen' % (ch, ox, oy))
    for y in range(16):
        m = ''.join('#' if g[y][x] else '.' for x in range(16))
        s = ''
        for x in range(16):
            r,gg,b = px[ox+x, oy+y]
            t = r+gg+b
            s += '#' if t>150 else ('+' if t>40 else '.')
        d = ''.join('X' if (m[x]=='#') != (s[x]=='#') else ' ' for x in range(16))
        print('%2d %s | %s | %s' % (y, m, s, d))
for ch, ox, oy in (('猪',64,183),('肉',80,183),('一',112,183)):
    dump(ch, ox, oy)
