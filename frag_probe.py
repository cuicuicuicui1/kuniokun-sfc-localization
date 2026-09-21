"""frag_probe.py -- is the glyph data in VRAM in fragments?

A failed VMADD (e.g. a HDMA channel rewriting $2116 between two of my stores)
would leave the glyph's words scattered rather than contiguous.  So we look for
the distinctive byte runs of 猪's glyph separately:

  contiguous : 5E 00 40 00 44 00 1F 00        (pool words 2..5)
  single word: 5E 00 and 1F 00 and C0 00      (any address at all)

and we print where each hit is, so a hit inside the font window ($C000-$CFFF)
can be told apart from a hit elsewhere.
"""
DUMP = r"C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/kfix20_vram.bin"
vram = open(DUMP, "rb").read()
print("dump %d bytes" % len(vram))


def find(pat):
    out, i = [], 0
    while True:
        j = vram.find(pat, i)
        if j < 0:
            return out
        out.append(j)
        i = j + 1


def where(addr):
    if 0xC000 <= addr < 0xD000:
        return "FONT WINDOW word %04X tile %03X" % ((addr - 0xC000) // 2 + 0x6000,
                                                    (addr - 0xC000) // 16)
    if 0xF000 <= addr < 0x10000:
        return "tilemap area word %04X" % ((addr - 0xC000) // 2 + 0x6000)
    return "other word %04X" % ((addr - 0xC000) // 2 + 0x6000)


for name, pat in (("contiguous 8 bytes 5E00400044001F00", bytes.fromhex("5E00400044001F00")),
                  ("word 005E as bytes 5E 00", bytes.fromhex("5E00")),
                  ("word 001F as bytes 1F 00", bytes.fromhex("1F00")),
                  ("word 0044 as bytes 44 00", bytes.fromhex("4400")),
                  ("word 00C0 as bytes C0 00", bytes.fromhex("C000"))):
    hits = find(pat)
    print("\n%s -> %d hit(s)" % (name, len(hits)))
    for h in hits[:12]:
        print("   byte %05X  %s" % (h, where(h)))

# what the plain Japanese font tile 09C has, for reference
rom = open(r"C:/Users/<user>/.zcode/workspace/default/sfc-recon/kuniokun_cn.smc", "rb").read()
jp = rom[0x0F8000 + 0x9C * 16:0x0F8000 + 0x9C * 16 + 16]
print("\njapanese font tile 09C: " + " ".join("%02X" % b for b in jp))
print("present in dump: %d time(s)" % len(find(jp)))
print("dump at 0xC9C0: " + " ".join("%02X" % b for b in vram[0xC9C0:0xC9D0]))
print("dump at 0xC9D0: " + " ".join("%02X" % b for b in vram[0xC9D0:0xC9E0]))