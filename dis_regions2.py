"""dis_regions2.py -- same tracking disassembly, but robust, and the caller search
comes first so it always prints.  Focus: the routine that uploads to VMADD $6000
(the Japanese font window) -- if it runs every frame while text is on screen, it
wipes any glyph a runtime patcher writes there.
"""
import mos65xx

ROM = open(r"C:/Users/<user>/.zcode/workspace/default/sfc-recon/kuniokun_cn.smc", "rb").read()


def rom_of(bank, addr):
    return bank * 0x8000 + (addr - 0x8000)


print("=== callers: JSL $00:87xx / JSR $87xx / JSL other-bank targets near $6000 uploads ===")
for lo in range(0x00, 0x100, 1):
    for op in (0x22, 0x20):
        pat = bytes([op, lo, 0x87])
        i = 0
        while True:
            j = ROM.find(pat, i)
            if j < 0:
                break
            bk, ad = j // 0x8000, 0x8000 + (j % 0x8000)
            kind = "JSL $00:%04X" % (0x8700 + lo) if op == 0x22 else "JSR $%04X" % (0x8700 + lo)
            print("  %s at ROM %06X = $%02X:%04X" % (kind, j, bk, ad))
            i = j + 1

print()
print("=== every reference to ROM offsets around the $6000 upload (0x000760-0x0007C0) ===")
for tgt in range(0x8700, 0x87C0, 0x10):
    for op, nm in ((0x22, "JSL"), (0x20, "JSR")):
        pat = bytes([op, tgt & 0xFF, tgt >> 8])
        i = 0
        while True:
            j = ROM.find(pat, i)
            if j < 0:
                break
            bk, ad = j // 0x8000, 0x8000 + (j % 0x8000)
            print("  %s $00:%04X called at ROM %06X = $%02X:%04X" % (nm, tgt, j, bk, ad))
            i = j + 1


def dis(bank, addr, length, tag):
    off = rom_of(bank, addr)
    data = ROM[off:off + length]
    print()
    print("=" * 78)
    print("%s  $%02X:%04X  (ROM %06X, %d bytes)" % (tag, bank, addr, off, len(data)))
    print("=" * 78)
    m = x = 1
    i = 0
    while i < len(data):
        try:
            ins = mos65xx.decode(data, offset=i, address=addr + i, m=bool(m), x=bool(x))
        except Exception:
            print("  %04X  <undecodable tail>" % (addr + i))
            break
        b = data[i:i + ins.size]
        print("  %04X  %-11s m%d x%d  %s"
              % (addr + i, " ".join("%02X" % c for c in b), m, x, ins.text or ins.mnemonic))
        if ins.opcode == 0xE2:
            if ins.operand & 0x20:
                m = 1
            if ins.operand & 0x10:
                x = 1
        elif ins.opcode == 0xC2:
            if ins.operand & 0x20:
                m = 0
            if ins.operand & 0x10:
                x = 0
        i += ins.size


dis(0x00, 0x86F0, 0xF0, "VRAM upload routine around VMADD $6000/$6800")
dis(0x03, 0xEB2F, 0x60, "JSR $EB2F: message service called by the per-frame driver")
dis(0x03, 0xEA00, 0x30, "just before the box-edge code")