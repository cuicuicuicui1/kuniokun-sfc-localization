#!/usr/bin/env python3
"""
cgram_recon.py -- SNES CGRAM (palette) recon for
  初代熱血硬派くにおくん  (kuniokun__SF8127.smc, LoROM, 1MB, CRC32 56C05339)

Run:  python cgram_recon.py            (from the sfc-recon dir)
      python cgram_recon.py --rom PATH

Reports, with exact ROM file offsets:
  * every CGRAM access site  (STA/STZ $2122, STA/STZ $2121, DMA to B-bus $22/$00)
  * decoded BGR555 palettes for the known ROM palette tables
  * the text-layer tilemap attribute analysis (all STA $2119 sites)
  * the 2bpp font value histogram at 0x0F8000
  * optional PNG renders of the font

Confirmed-by-evidence facts are printed with their file offset so each can be
re-checked by hand.
"""
import sys, os

ROM_DEFAULT = "dl/roms/kuniokun__SF8127.smc"


# ---------------------------------------------------------------- ROM helpers
def load(path):
    return open(path, "rb").read()


def lorom(off):
    """file offset -> (bank, 16-bit address) for LoROM"""
    return off // 0x8000, 0x8000 + (off % 0x8000)


def find_all(d, pat):
    out, i = [], 0
    while True:
        j = d.find(pat, i)
        if j < 0:
            return out
        out.append(j)
        i = j + 1


