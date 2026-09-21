"""Find which BG layer of a VRAM dump reproduces the screenshot, and where its
tiles live, so the same graphics can be located in the ROM.

Brute force over the only unknowns that matter for a static screen:
    character base (0x0000..0xE000 step 0x2000)
    bits per pixel (2 / 4 / 8)
    tilemap base      (0x0000..0xFC00 step 0x400)
    tilemap size      (32x32 / 64x32 / 32x64 / 64x64)
and score each assembled picture against the reference frame.
"""
import os
import sys

import numpy as np
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.join(BASE, 'hw')
W, H = 256, 224
COLS, ROWS = W // 8, H // 8


def load(tag):
    vram = np.frombuffer(open(os.path.join(HW, tag + '_vram64.bin'), 'rb').read(), dtype=np.uint8)
    cgram = np.frombuffer(open(os.path.join(HW, tag + '_cgram.bin'), 'rb').read(), dtype=np.uint8)
    return vram, cgram


def cgram_rgb(cgram):
    w = cgram[0::2].astype(np.uint16) | (cgram[1::2].astype(np.uint16) << 8)
    r = (w & 31) * 255 // 31
    g = ((w >> 5) & 31) * 255 // 31
    b = ((w >> 10) & 31) * 255 // 31
    return np.stack([r, g, b], axis=1).astype(np.uint8)


def decode_all(vram, charbase, bpp, nt=1024):
    """(nt, 8, 8) colour indices for every tile at this character base.

    SNES tile layout: row major, one byte per bitplane inside a row, so the byte
    for row y / plane p sits at y*bpp + p.  Verified against the game's own font
    at VRAM $C000, which decodes to readable ASCII and kana.
    """
    base = charbase + np.arange(nt) * (bpp * 8)
    out = np.zeros((nt, 8, 8), dtype=np.uint8)
    for y in range(8):
        for p in range(bpp):
            b = vram[(base + y * bpp + p) & 0xFFFF].astype(np.uint16)
            bits = (b[:, None] >> np.arange(7, -1, -1)[None, :]) & 1
            out[:, y, :] |= (bits << p).astype(np.uint8)
    return out


def map_offsets(size):
    ys, xs = np.mgrid[0:ROWS, 0:COLS]
    if size == 0:
        return (ys * 32 + xs).astype(np.int32)
    if size == 1:
        return ((xs // 32) * 0x400 + ys * 32 + (xs % 32)).astype(np.int32)
    if size == 2:
        return ((ys // 32) * 0x400 + (ys % 32) * 32 + xs).astype(np.int32)
    return (((ys // 32) * 2 + (xs // 32)) * 0x400 + (ys % 32) * 32 + (xs % 32)).astype(np.int32)


OFFS = {s: map_offsets(s) for s in (0, 1, 2, 3)}


def render(vram_words, tiles, mapbase, size, cg):

    off = mapbase // 2 + OFFS[size]
    if off.max() >= 0x8000:
        return None
    words = vram_words[off]
    idx = (words & 0x3FF).astype(np.int32)
    pal = ((words >> 10) & 7).astype(np.uint8)
    fx = ((words >> 14) & 1).astype(bool)
    fy = ((words >> 15) & 1).astype(bool)
    t = tiles[idx]
    t = np.where(fy[:, :, None, None], t[:, :, ::-1, :], t)
    t = np.where(fx[:, :, None, None], t[:, :, :, ::-1], t)
    pic = t.transpose(0, 2, 1, 3).reshape(ROWS * 8, COLS * 8)
    cidx = np.repeat(np.repeat(pal, 8, axis=0), 8, axis=1)
    rgb = cg[cidx * 16 + pic]
    return rgb, idx


def main():
    tag = sys.argv[1]
    shot = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HW, tag + '.png')
    vram, cgram = load(tag)
    cg = cgram_rgb(cgram)
    vram_words = vram[0::2].astype(np.uint16) | (vram[1::2].astype(np.uint16) << 8)
    ref = np.asarray(Image.open(shot).convert('RGB').resize((W, H), Image.NEAREST))

    best = []
    for bpp in (2, 4, 8):
        for charbase in range(0, 0x10000, 0x2000):
            tiles = decode_all(vram, charbase, bpp)
            if not tiles.any():
                continue
            for mapbase in range(0, 0x10000, 0x400):
                for size in (0, 1, 2, 3):
                    got = render(vram_words, tiles, mapbase, size, cg)
                    if got is None:
                        continue
                    rgb, idx = got
                    s = float((rgb == ref).all(axis=2).mean())
                    if s > 0.25:
                        print('score=%.4f bpp=%d char=%04X map=%04X size=%d ntiles=%d'
                              % (s, bpp, charbase, mapbase, size, len(np.unique(idx))))
                        best.append((s, bpp, charbase, mapbase, size))
    best.sort(reverse=True)
    print('--- top ---')
    for s, bpp, charbase, mapbase, size in best[:10]:
        print('score=%.4f bpp=%d char=%04X map=%04X size=%d' % (s, bpp, charbase, mapbase, size))


if __name__ == '__main__':
    main()