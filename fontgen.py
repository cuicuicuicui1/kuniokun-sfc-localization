"""Chinese bitmap font generator for the kuniokun SFC project.

Renders a character set with a system CJK font into SNES 2bpp tiles.

Layouts supported:
  '16x16' : 16x16 glyph in a 4-tile block  -> 2 character cells wide (TL,TR,BL,BR)
  '8x16'  : 8x12 glyph in the top of an 8x16 cell -> 1 character cell (2 tiles)
  '12x12' : 12x12 glyph inside the 16x16 block

Usage:  python fontgen.py <outprefix> <layout> [size]
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sfc_tools import pack_16x16, pack_8x8

FONTS = [
    ('msyh',   'C:/Windows/Fonts/msyh.ttc'),
    ('simsun', 'C:/Windows/Fonts/simsun.ttc'),
    ('simhei', 'C:/Windows/Fonts/simhei.ttf'),
    ('msjh',   'C:/Windows/Fonts/msjh.ttc'),
]

SAMPLE = (
    '學生暴力聯盟力量請我們幫助抱歉昨天襲擊櫻宮制服相似飯店大阪帶路決鬥輸謝謝'
    '你好嗎沒有什麼事情現在知道這個地方去哪裡時候日本東京學校老師朋友同學'
    '戰鬥打倒敵人勝利失敗攻擊防禦武器裝備道具使用得到金錢買賣商店價格'
    '前後左右上下東西南北中第一二三四五六七八九十百千萬年月日時分秒'
    '大中小高低長短快慢強弱新舊多少遠近難易有無來去出入開始結束'
    '心手眼耳口鼻頭身體血氣男女子父母兄弟姊妹家族'
    '火水木金土空天地山海川森林石鉄風雨雪雲雷電'
    '話言詞語文字本語讀寫聽説問答説明介紹名字'
    '走跑跳站坐睡醒吃喝看見聽到感覺想法意見'
    '必勝負責任任務完成準備出發到達返回繼續'
)


def render_glyph(ch, fontpath, px, bw, bh, thresh=110):
    """Return a bh x bw list of 0/1 with the glyph centred."""
    f = ImageFont.truetype(fontpath, px)
    pad = px * 2
    img = Image.new('L', (px * 3, px * 3), 0)
    dr = ImageDraw.Draw(img)
    try:
        dr.text((px * 1.5, px * 1.5), ch, fill=255, font=f, anchor='mm')
    except Exception:
        dr.text((px, px), ch, fill=255, font=f)
    # find ink bbox
    bb = img.getbbox()
    if bb is None:
        return [[0] * bw for _ in range(bh)]
    ink = img.crop(bb)
    iw, ih = ink.size
    if iw > bw or ih > bh:
        ink = ink.resize((min(iw, bw), min(ih, bh)), Image.LANCZOS)
        iw, ih = ink.size
    out = [[0] * bw for _ in range(bh)]
    ox = (bw - iw) // 2
    oy = (bh - ih) // 2
    p = ink.load()
    for y in range(ih):
        for x in range(iw):
            if p[x, y] > thresh:
                out[oy + y][ox + x] = 1
    return out


def to_16x16(g):
    """Centre an 8..16px glyph inside a 16x16 grid."""
    gh = len(g)
    gw = len(g[0])
    grid = [[0] * 16 for _ in range(16)]
    oy = (16 - gh) // 2
    ox = (16 - gw) // 2
    for y in range(gh):
        for x in range(gw):
            grid[oy + y][ox + x] = g[y][x]
    return grid


def to_8x16(g):
    """Place an 8..12 tall / <=8 wide glyph in the top of an 8x16 cell."""
    gh = len(g)
    gw = len(g[0])
    grid = [[0] * 8 for _ in range(16)]
    oy = max(0, (16 - gh) // 2)
    ox = max(0, (8 - gw) // 2)
    for y in range(min(gh, 16)):
        for x in range(min(gw, 8)):
            grid[oy + y][ox + x] = g[y][x]
    return grid


def contact_sheet(chars, path, bw=8, scale=4, per_row=24):
    n = len(chars)
    rows = (n + per_row - 1) // per_row
    im = Image.new('L', (per_row * bw * scale, rows * 16 * scale), 255)
    return im


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else 'cnfont'
    layout = sys.argv[2] if len(sys.argv) > 2 else '16x16'
    px = int(sys.argv[3]) if len(sys.argv) > 3 else {'16x16': 16, '12x12': 12, '8x16': 12}[layout]

    fontpath = None
    for name, p in FONTS:
        if os.path.exists(p):
            fontpath = p
            print('using font', name, p)
            break
    if not fontpath:
        raise SystemExit('no CJK font found')

    chars = sorted(set(SAMPLE))
    print('chars:', len(chars))

    if layout == '16x16':
        bw, bh = 16, 16
        packer = lambda g: pack_16x16(to_16x16(g))
        tiles_per = 4
    elif layout == '12x12':
        bw, bh = 12, 12
        packer = lambda g: pack_16x16(to_16x16(g))
        tiles_per = 4
    elif layout == '8x16':
        bw, bh = 8, 12
        packer = lambda g: (pack_8x8(to_8x16(g)[:8]) + pack_8x8(to_8x16(g)[8:]))
        tiles_per = 2
    else:
        raise SystemExit('unknown layout')

    data = bytearray()
    grids = {}
    for ch in chars:
        g = render_glyph(ch, fontpath, px, bw, bh)
        grids[ch] = g
        data += packer(g)
    open(out + '.bin', 'wb').write(bytes(data))
    open(out + '_chars.txt', 'w', encoding='utf-8').write(''.join(chars))
    print('%s.bin = %d bytes, %d glyphs x %d tiles' % (out, len(data), len(chars), tiles_per))

    # contact sheet: 2 rows per glyph block, 24 per row
    per_row = 24
    n = len(chars)
    rows = (n + per_row - 1) // per_row
    S = 5
    im = Image.new('L', (per_row * bw * S, rows * bh * S), 255)
    for i, ch in enumerate(chars):
        cx = (i % per_row) * bw * S
        cy = (i // per_row) * bh * S
        for y in range(bh):
            for x in range(bw):
                if grids[ch][y][x]:
                    for dy in range(S):
                        for dx in range(S):
                            im.putpixel((cx + x * S + dx, cy + y * S + dy), 0)
    im.save(out + '_sheet.png')
    print('wrote', out + '_sheet.png')

    for ch in chars[:8]:
        print('---', ch)
        for r in grids[ch]:
            print('   ' + ''.join('#' if v else '.' for v in r))


if __name__ == '__main__':
    main()