def bgr555(w):
    """SNES CGRAM word -> (r,g,b) 0..255.  bits0-4=R,5-9=G,10-14=B, bit15 unused"""
    return ((w & 31) * 255 // 31, ((w >> 5) & 31) * 255 // 31, ((w >> 10) & 31) * 255 // 31)


def words(d, off, n):
    return [d[off + 2 * i] | (d[off + 2 * i + 1] << 8) for i in range(n)]


# ------------------------------------------------------- CGRAM access scanning
def scan_cgram_sites(d):
    print("=" * 78)
    print("CGRAM ACCESS SITES  (file offsets are ROM file positions)")
    print("=" * 78)

    checks = [
        ("STA $2122  (8D 22 21)", b"\x8d\x22\x21"),
        ("STZ $2122  (9C 22 21)", b"\x9c\x22\x21"),
        ("STA $2121  (8D 21 21)", b"\x8d\x21\x21"),
        ("STZ $2121  (9C 21 21)", b"\x9c\x21\x21"),
        ("LDA #$2200 (A9 00 22)", b"\xa9\x00\x22"),
        ("STA $2119  (8D 19 21)", b"\x8d\x19\x21"),
        ("STA $2118  (8D 18\x21)", b"\x8d\x18\x21"),
    ]
    for name, pat in checks:
        hits = find_all(d, pat)
        print("\n%-24s : %d hit(s)" % (name, len(hits)))
        for h in hits:
            b, a = lorom(h)
            print("   %06X  $%02X:%04X   next6=%s" % (h, b, a, d[h + 3:h + 9].hex(" ")))

    # LDA #$2200 followed by STA $43x0  => CGRAM DMA channel setup
    print("\n--- DMA channels whose B-bus destination is $2122 (LDA #$2200 : STA $43x0) ---")
    for h in find_all(d, b"\xa9\x00\x22"):
        for ch in range(8):
            if d[h + 3:h + 5] == bytes([0x8d, 0x10 * ch]) and d[h + 5] == 0x43:
                print("   setup %06X $%02X:%04X -> DMA ch%d" % (h, *lorom(h), ch))
    # also: LDA #$2100 would set CGADD as DMA dest -> never happens
    print("   LDA #$2100 (CGADD as DMA dest) hits: %d  (0 => CGADD never set by DMA)"
          % len(find_all(d, b"\xa9\x00\x21")))


# ------------------------------------------------------------ palette decoding
# ROM tables found by following the DMA setups (see report).
TABLES = [
    ("$02:988A (file 0x01188A)  Site B2: 112 words, 224-byte entries, idx $031F, -> CGADD 0 (pal 0-6)",
     0x01188A, 224, 7),
    ("$02:984A (file 0x01184A)  Site B1 branch B: 16 words -> CGADD 0 (pal 0)",
     0x01184A, 32, 1),
    ("$02:986A (file 0x01186A)  Site B1 branch A: 16 words -> CGADD 0 (pal 0)",
     0x01186A, 32, 1),
    ("$02:B8EA (file 0x0138EA)  Site D: 16-word palettes -> CGADD 0x80+16*X (pal 8-15)",
     0x0138EA, 32, 1),
    ("$00:B6D0 (file 0x0036D0)  CPU loop: 6 words -> CGADD 0x31 (colors 49-54)",
     0x0036D0, 12, 1),
    ("$00:B964 (file 0x003964)  CPU loop: 6 words -> CGADD 0x1D (colors 29-34)",
     0x003964, 12, 1),
]


def decode_tables(d, entry=0):
    print("\n" + "=" * 78)
    print("ROM PALETTE TABLES (BGR555, little-endian; rgb = v*255//31)")
    print("=" * 78)
    for desc, off, stride, nent in TABLES:
        print("\n### %s" % desc)
        print("    entry %d at file 0x%06X" % (entry, off + stride * entry))
        n = stride // 2
        ws = words(d, off + stride * entry, n)
        for i in range(0, n, 16):
            print("    words %3d-%3d :" % (i, i + 15))
            for k in range(i, min(i + 16, n)):
                r, g, b = bgr555(ws[k])
                print("      [%3d] 0x%04X  (%3d,%3d,%3d)" % (k, ws[k], r, g, b))


# --------------------------------------------------- text layer / tilemap proof
def tilemap_proof(d):
    print("\n" + "=" * 78)
    print("TEXT-LAYER TILEMAP ATTRIBUTE  (every STA $2119 site)")
    print("=" * 78)
    for h in find_all(d, b"\x8d\x19\x21"):
        # the attribute byte is loaded immediately before 8D 19 21
        prev = d[h - 2:h]
        attr = prev[1] if prev[0] == 0xA9 else None
        b, a = lorom(h)
        if attr is None:
            print("   %06X $%02X:%04X  attr=??? (not immediate)" % (h, b, a))
            continue
        pal = (attr >> 2) & 7
        pri = (attr >> 5) & 1
        print("   %06X $%02X:%04X  LDA #$%02X -> attr 0x%02X  palette=%d priority=%d flips=%d"
              % (h, b, a, attr, attr, pal, pri, (attr >> 6) & 3))
    print("   => tilemap entry = 16 bits: bits0-9 tile#, 10-12 palette, 13 prio, 14-15 flip")
    print("      high byte 0x24 = 0b00100100 -> palette bits(10-12)=1, prio(13)=1")


# ------------------------------------------------------------------ font probe
FONT = 0x0F8000


def font_probe(d):
    print("\n" + "=" * 78)
    print("FONT at file 0x%06X  (2bpp 8x8, 16 bytes/tile, MSB=leftmost)" % FONT)
    print("=" * 78)
    print("   value = plane0bit | plane1bit<<1   (0=bg, 1=face, 2=shadow, 3=accent)")

    def tile_vals(to):
        v = [[0] * 8 for _ in range(8)]
        for y in range(8):
            p0, p1 = d[to + y * 2], d[to + y * 2 + 1]
            for x in range(8):
                v[y][x] = ((p0 >> (7 - x)) & 1) | (((p1 >> (7 - x)) & 1) << 1)
        return v

    for blk in range(4):                       # tiles 0-255 = the font
        cnt = [0, 0, 0, 0]
        for t in range(64):
            for row in tile_vals(FONT + (blk * 64 + t) * 16):
                for val in row:
                    cnt[val] += 1
        tot = sum(cnt)
        print("   tiles %3d-%3d (file %06X): 0=%.1f%% 1=%.1f%% 2=%.1f%% 3=%.1f%%"
              % (blk * 64, blk * 64 + 63, FONT + blk * 64 * 16,
                 100 * cnt[0] / tot, 100 * cnt[1] / tot,
                 100 * cnt[2] / tot, 100 * cnt[3] / tot))

    def render(off, ntiles, path, colsN=16, scale=6,
               pal=((0, 0, 0), (255, 0, 0), (0, 220, 0), (0, 100, 255))):
        from PIL import Image
        rows = (ntiles + colsN - 1) // colsN
        im = Image.new("RGB", (colsN * 8 * scale, rows * 8 * scale), (60, 60, 60))
        px = im.load()
        for t in range(ntiles):
            to = off + t * 16
            cx, cy = (t % colsN) * 8, (t // colsN) * 8
            for y, row in enumerate(tile_vals(to)):
                for x, val in enumerate(row):
                    col = pal[val]
                    for dy in range(scale):
                        for dx in range(scale):
                            px[(cx + x) * scale + dx, (cy + y) * scale + dy] = col
        im.save(path)
        print("   saved %s %s" % (path, im.size))

    return render, tile_vals


# ----------------------------------------------------------------------- main
def main():
    rom = ROM_DEFAULT
    if "--rom" in sys.argv:
        rom = sys.argv[sys.argv.index("--rom") + 1]
    d = load(rom)
    print("ROM %s  %d bytes" % (rom, len(d)))
    print("title bytes @0x7FC0 = %s" % d[0x7FC0:0x7FCC].decode("shift_jis", "replace"))

    scan_cgram_sites(d)
    decode_tables(d)
    tilemap_proof(d)
    render, tile_vals = font_probe(d)

    if "--png" in sys.argv:
        render(FONT, 64, "font_tiles_000_063.png")
        render(FONT + 64 * 16, 64, "font_tiles_064_127.png")
        render(FONT + 96 * 16, 128, "font_tiles_096_223.png")
        # same font drawn with the actual text palette (CGRAM 16-31, entry 0 of $02:988A)
        pal1 = words(d, 0x01188A, 112)[16:32]
        render(FONT + 96 * 16, 128, "font_tiles_096_223_pal1.png",
               pal=[bgr555(w) for w in pal1])

    print("\nDone.")


if __name__ == "__main__":
    main()
