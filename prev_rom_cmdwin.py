"""Render the command window exactly as the engine will, from the built ROM.

The engine's routine at $03:F95D copies the 52 byte cell table at ROM 0x01F743
to WRAM and turns each byte into a tile map cell: the upper half comes from
FB[code] and the lower half from FA[code].  Drawing the font tiles those entries
point at is therefore a faithful picture of the Start menu, without having to
reach it in the emulator.

    python prev_rom_cmdwin.py [rom] [out.png]
"""
import sys
sys.path.insert(0, '.')
import kuniokun_map as km
from sfc_tools import unpack_8x8
from PIL import Image

rom_path = sys.argv[1] if len(sys.argv) > 1 else 'kuniokun_cn.smc'
out = sys.argv[2] if len(sys.argv) > 2 else 'hw/rom_cmdwin.png'
rom = open(rom_path, 'rb').read()

ROM_OFF = 0x01F743
ROWS, COLS = 2, 26
SCALE = 4
PAL = [(0, 0, 0), (255, 255, 255)]      # 1bpp preview: set bits are white

# font tile t: 16 bytes, 4bpp planar -> treat any non-zero pixel as "on"
def tile_bits(t):
    d = rom[km.FONT + t * 16: km.FONT + t * 16 + 16]
    return unpack_8x8(d)


# FA/FB must come from the *built* ROM: the build repoints ten codes at the
# window's static glyph tiles, and km.FA/km.FB hold the original tables.
fa = rom[km.FA_OFF:km.FA_OFF + 256]
fb = rom[km.FB_OFF:km.FB_OFF + 256]

tbl = rom[ROM_OFF:ROM_OFF + ROWS * COLS]
img = Image.new('RGB', (COLS * 8 * SCALE, ROWS * 16 * SCALE), PAL[0])
px = img.load()
used = {}
for r in range(ROWS):
    for c in range(COLS):
        code = tbl[r * COLS + c]
        used.setdefault(code, 0)
        used[code] += 1
        if code == 0:
            continue
        upper = fb[code]
        lower = fa[code]
        for half, t in ((0, upper), (1, lower)):
            bits = tile_bits(t)
            for y in range(8):
                for x in range(8):
                    if bits[y][x]:
                        X = (c * 8 + x) * SCALE
                        Y = (r * 16 + half * 8 + y) * SCALE
                        for dy in range(SCALE):
                            for dx in range(SCALE):
                                px[X + dx, Y + dy] = PAL[1]
img.save(out)
print('wrote %s (%dx%d)' % (out, img.size[0], img.size[1]))
print('cell codes used: %s' % ' '.join('%02X' % c for c in sorted(used)))
