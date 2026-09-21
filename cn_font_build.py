#!/usr/bin/env python3
"""Build a Chinese 16x16 (four 8x8 tiles) 2bpp bitmap font for the
SFC 初代熱血硬派くにおくん localization.

Target format (matches the game's existing font at ROM 0x0F8000):
  each 8x8 tile = 16 bytes, ROW-INTERLEAVED 2bpp:
      byte[base + y*2]     = plane0 bitmask for row y (bit7 = leftmost)
      byte[base + y*2 + 1] = plane1 bitmask for row y
  pixel value = ((plane0>>(7-x))&1) | (((plane1>>(7-x))&1)<<1)
One Chinese glyph = four 8x8 tiles (TL,TR,BL,BR) = 64 bytes.
Ink is written as pixel value 1, so plane0 carries the bits and plane1 = 0.

Usage:
    python cn_font_build.py probe     # legibility comparison sheet
    python cn_font_build.py build     # write the deliverable files
"""
import os
import sys
import math
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(HERE, 'dl', '_tmp')

FONTS = {
    'msyh':   'C:/Windows/Fonts/msyh.ttc',      # Microsoft YaHei, sans
    'simhei': 'C:/Windows/Fonts/simhei.ttf',    # SimHei, heavy sans
    'simsun': 'C:/Windows/Fonts/simsun.ttc',    # SimSun, serif
}

# ---------------------------------------------------------------- character set
GAME_VOCAB = (
    '开始继续结束暂停退出返回取消确定选择设置选项菜单标题画面音乐音效消息对话文字显示隐藏'
    '存档读档保存载入重新游戏玩家角色名字状态能力力量速度防御攻击生命体力魔法技能经验等级'
    '金钱道具装备武器防具药水物品敌人战斗胜利失败撤退逃跑移动等待调查使用得到失去获得购买'
    '出售商店旅店价格免费城镇村庄森林洞窟城堡王宫公主勇者剑盾铠甲头盔教堂祈祷复活死亡受伤'
    '治愈中毒火焰雷电冰冻光明黑暗时间白天夜晚早上中午晚上今天明天昨天现在这里那里什么为什么'
    '谁哪里怎么谢谢对不起你好再见请是不好坏大小多少快慢强弱新旧上下左右前后中间方向键盘按钮'
    '按下松开输入密码性别年龄出生血型身高体重喜欢讨厌朋友伙伴同伴老师学生父亲母亲哥哥姐姐'
    '弟弟妹妹男人女人孩子大人家人世界地球国家城市日本中国美国学校医院警察不良暴走番长打架'
    '拳头踢腿必杀连击组合气力怒气集中回避反击硬直倒地起身投掷抓取冲撞跳跃冲刺跑走站坐躺睡'
    '醒吃喝说话笑哭生气害怕高兴悲伤惊讶疑惑认真加油努力和平正义邪恶秘密真相谜事件故事冒险'
    '旅行出发到达回去前进后退左转右转直行停止危险安全注意警告禁止允许必须应该可以能够想要'
    '需要知道明白记得忘记找到丢失打开关闭进入出去回来过来上去下去起来坐下站立走路跑步跳飞'
    '游泳爬初代熱血硬派国男'
)
# extra kanji that a Japanese-source game text may keep verbatim
EXTRA_KANJI = '熱血硬派国男戦闘撃剣盾窟冒険旅敵癒毒'
BASE_HANZI = 1400          # standard 常用字 ranked by frequency
ASCII_RANGE = range(0x20, 0x7F)


