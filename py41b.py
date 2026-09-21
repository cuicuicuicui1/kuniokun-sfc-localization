from PIL import Image
import cnglyph, sys
TAG = 'v41a'
POS = {'猪':(64,183),'肉':(80,183),'包':(96,183),'一':(112,183),'个':(128,183),
       '大':(112,185),'阪':(80,181),'啊':(81,185)}
f = sys.argv[1] if len(sys.argv)>1 else 'hw/%s_f01400.png'%TAG
img = Image.open(f).convert('RGB'); px = img.load()
for ch,(ox,oy) in POS.items():
    g = cnglyph.render16x16(ch)
    bad=[]
    for y in range(16):
        for x in range(16):
            want = 1 if g[y][x] else 0
            r,gg,b = px[ox+x,oy+y]
            got = 1 if (r+gg+b)>150 else 0
            if want!=got: bad.append((x,y,want,got,'%02X%02X%02X'%(r,gg,b)))
    print(ch, 'bad', len(bad), bad[:8])
