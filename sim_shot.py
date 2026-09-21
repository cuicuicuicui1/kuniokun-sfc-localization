"""Render a message box the way the patched ROM would draw it.

Preloads the original 256-tile font into VRAM $6000 (as the game's font DMA
does at boot), runs the patched renderer for one string, then paints the
tilemap band into a PNG so the result can be inspected without an emulator.

    python -u sim_shot.py <hex text offset> [cells] [out.png] [scale]
"""
import json
import sys

from PIL import Image

import cnbuild
import sim_verify as sv
from sim65816 import CPU

ORIG = cnbuild.ORIG_ROM
CURSOR = 0x7800
FONT = 0x0F8000

# BG palette 1 (CGRAM 16-31): idx0 bg, idx1 ink, idx2 shadow
INK = (255, 246, 230)
SHADOW = (230, 222, 205)
BG = (0, 0, 0)


def load_font(cpu):
    d = open(ORIG, 'rb').read()
    for t in range(256):
        base = FONT + t * 16
        for y in range(8):
            p0 = d[base + y * 2]
            p1 = d[base + y * 2 + 1]
            cpu.vram[(0x6000 + t * 8 + y) & 0x7FFF] = p0 | (p1 << 8)


def cells_png(cpu, path, cols=32, rows=2, scale=4):
    img = Image.new('RGB', (cols * 8 * scale, rows * 8 * scale), BG)
    px = img.load()
    for r in range(rows):
        for c in range(cols):
            ent = cpu.vram[(CURSOR + r * 32 + c) & 0x7FFF]
            tile = ent & 0x3FF
            for y in range(8):
                w = cpu.vram[(0x6000 + tile * 8 + y) & 0x7FFF]
                p0, p1 = w & 0xFF, w >> 8
                for x in range(8):
                    v = ((p0 >> (7 - x)) & 1) | (((p1 >> (7 - x)) & 1) << 1)
                    if v == 0:
                        continue
                    col = INK if v == 1 else SHADOW if v == 2 else (255, 255, 255)
                    for dy in range(scale):
                        for dx in range(scale):
                            px[((c * 8 + x) * scale + dx,
                                (r * 8 + y) * scale + dy)] = col
    img.save(path)
    return img.size


def main():
    off = int(sys.argv[1], 16)
    nb = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    out = sys.argv[3] if len(sys.argv) > 3 else 'shot_%06X.png' % off
    scale = int(sys.argv[4]) if len(sys.argv) > 4 else 4

    amap = json.load(open(cnbuild.BASE + '/cn_addr_map.json'))
    key = '%06X' % off
    rom = open(sv.ROM, 'rb').read()
    cpu = CPU(rom)
    load_font(cpu)
    # run the patched renderer from a clean VRAM/tilemap state
    cpu.vram = cpu.vram  # keep the font
    run = sv.run
    saved = cpu.vram[:]
    enc, tr = sv.build_order()
    drawn = [c for c in sv.expected_cells(tr[key], enc.glyphs) if c[0] != 'ctrl']
    nb = max(1, min(nb, len(drawn)))
    cpu2 = run(rom, amap[key], nb)
    # merge: font stays, tilemap/glyph regions come from cpu2
    v = saved[:]
    for i in range(0x7800, 0x7840):
        v[i] = cpu2.vram[i]
    for i in range(0x6000, 0x6800):
        if cpu2.vram[i] != 0 or saved[i] == 0:
            v[i] = cpu2.vram[i]
    cpu.vram = v
    size = cells_png(cpu, out, scale=scale)
    print('%s -> %s %s  (cells=%d)' % (key, out, size, nb))


if __name__ == '__main__':
    main()