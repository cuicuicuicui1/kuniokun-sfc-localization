"""find_pool_in_vram.py -- where did the drawer's 32 glyph bytes go?

Inputs (no emulator needed):
  hw/kfix20_vram.bin  -- 64 KiB dump of the VRAM memory domain (byte addressed)
  kuniokun_cn.smc     -- the patched ROM: glyph pool + the original Japanese font

For each of the five characters the on-screen slots resolve to, we locate its
32 pool bytes inside the dump.  A miss means the drawer's CPU writes to $2118
never reached VRAM at all; a hit at a different address tells us what VMADD the
write actually used.  Byte 0 of each destination word is also checked against the
pool's last byte, which is what an 8-bit-mode store loop would leave behind.
"""
DUMP = r"C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/kfix20_vram.bin"
ROM = r"C:/Users/<user>/.zcode/workspace/default/sfc-recon/kuniokun_cn.smc"
POOL_ROM = 0x108000
FONT_ROM = 0x0F8000      # original Japanese font, 8x8 2bpp, 16 bytes per tile
SLOTPAIR = 0x01E900

vram = open(DUMP, "rb").read()
rom = open(ROM, "rb").read()
print("dump %d bytes, rom %d bytes" % (len(vram), len(rom)))

# (char, page, slot, tile) -- from identify_scene.py / the on-screen tilemap
CELLS = [("猪", 6, 0x3F, None), ("肉", 8, 0x49, None), ("包", 1, 0x01, None),
         ("一", 0, 0x15, None), ("个", 0, 0x29, None)]

# on-screen tile pairs measured earlier (upper, lower) by hw/v16.lua
MEASURED = {"猪": (0x09C, 0x09D), "肉": (0x0E6, 0x0E7), "包": (0x004, 0x005),
            "一": (0x03E, 0x03F), "个": (0x068, 0x069)}

for ch, page, slot, _t in CELLS:
    off = POOL_ROM + page * 0x8000 + slot * 32
    pool = rom[off:off + 32]
    assert len(pool) == 32
    up, lo = MEASURED[ch]
    # a cell lives at VRAM words $6000 + tile*8 => bytes ($C000 + tile*16)
    cell_bytes = 0xC000 + up * 16
    in_vram = vram[cell_bytes:cell_bytes + 32]
    jp = rom[FONT_ROM + up * 16:FONT_ROM + up * 16 + 32]
    hits = [i for i in range(0, len(vram) - 32 + 1) if vram[i:i + 32] == pool]
    print("\n%s pool@ROM %06X  screen tiles (%03X,%03X) -> cell bytes %04X..%04X"
          % (ch, off, up, lo, cell_bytes, cell_bytes + 31))
    print("  slotpair says tile %03X (table[%02X]=%02X)"
          % (up, slot, rom[SLOTPAIR + slot]))
    print("  pool  : " + " ".join("%02X" % b for b in pool))
    print("  vram  : " + " ".join("%02X" % b for b in in_vram))
    print("  jpfont: " + " ".join("%02X" % b for b in jp))
    print("  vram == pool   : %s" % (in_vram == pool))
    print("  vram == jpfont : %s" % (in_vram == jp))
    print("  full 32-byte pool found in VRAM at: %s"
          % (["%04X" % h for h in hits] or "NOWHERE"))
    print("  byte0 %02X vs pool[31] %02X (8-bit store loop would leave pool[31] here)"
          % (in_vram[0], pool[31]))
    # any half of the glyph present?
    for name, part in (("first16", pool[:16]), ("last16", pool[16:])):
        h = [i for i in range(0, len(vram) - 16 + 1) if vram[i:i + 16] == part]
        print("  %s found at: %s" % (name, ["%04X" % x for x in h] or "NOWHERE"))

# how many non-zero tiles are in the font window at all, for context
win = vram[0xC000:0xD000]
print("\nfont window bytes 0xC000-0xCFFF: nonzero=%d" % sum(1 for b in win if b))
print("original japanese font tile 0..0x7F matches window: %s"
      % (win[:0x1000] == rom[FONT_ROM:FONT_ROM + 0x1000]))
print("original japanese font tile 0x80..0xFF matches window+0x1000: %s"
      % (win[0x1000:0x2000] == rom[FONT_ROM + 0x1000:FONT_ROM + 0x2000]))