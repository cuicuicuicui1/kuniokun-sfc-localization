from PIL import Image
rom = open('kuniokun_cn.smc','rb').read()
orig = open('dl/roms/kuniokun__SF8127.smc','rb').read()
v = open('hw/v42a_vram.bin','rb').read()
img = Image.open('hw/v41a_f01400.png').convert('RGB'); px = img.load()
def vt(t):
    o = t*16
    return v[o:o+16]
def rows8(tb):
    return [[((tb[y*2+1]>>(7-x))&1)*2+((tb[y*2]>>(7-x))&1) for x in range(8)] for y in range(8)]
def ink(rows, y): return sum(1 for c in rows[y] if c)
def screen_ink(x, y): return 1 if sum(px[x,y])>150 else 0
left  = [rom[0x1F0180+s] for s in range(53)]
right = [rom[0x1F0180+53+s] for s in range(53)]
slot = 42   # 猪
tl, bl = rows8(vt(2*left[slot])), rows8(vt(2*left[slot]+1))
tr, br = rows8(vt(2*right[slot])), rows8(vt(2*right[slot]+1))
grid = [[(1 if tl[y][x] else 0) for x in range(8)] + [(1 if tr[y][x] else 0) for x in range(8)] for y in range(8)] + \
       [[(1 if bl[y][x] else 0) for x in range(8)] + [(1 if br[y][x] else 0) for x in range(8)] for y in range(8)]
best = None
for oy in range(176, 196):
    for ox in range(56, 72):
        bad = sum(1 for y in range(16) for x in range(16) if grid[y][x] != screen_ink(ox+x, oy+y))
        if best is None or bad < best[0]: best = (bad, ox, oy)
print('猪 16x16 best', best)
# the VRAM tile row 0 with the ink row per tile (to spot systematic clipping)
print('猪 TL ink/row', [ink(tl,y) for y in range(8)], ' BL', [ink(bl,y) for y in range(8)])
print('猪 TR ink/row', [ink(tr,y) for y in range(8)], ' BR', [ink(br,y) for y in range(8)])
# name glyph: tile 0x98 (FA of code 0x47) as an 8x8 block, brute-force its screen position
t98 = rows8(vt(0x98))
bestn = None
for oy in range(178, 196):
    for ox in range(20, 44):
        bad = sum(1 for y in range(8) for x in range(8) if (1 if t98[y][x] else 0) != screen_ink(ox+x, oy+y))
        if bestn is None or bad < bestn[0]: bestn = (bad, ox, oy)
print('name tile 0x98 best', bestn)
print('name tile 0x98 ink/row', [ink(t98,y) for y in range(8)])
# and the second name char (tile 0x77?)
t77 = rows8(vt(0x77))
bestn2 = None
for oy in range(178, 196):
    for ox in range(20, 48):
        bad = sum(1 for y in range(8) for x in range(8) if (1 if t77[y][x] else 0) != screen_ink(ox+x, oy+y))
        if bestn2 is None or bad < bestn2[0]: bestn2 = (bad, ox, oy)
print('name tile 0x77 best', bestn2, 'ink/row', [ink(t77,y) for y in range(8)])
