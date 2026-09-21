#!/usr/bin/env python3
"""Proof of concept: rasterise Chinese glyphs into real SNES 2bpp tile data
and render them the way the game's VBlank uploader would show them.

Uses Hero Senki's confirmed 8x8 2bpp font at ROM 0x01A000 as the reference.
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROM = r"F:\BaiduNetdiskDownload\SFC\Hero Senki - Project Olympus (Japan) 优先级高\Hero Senki - Project Olympus (Japan).sfc"
FONTOFF = 0x01C9A0   # Hero Senki 8x8 2bpp font block, 0x01C9A0-0x01D7A0 (224 tiles)
FONT_TILES = 256

CJK = ["英雄戦記", "日本語", "中文漢字", "翻訳可能", "亜唖娃阿哀愛挨"]

def find_cjk_font(px):
    for p in (r"C:\Windows\Fonts\simsun.ttc", r"C:\Windows\Fonts\msyh.ttc",
              r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\msgothic.ttc"):
        if os.path.exists(p):
            try: return ImageFont.truetype(p, px)
            except Exception: pass
    return ImageFont.load_default()

def bitmap(text, px, cell=None):
    """Rasterise text to a dict char -> 2D list of 0/1 at the given pixel size."""
    cell = cell or px
    f = find_cjk_font(px)
    out = {}
    for ch in text:
        img = Image.new('L', (cell, cell), 0)
        d = ImageDraw.Draw(img)
        bb = d.textbbox((0, 0), ch, font=f)
        w = bb[2] - bb[0]; h = bb[3] - bb[1]
        d.text(((cell - w) // 2 - bb[0], (cell - h) // 2 - bb[1]), ch, font=f, fill=255)
        px_ = img.load()
        out[ch] = [[1 if px_[x, y] > 128 else 0 for x in range(cell)] for y in range(cell)]
    return out

def encode_tile2bpp(rows):
    """8x8 0/1 rows -> 16 bytes SNES 2bpp planar (plane0/plane1 interleaved per row).
    Ink is value 3 so plane0 == plane1, matching the game's existing font."""
    b = bytearray()
    for r in rows:
        v = 0
        for x in range(8):
            if r[x]: v |= (0x80 >> x)
        b.append(v & 0xFF)   # plane 0
        b.append(v & 0xFF)   # plane 1  -> pixel value 3
    return bytes(b)

def glyph_to_tiles(bm):
    """cell x cell bitmap -> list of 8x8 tiles in reading order (row-major across the cell)."""
    n = len(bm) // 8
    tiles = []
    for ty in range(n):
        for tx in range(n):
            rows = [[bm[ty*8 + y][tx*8 + x] for x in range(8)] for y in range(8)]
            tiles.append(encode_tile2bpp(rows))
    return tiles

def render_row(tilebytes, ntiles, scale, path):
    """Render raw SNES 2bpp tile bytes to a PNG (0->white, 3->black)."""
    img = Image.new('L', (8 * ntiles * scale, 8 * scale), 255)
    px = img.load()
    for t in range(ntiles):
        data = tilebytes[t*16:(t+1)*16]
        for y in range(8):
            p0 = data[y*2]; p1 = data[y*2 + 1]
            for x in range(8):
                bit = 0x80 >> x
                v = (1 if p0 & bit else 0) | (2 if p1 & bit else 0)
                g = [255, 170, 85, 0][v]
                for sy in range(scale):
                    for sx in range(scale):
                        px[(t*8 + x)*scale + sx, y*scale + sy] = g
    img.save(path)
    return path

def main():
    body = open(ROM, 'rb').read()
    print('== Hero Senki 8x8 2bpp font read back from the ROM ==')
    # 0x01A000 is the font base; its first tiles are blank padding, so show from 0x01A100
    orig = body[FONTOFF + 0x100:FONTOFF + 0x100 + 32*16]
    render_row(orig, 32, 3, os.path.join(HERE, 'poc_1_原字库.png'))

    for px, tag in ((8, '8x8'), (12, '12x12'), (16, '16x16')):
        allt = bytearray()
        got = ''
        for ch in '英雄戦記中文漢字翻訳可能亜':
            bm = bitmap(ch, px, 16)
            allt += b''.join(glyph_to_tiles(bm[ch]))
            got += ch
        render_row(bytes(allt), 16, 3, os.path.join(HERE, 'poc_2_%s_%s.png' % (tag, got)))
        print('   %s: %d chars -> %d tiles (%d bytes)' % (tag, len(got), len(allt)//16, len(allt)))

    # side-by-side comparison strip: 8x8 vs 12x12 for the same characters
    for px, tag in ((8, '8px'), (12, '12px')):
        allt = bytearray()
        for ch in '翻訳漢字確認困難':
            bm = bitmap(ch, px, 16)
            allt += b''.join(glyph_to_tiles(bm[ch]))
        render_row(bytes(allt), 16, 3, os.path.join(HERE, 'poc_3_legib_%s.png' % tag))
    print('done')

if __name__ == '__main__':
    main()