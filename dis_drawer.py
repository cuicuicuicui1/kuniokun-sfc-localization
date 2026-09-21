"""dis_drawer.py -- full disassembly of the patched drawer copy at ROM 0x1F0200.

The drawer hook is 0x01FA30 <- JML $3E:8200, and LoROM maps $3E:8200 to ROM
0x1F0200.  This dumps every instruction with its ROM offset so the glyph-upload
block can be read exactly as the console will execute it.
"""
import mos65xx

ROM = r"C:/Users/<user>/.zcode/workspace/default/sfc-recon/kuniokun_cn.smc"
E3_DRAWER = 0x1F0200
E3_PRELOAD = 0x1F0000
E3_DISPATCH = 0x1F0080
E3_SLOTPAIR = 0x1F0180
B3_SANITIZE = 0x01E970
B3_SLOTPAIR = 0x01E900

rom = open(ROM, "rb").read()
m = mos65xx.MOS65xx()

for name, off, size in (("preload", E3_PRELOAD, 0x22),
                        ("dispatch", E3_DISPATCH, 0x120),
                        ("slotpair(A3)", E3_SLOTPAIR, 0x90),
                        ("drawer", E3_DRAWER, 0x160),
                        ("sanitize", B3_SANITIZE, 0x20)):
    print("=" * 78)
    print("%s @ ROM %06X = $%02X:%04X" % (name, off, (off // 0x8000), 0x8000 + (off % 0x8000)))
    print("=" * 78)
    buf = rom[off:off + size]
    print("raw: " + " ".join("%02X" % b for b in buf[:0x40]))
    text = m.disassemble(buf, address=off)
    for line in text.splitlines():
        print("  " + line)

print("=" * 78)
print("hook sites")
for off, want in ((0x01FA30, "JML $3E:8200"), (0x00FC79, "JML $3E:8000"),
                  (0x00FC85, "2-byte patch"), (0x00FC92, "JML $3E:8080")):
    print("  ROM %06X: %s" % (off, " ".join("%02X" % b for b in rom[off:off + 4])))