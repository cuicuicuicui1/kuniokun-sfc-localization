"""8x16 Chinese glyph renderer for the kuniokun project.

Each glyph = 2 SNES tiles (upper 8x8, lower 8x8) = 32 bytes, packed with the
same row-interleaved 2bpp format the game's own font uses.
"""
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sfc_tools import pack_8x8

FONTS = ['C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simsun.ttc',
         'C:/Windows/Fonts/simhei.ttf']

SAMPLE = (
    '學生暴力聯盟力量請我們幫助抱歉昨天襲擊櫻宮制服相似飯店大阪帶路決鬥輸謝謝'
    '你好嗎沒有什麼事情現在知道這個地方去哪裡時候日本東京學校老師朋友同學'
    '戰鬥打倒敵人勝利失敗攻擊防禦武器裝備道具使用得到金錢買賣商店價格'
    '前後左右上下東西南北中第一二三四五六七八九十百千萬年月日時分秒'
    '大中小高低長短快慢強弱新舊多少遠近難易有無來去出入開始結束'
    '心手眼耳口鼻頭身體血氣男女子父母兄弟姊妹家族'
    '火水木金土空天地山海川森林石鐵風雨雪雲雷電'
    '話言詞語文字本語讀寫聽説問答説明介紹名字'
    '走跑跳站坐睡醒吃喝看見聽到感覺想法意見'
    '必勝負責任任務完成準備出發到達返回繼續'
)


def render8x16(ch, fontpath, px=16, thresh=128, widen=1.0):
    f = ImageFont.truetype(fontpath, px)
    S = px * 3
    img = Image.new('L', (S, S), 0)
    dr = ImageDraw.Draw(img)
    dr.text((S / 2, S / 2), ch, fill=255, font=f, anchor='mm')
    bb = img.getbbox()
    if bb is None:
        return [[0] * 8 for _ in range(16)]
    ink = img.crop(bb)
    iw, ih = ink.size
    # fill the 8x16 box (CJK bitmap cells are slightly condensed; fill is standard)
    tw = max(1, min(8, int(round(iw * widen))))
    ink = ink.resize((max(1, min(8, tw)), min(16, ih)), Image.LANCZOS)
    iw, ih = ink.size
    g = [[0] * 8 for _ in range(16)]
    ox = (8 - iw) // 2
    oy = (16 - ih) // 2
    p = ink.load()
    for y in range(ih):
        for x in range(iw):
            if p[x, y] > thresh:
                g[oy + y][ox + x] = 1
    return g


def pack8x16(g):
    """upper 8x8 then lower 8x8, each row-interleaved 2bpp (16 bytes each)."""
    return pack_8x8(g[:8]) + pack_8x8(g[8:])


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else 'cn816'
    px = int(sys.argv[2]) if len(sys.argv) > 2 else 16
    thresh = int(sys.argv[3]) if len(sys.argv) > 3 else 128
    chars = sorted(set(SAMPLE))
    fp = next(p for p in FONTS if __import__('os').path.exists(p))
    print('font:', fp, 'px:', px, 'thresh:', thresh, 'chars:', len(chars))

    data = bytearray()
    grids = {}
    for ch in chars:
        g = render8x16(ch, fp, px, thresh)
        grids[ch] = g
        data += pack8x16(g)
    open(out + '.bin', 'wb').write(bytes(data))
    print('%s.bin %d bytes (%d glyphs x 32 B)' % (out, len(data), len(chars)))

    per_row = 32
    S = 4
    n = len(chars)
    rows = (n + per_row - 1) // per_row
    im = Image.new('L', (per_row * 8 * S, rows * 16 * S), 255)
    for i, ch in enumerate(chars):
        cx = (i % per_row) * 8 * S
        cy = (i // per_row) * 16 * S
        for y in range(16):
            for x in range(8):
                if grids[ch][y][x]:
                    for dy in range(S):
                        for dx in range(S):
                            im.putpixel((cx + x * S + dx, cy + y * S + dy), 0)
    im.save(out + '_sheet.png')
    print('wrote', out + '_sheet.png')

    for ch in chars[:3]:
        print('---', ch)
        for r in grids[ch]:
            print('   ' + ''.join('#' if v else '.' for v in r))


if __name__ == '__main__':
    main()