def build_charset():
    """Return the ordered character list: hanzi (frequency order) then ASCII."""
    ts = {}
    for line in open(os.path.join(TMP, 'TSCharacters.txt'), encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        parts = line.rstrip('\n').split('\t')
        if len(parts) >= 2 and parts[1].split():
            ts[parts[0]] = parts[1].split()[0]

    freq = {}
    for line in open(os.path.join(TMP, 'essay.txt'), encoding='utf-8'):
        p = line.rstrip('\n').split('\t')
        if len(p) != 2 or len(p[0]) != 1:
            continue
        ch = p[0]
        if not ('\u4e00' <= ch <= '\u9fff'):
            continue
        try:
            c = int(p[1])
        except ValueError:
            continue
        s = ts.get(ch, ch)
        freq[s] = freq.get(s, 0) + c

    # standard 现代汉语常用字表 (3500) as the allowed common-character pool
    std = []
    seen = set()
    for ch in open(os.path.join(TMP, 'c3500.txt'), encoding='utf-8-sig').read():
        if '\u4e00' <= ch <= '\u9fff' and ch not in seen:
            seen.add(ch)
            std.append(ch)

    ranked = sorted(std, key=lambda c: (-freq.get(c, 0), c))
    hanzi = list(ranked[:BASE_HANZI])
    have = set(hanzi)
    extra = [c for c in GAME_VOCAB + EXTRA_KANJI if '\u4e00' <= c <= '\u9fff']
    for c in extra:
        if c not in have:
            have.add(c)
            hanzi.append(c)
    # re-sort the appended extras by frequency so the tail is still sensible
    tail = sorted(hanzi[BASE_HANZI:], key=lambda c: (-freq.get(c, 0), c))
    hanzi = hanzi[:BASE_HANZI] + tail

    chars = hanzi + [chr(c) for c in ASCII_RANGE]
    return chars


# ------------------------------------------------------------------- rendering
def rasterize(ch, n, fontpath, size, ss, thr):
    """Rasterise one character to an n x n 0/1 bitmap.

    ss = supersample factor (1 = draw directly at `size` px, >1 = draw at
    size*ss then LANCZOS-downsample to n x n).  The ink bounding box is
    centred in the n x n cell.
    """
    cell = n * ss
    img = Image.new('L', (cell, cell), 0)
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype(fontpath, size * ss)
    except Exception:
        f = ImageFont.load_default()
    bb = d.textbbox((0, 0), ch, font=f)
    w = bb[2] - bb[0]
    h = bb[3] - bb[1]
    x = (cell - w) // 2 - bb[0]
    y = (cell - h) // 2 - bb[1]
    d.text((x, y), ch, font=f, fill=255)
    if ss > 1:
        img = img.resize((n, n), Image.LANCZOS)
    px = img.load()
    return [[1 if px[x, y] > thr else 0 for x in range(n)] for y in range(n)]


def to_cell16(bm, n):
    """Place an n x n bitmap into a 16 x 16 cell, centred (offset (16-n)//2)."""
    off = (16 - n) // 2
    grid = [[0] * 16 for _ in range(16)]
    for y in range(n):
        for x in range(n):
            grid[off + y][off + x] = bm[y][x]
    return grid


def encode_tile2bpp(rows8):
    """8x8 0/1 rows -> 16 bytes row-interleaved 2bpp, ink = pixel value 1."""
    out = bytearray()
    for y in range(8):
        p0 = 0
        for x in range(8):
            if rows8[y][x]:
                p0 |= (0x80 >> x)
        out.append(p0)   # plane 0 = ink
        out.append(0x00)  # plane 1 = 0 -> pixel value 1
    return bytes(out)


def encode_glyph(grid16):
    """16x16 0/1 grid -> 64 bytes: tiles TL, TR, BL, BR."""
    data = bytearray()
    for ty in (0, 8):
        for tx in (0, 8):
            rows = [[grid16[ty + y][tx + x] for x in range(8)] for y in range(8)]
            data += encode_tile2bpp(rows)
    return bytes(data)


def decode_glyph(data64):
    """Independent decoder: 64 bytes -> 16x16 grid of 0/1 (pixel value != 0)."""
    assert len(data64) == 64, 'glyph must be 64 bytes'
    grid = [[0] * 16 for _ in range(16)]
    for ti, (ty, tx) in enumerate(((0, 0), (0, 8), (8, 0), (8, 8))):
        tile = data64[ti * 16:ti * 16 + 16]
        for y in range(8):
            p0 = tile[y * 2]
            p1 = tile[y * 2 + 1]
            for x in range(8):
                bit = 0x80 >> x
                val = (1 if p0 & bit else 0) | ((1 if p1 & bit else 0) << 1)
                grid[ty + y][tx + x] = 1 if val else 0
    return grid


# --------------------------------------------------------------- probe / build
def probe():
    test = '一国学说话热血硬派翻訳漢字確認困難戦闘攻撃生命魔法装備剣盾洞窟冒険旅敵癒毒'
    configs = []
    for n in (12, 14):
        for fname in ('msyh', 'simhei'):
            for method, ss, size in (('direct', 1, n), ('ss4', 4, n)):
                for thr in (80, 100, 128):
                    configs.append((n, fname, method, ss, size, thr))
    z = 3
    cw = 16 * z
    lw = 250
    W = lw + cw * len(test)
    rh = 16 * z + 6
    H = 30 + rh * len(configs)
    sheet = Image.new('RGB', (W, H), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    try:
        lf = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 12)
    except Exception:
        lf = ImageFont.load_default()
    d.text((6, 8), 'PROBE: rows = n / font / method / thr ; cols = test chars', fill=(0, 0, 0), font=lf)
    for ci, (n, fname, method, ss, size, thr) in enumerate(configs):
        y0 = 30 + ci * rh
        label = 'n=%d %s %s thr=%d' % (n, fname, method, thr)
        d.text((6, y0 + cw // 2 - 6), label, fill=(0, 0, 0), font=lf)
        for xi, ch in enumerate(test):
            bm = rasterize(ch, n, FONTS[fname], size, ss, thr)
            g = to_cell16(bm, n)
            x0 = lw + xi * cw
            for y in range(16):
                for x in range(16):
                    if g[y][x]:
                        d.rectangle([x0 + x * z, y0 + y * z, x0 + x * z + z - 1, y0 + y * z + z - 1],
                                    fill=(0, 0, 0))
            d.rectangle([x0, y0, x0 + cw - 1, y0 + cw - 1], outline=(210, 210, 210))
    out = os.path.join(HERE, 'cn_font_probe.png')
    sheet.save(out)
    print('wrote', out, sheet.size, 'rows', len(configs))


def build(n=12, fname='simhei', ss=4, thr=100, suffix='12x12'):
    chars = build_charset()
    fontpath = FONTS[fname]
    blobs = []
    grids = []
    for ch in chars:
        bm = rasterize(ch, n, fontpath, n, ss, thr)
        g = to_cell16(bm, n)
        grids.append(g)
        blobs.append(encode_glyph(g))
    blob = b''.join(blobs)

    binname = 'cn_font_%s.bin' % suffix
    with open(os.path.join(HERE, binname), 'wb') as fh:
        fh.write(blob)
    with open(os.path.join(HERE, 'cn_chars.txt'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(chars) + '\n')
    print('chars=%d  bytes=%d  (%d per glyph)' % (len(chars), len(blob), len(blob) // len(chars)))

    make_contact(grids, chars, os.path.join(HERE, 'cn_font_contact_%s.png' % suffix))
    if suffix == '12x12':
        make_contact(grids, chars, os.path.join(HERE, 'cn_font_contact.png'))
        make_preview(grids, chars, os.path.join(HERE, 'cn_font_12x12_preview.txt'), 40)
    return chars, blob, grids


def make_contact(grids, chars, path, per_row=32, z=4):
    rows = math.ceil(len(grids) / per_row)
    cw = 16 * z
    lw = 34
    W = lw + cw * per_row
    H = rows * cw
    img = Image.new('L', (W, H), 255)
    d = ImageDraw.Draw(img)
    try:
        lf = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 11)
    except Exception:
        lf = ImageFont.load_default()
    for i, g in enumerate(grids):
        r = i // per_row
        c = i % per_row
        x0 = lw + c * cw
        y0 = r * cw
        d.text((2, y0 + cw // 2 - 5), str(i), fill=0, font=lf)
        for y in range(16):
            for x in range(16):
                if g[y][x]:
                    d.rectangle([x0 + x * z, y0 + y * z, x0 + x * z + z - 1, y0 + y * z + z - 1], fill=0)
        d.rectangle([x0, y0, x0 + cw - 1, y0 + cw - 1], outline=200)
    img.save(path)
    print('wrote', path, img.size)


def make_preview(grids, chars, path, count=40):
    lines = []
    for i in range(min(count, len(grids))):
        g = grids[i]
        lines.append('--- glyph %d  U+%04X  %s' % (i, ord(chars[i]), chars[i]))
        for y in range(16):
            lines.append(''.join('#' if g[y][x] else '.' for x in range(16)))
        lines.append('')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')
    print('wrote', path)


def verify(binname, grids):
    """Re-read the .bin with an independent decoder and compare."""
    blob = open(os.path.join(HERE, binname), 'rb').read()
    n = len(blob) // 64
    bad = []
    for i in range(n):
        got = decode_glyph(blob[i * 64:(i + 1) * 64])
        if got != grids[i]:
            bad.append(i)
    print('verify %s: %d glyphs, %d mismatches %s' % (binname, n, len(bad), bad[:10]))
    return len(bad) == 0


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'probe'
    if mode == 'probe':
        probe()
    elif mode == 'build':
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 12
        fname = sys.argv[3] if len(sys.argv) > 3 else 'simhei'
        ss = int(sys.argv[4]) if len(sys.argv) > 4 else 4
        thr = int(sys.argv[5]) if len(sys.argv) > 5 else 100
        suffix = '%dx%d' % (n, n)
        chars, blob, grids = build(n, fname, ss, thr, suffix)
        verify('cn_font_%s.bin' % suffix, grids)
