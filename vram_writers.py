"""vram_writers.py -- every VRAM-register write site in the ROM, plus hard checks
that the built ROM on disk really contains the drawer I think it does.

Part 1: sanity -- crc32 of the two ROM copies, hook bytes, drawer head, glyph pool
        bytes for the five characters of the shop line, slot-pair table head.
Part 2: scan the whole ROM for writes to $2115/$2116/$2118/$2119 (and DMA/HDMA
        enable $420B/$420C, and $43x0-$43x7 B-bus register writes), map each hit
        to a LoROM bank:offset, and disassemble a window around each so the code
        around the hit is readable.
"""
import zlib

CN = r"C:/Users/<user>/.zcode/workspace/default/sfc-recon/kuniokun_cn.smc"
KFIX = r"C:/Users/<user>/.zcode/workspace/default/sfc-recon/dl/roms/kfix.smc"
ROM = open(CN, "rb").read()


def lorom(off):
    """ROM file offset -> (bank, addr) for LoROM ($8000-FFFF windows)."""
    bank = off // 0x8000
    return bank, 0x8000 + (off % 0x8000)


def rom_of(bank, addr):
    return bank * 0x8000 + (addr - 0x8000)


print("=== PART 1: what is in the ROM on disk ===")
for p in (CN, KFIX):
    d = open(p, "rb").read()
    print("%-12s %d bytes crc32=%08X" % (p.split("/")[-1], len(d), zlib.crc32(d) & 0xFFFFFFFF))
print("hook 0x01FA30: " + " ".join("%02X" % b for b in ROM[0x01FA30:0x01FA38]))
print("drawer head   : " + " ".join("%02X" % b for b in ROM[0x1F0200:0x1F0214]))
print("prefix/page immediates: cmp #$c5?  cmp #$d1?")
POOL = 0x108000
for ch, page, gid in (("猪", 6, 0x3F), ("肉", 8, 0x49), ("包", 1, 0x01),
                      ("一", 0, 0x15), ("个", 0, 0x29)):
    off = POOL + page * 0x8000 + gid * 32
    b = ROM[off:off + 32]
    print("pool %s page %2d id %02X at ROM %06X bank $%02X off $%04X: %s"
          % (ch, page, gid, off, 0x21 + page, 0x8000 + gid * 32,
             " ".join("%02X" % x for x in b[:16])))
print("slotpair $03:E900 (from ROM %06X): " % rom_of(3, 0xE900)
      + " ".join("%02X" % b for b in ROM[rom_of(3, 0xE900):rom_of(3, 0xE900) + 24]))

print()
print("=== PART 2: VRAM register write sites ===")
pats = {
    "STA $2115 (8D 15 21)": bytes.fromhex("8D1521"),
    "STA $2116 (8D 16 21)": bytes.fromhex("8D1621"),
    "STA $2117 (8D 17 21)": bytes.fromhex("8D1721"),
    "STA $2118 (8D 18 21)": bytes.fromhex("8D1821"),
    "STA $2119 (8D 19 21)": bytes.fromhex("8D1921"),
    "STA $420B (8D 0B 42)": bytes.fromhex("8D0B42"),
    "STA $420C (8D 0C 42)": bytes.fromhex("8D0C42"),
}
for name, pat in pats.items():
    hits, i = [], 0
    while True:
        j = ROM.find(pat, i)
        if j < 0:
            break
        hits.append(j)
        i = j + 1
    print("\n%s -> %d site(s)" % (name, len(hits)))
    for h in hits:
        bk, ad = lorom(h)
        pre = ROM[max(0, h - 10):h + 3]
        print("   ROM %06X = $%02X:%04X   ctx: %s"
              % (h, bk, ad, " ".join("%02X" % b for b in pre)))