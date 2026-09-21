"""Render the yes/no choice box the way the engine builds it.

The box is not drawn by the text drawer: three script blocks (pointed at from
$03:F45B -> $03:F45F -> blocks) each fill the 64 byte cell buffer at $040A and
upload it to one VRAM map row.  This walks the same data out of a ROM and paints
the result with the font tiles at $0F8000, so the picture is what the game shows
without needing to reach the box in an emulator.

    python prev_choice.py <rom> <out.png> [prompt_sel]
"""
import sys
from PIL import Image, ImageDraw

FONT = 0x0F8000
BLOCK_TABLE = 0x1F45B          # $03:F45B: $0363 -> pointer table
ROW_ADDR_HI = 0x1F455          # $03:F455: $0395 -> VRAM word address high
ROW_ADDR_LO = 0x1F458          # $03:F458: $0395 -> VRAM word address low
CURSOR_TILE = 0x1F3C7          # $03:F3C7: Y -> tile
PAL = [(255, 255, 255), (170, 170, 170), (85, 85, 85), (0, 0, 0)]


def cell_at(rom, off):
    return rom[off] | ((rom[off + 1] & 1) << 8), rom[off + 1]


def bank3(v):
    """A pointer stored in a bank $03 table names $03:v, i.e. ROM v + 0x10000."""
    return v + 0x10000


def rows_of(rom, sel, nrows):
    """[(vram word addr, [ (tile, attr) x 32 ])] for prompt set `sel`."""
    p = bank3(rom[BLOCK_TABLE + sel * 2] | (rom[BLOCK_TABLE + sel * 2 + 1] << 8))
    out = []
    for r in range(nrows):
        q = bank3(rom[p + r * 2] | (rom[p + r * 2 + 1] << 8))
        addr = rom[ROW_ADDR_LO + r] | (rom[ROW_ADDR_HI + r] << 8)
        cells = [(0, 0)] * 32
        # $040A is a byte buffer: 64 bytes = 32 cells, cell j = bytes 2j, 2j+1,
        # and the block's first byte is the *byte* index it starts writing at.
        x = rom[q]
        n = rom[q + 1]
        for i in range(0, n, 2):
            cells[(x + i) // 2] = (rom[q + 2 + i], rom[q + 3 + i])
        out.append((addr, cells))
    return out


def paint(img, px, rom, addr, cells, cursor):
    """Draw one map row (32 cells wide, one word per cell)."""
    row = (addr >> 5) & 0x1F
    for c, (t, _a) in enumerate(cells):
        if c in cursor:
            t = cursor[c]
        off = FONT + t * 16
        if off + 16 > len(rom):
            continue
        for y in range(8):
            b0 = rom[off + y * 2]
            b1 = rom[off + y * 2 + 1]
            for x in range(8):
                bit = 7 - x
                v = ((b0 >> bit) & 1) | (((b1 >> bit) & 1) << 1)
                px[c * 8 + x, row * 8 + y] = PAL[v]


def main():
    rom = open(sys.argv[1], 'rb').read()
    out = sys.argv[2]
    sel = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    nrows = 3
    # the cursor: $0368 is the selected option (0 -> cell 18, 1 -> cell 22) and
    # the blink flag picks tile $F3C7[0] ($47 = arrow) or $F3C7[1] ($49 = blank)
    cur = {18: rom[CURSOR_TILE], 22: rom[CURSOR_TILE + 1]}
    rows = rows_of(rom, sel, nrows)
    img = Image.new('RGB', (32 * 8, 32 * 8), PAL[1])
    px = img.load()
    for addr, cells in rows:
        paint(img, px, rom, addr, cells, cur)
    img = img.crop((0, 27 * 8, 32 * 8, 33 * 8))
    img = img.resize((32 * 8 * 3, 6 * 8 * 3), Image.NEAREST)
    img.save(out)
    print('wrote %s' % out)


main()
