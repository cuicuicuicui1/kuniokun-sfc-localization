#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shape-match game font tiles against real Japanese glyphs.

Tight-crop render (glyph fills 8x8) works well for the chunky game font.
Candidate set is restricted per block to avoid punctuation false positives.
Validated on the known katakana block 0xA1-0xCC.
"""
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROM = 'dl/roms/kuniokun__SF8127.smc'
OFF = 0x0F8000
fontdata = open(ROM, 'rb').read()[OFF:OFF + 4096]

def tile_mask(idx):
    tb = fontdata[idx*16:(idx+1)*16]
    m = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        p0 = tb[y*2]; p1 = tb[y*2+1]
        for x in range(8):
            v = ((p0 >> (7-x)) & 1) | (((p1 >> (7-x)) & 1) << 1)
            m[y, x] = 1 if v else 0
    return m

FONTS = ['C:/Windows/Fonts/msgothic.ttc',
         'C:/Windows/Fonts/YuGothB.ttc']

def render_mask(ch, fpath, size=120):
    try:
        f = ImageFont.truetype(fpath, size)
    except Exception:
        return None
    img = Image.new('L', (size*3, size*3), 0)
    d = ImageDraw.Draw(img)
    d.text((size, size), ch, font=f, fill=255)
    bb = img.getbbox()
    if not bb:
        return None
    crop = img.crop(bb)
    small = crop.resize((8, 8), Image.BOX)
    a = np.asarray(small, dtype=np.float32)
    return (a > 90).astype(np.uint8)

def best_iou(m, cand, shifts=1):
    best = 0.0
    for dy in range(-shifts, shifts+1):
        for dx in range(-shifts, shifts+1):
            c = np.roll(np.roll(cand, dy, 0), dx, 1)
            inter = np.logical_and(m, c).sum()
            uni = np.logical_or(m, c).sum()
            if uni:
                best = max(best, inter/uni)
    return best

HIRA_FULL = list('あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん')
HIRA_DAKU = list('がぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽ')
KATA_FULL = list('アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン')
KATA_DAKU = list('ガギグゲゴザジズゼゾダヂヅデドバビブベボパピプペポ')
SMALL = list('ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮ')

def cands(arg):
    if arg == 'katakana':
        return KATA_FULL + KATA_DAKU + ['ー', 'ヰ', 'ヱ']
    if arg == 'hira':
        return HIRA_FULL + HIRA_DAKU + SMALL
    if arg == 'small':
        return SMALL
    return HIRA_FULL + KATA_FULL + SMALL

def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else 'katakana'
    if arg == 'katakana':
        rng = range(0xA0, 0xE0)
    elif arg == 'hira':
        rng = range(0x60, 0xA0)
    else:
        rng = range(0x00, 0x100)
    CAND = cands(arg)
    # precompute candidate masks
    cmask = {}
    for ch in CAND:
        for f in FONTS:
            cm = render_mask(ch, f)
            if cm is None:
                continue
            s = cm.sum()
            if s > cmask.get(ch, (None, -1))[1]:
                cmask[ch] = (cm, s)
    for idx in rng:
        m = tile_mask(idx)
        if m.sum() == 0:
            print('0x%02X  BLANK' % idx)
            continue
        scores = [(ch, best_iou(m, cm)) for ch, (cm, _) in cmask.items()]
        scores.sort(key=lambda kv: -kv[1])
        print('0x%02X  ' % idx + '  '.join('%s:%.2f' % (c, s) for c, s in scores[:5]))

if __name__ == '__main__':
    main()
