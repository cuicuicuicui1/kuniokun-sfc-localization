from PIL import Image
import cnglyph
rom = open('kuniokun_cn.smc','rb').read()
v = open('hw/v42a_vram.bin','rb').read()
def vram_tile(t):
    o = (0xC000 + t*16) - 0xC000
    return v[o:o+16]
def pool(page, slot):
    o = (0x21+page)*0x8000 + slot*64
    return rom[o:o+64]
def rows_of(tilebytes):   # row-interleaved 2bpp: row y = bytes [y*2] (plane0), [y*2+1] (plane1)
    out = []
    for y in range(8):
        p0, p1 = tilebytes[y*2], tilebytes[y*2+1]
        out.append([((p1 >> (7-x)) & 1)*2 + ((p0 >> (7-x)) & 1) for x in range(8)])
    return out
img = Image.open('hw/v41a_f01400.png').convert('RGB'); px = img.load()
def screen_rows(ox, oy):  # 8x8 ink block from screenshot
    return [[1 if sum(px[ox+x, oy+y]) > 150 else 0 for x in range(8)] for y in range(8)]
for ch, page, slot, sx, sy in (('猪',11,42,64,183), ('肉',14,38,80,183), ('子',None,None,0,0)):
    if page is None: continue
    p = pool(page, slot)
    lt = 2*rom[0x1F0180+slot]; rt = 2*rom[0x1F0180+53+slot]
    print('=== %s slot %d tiles %02X/%02X/%02X/%02X' % (ch, slot, lt, lt+1, rt, rt+1))
    for name, tb in (('TL', vram_tile(lt)), ('BL', vram_tile(lt+1)), ('TR', vram_tile(rt)), ('BR', vram_tile(rt+1))):
        print('  VRAM %s == pool part: %s' % (name, tb == (p[0:16] if name=='TL' else p[16:32] if name=='BL' else p[32:48] if name=='TR' else p[48:64])))
    # compare VRAM TL rows against the screenshot's top-left 8x8 block
    tl = rows_of(vram_tile(lt)); bl = rows_of(vram_tile(lt+1))
    tr = rows_of(vram_tile(rt)); br = rows_of(vram_tile(rt+1))
    scr = [screen_rows(sx, sy) + screen_rows(sx, sy+8), screen_rows(sx+8, sy) + screen_rows(sx+8, sy+8)]
    # scr[0] = left half rows 0..15, scr[1] = right half
    vram_all = [tl + bl, tr + br]
    for half, pos in ((0,'L'), (1,'R')):
        diffs = [(x,y) for y in range(16) for x in range(8) if (1 if vram_all[half][y][x] else 0) != scr[half][y][x]]
        print('  %s half: vram vs screen diffs = %d %s' % (pos, len(diffs), diffs[:6]))
