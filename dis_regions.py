"""dis_regions.py -- tracking disassembly of the regions that matter now:

  $03:E9B0..$03:EB80  message-area clear, script flush, and JSR $EB2F
  $00:86C0..$00:87E0  the VRAM upload routine that targets VMADD $6000/$6800
                      (= the font / pattern upload; who calls it and when?)

and a caller search for the upload routine's entry point.
"""
import mos65xx

ROM = open(r"C:/Users/<user>/.zcode/workspace/default/sfc-recon/kuniokun_cn.smc", "rb").read()


def rom_of(bank, addr):
    return bank * 0x8000 + (addr - 0x8000)


def dis(bank, addr, length, tag):
    off = rom_of(bank, addr)
    data = ROM[off:off + length]
    print("=" * 78)
    print("%s  $%02X:%04X  (ROM %06X, %d bytes)" % (tag, bank, addr, off, len(data)))
    print("=" * 78)
    m = x = 1  # 8-bit A and X at entry (most of this code runs in 8-bit)
    i = 0
    while i < len(data):
        ins = mos65xx.decode(data, offset=i, address=addr + i, m=bool(m), x=bool(x))
        if ins is None:
            print("  %04X  ???" % (addr + i))
            i += 1
            continue
        b = data[i:i + ins.size]
        print("  %04X  %-9s  m%d x%d  %-22s %s"
              % (addr + i, " ".join("%02X" % c for c in b), m, x, ins.mnemonic, ins.operand))
        if ins.opcode == 0xE2:      # sep
            if ins.operand & 0x20:
                m = 1
            if ins.operand & 0x10:
                x = 1
        elif ins.opcode == 0xC2:    # rep
            if ins.operand & 0x20:
                m = 0
            if ins.operand & 0x10:
                x = 0
        elif ins.mnemonic in ("rtl", "rts", "jml", "jmp", "bra"):
            print("       -- flow leaves linear order here")
        i += ins.size


dis(0x03, 0xE9B0, 0x50, "message-area clear + $2115 setup")
dis(0x03, 0xEA20, 0x80, "script flush region")
dis(0x03, 0xEB2F, 0x50, "what the driver calls via JSR $EB2F")
print()
dis(0x00, 0x86C0, 0x120, "VRAM upload routine (VMADD $6000/$6800 targets)")

print()
print("=== callers of the $6000-targeting upload: search JSL/JSR $00:87xx ===")
for lo in range(0x60, 0x90):
    for op, name in ((0x22, "JSL $00:%04X"), (0x20, "JSR $%04X")):
        pat = bytes([op, lo, 0x87])
        i, hits = 0, []
        while True:
            j = ROM.find(pat, i)
            if j < 0:
                break
            hits.append(j)
            i = j + 1
        for h in hits:
            bk, ad = h // 0x8000, 0x8000 + (h % 0x8000)
            print("  %s at ROM %06X = $%02X:%04X" % (name % (0x8700 + lo), h, bk, ad))