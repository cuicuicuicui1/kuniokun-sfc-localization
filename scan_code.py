"""Scan 65816 code for pointer-table load patterns."""
import struct
from collections import Counter, defaultdict

d = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()
N = len(d)

# opcode -> (name, operand_len)
OPS = {
    0xB9: ('LDA abs,Y', 2), 0xBD: ('LDA abs,X', 2), 0xAD: ('LDA abs', 2),
    0xBF: ('LDA long,X', 3), 0xB7: ('LDA [dp],Y', 1), 0xA7: ('LDA [dp]', 1),
    0xBC: ('LDY abs,X', 2), 0xBE: ('LDX abs,Y', 2), 0xAE: ('LDX abs', 2),
    0xB6: ('LDX dp,Y', 1), 0xAF: ('LDA long', 3), 0x9D: ('STA abs,X', 2),
    0x9F: ('STA long,X', 3), 0x99: ('STA abs,Y', 2),
}

hits = defaultdict(list)   # opcode -> list of (site, operand)
for off in range(N - 4):
    op = d[off]
    if op in OPS:
        name, ln = OPS[op]
        if op in (0xBF, 0xAF, 0x9F):
            lo, hi, bk = d[off + 1], d[off + 2], d[off + 3]
            hits[op].append((off, lo | (hi << 8), bk))
        elif ln == 2:
            lo, hi = d[off + 1], d[off + 2]
            hits[op].append((off, lo | (hi << 8), None))
        else:
            hits[op].append((off, d[off + 1], None))

print('opcode hit counts:')
for op, name, ln in [(k, v[0], v[1]) for k, v in OPS.items()]:
    print('  %02X %-12s %5d' % (op, name, len(hits[op])))

# ---- 24-bit long loads: collect (bank, addr) and see if they form tables
print('\n24-bit long,X loads (BF) with target in bank $00-$07:')
longs = hits[0xBF]
cnt = Counter()
for site, addr, bk in longs:
    cnt[(bk, addr)] += 1
# print grouped by bank
bybank = defaultdict(list)
for site, addr, bk in longs:
    bybank[bk].append((addr, site))
for bk in sorted(bybank):
    addrs = sorted(set(a for a, s in bybank[bk]))
    print('  bank $%02X: %d sites, %d distinct addrs' % (bk, len(bybank[bk]), len(addrs)))

# ---- look for B9/BF sites whose 16-bit address is followed by an increasing table
print('\n16-bit abs,Y/X loads (B9/BD) whose address starts an increasing u16 run >=8:')
def runlen(base, maxn=2000):
    prev = -1; L = 0
    while L < maxn and base + 2 * L + 2 <= N:
        v = d[base + 2 * L] | (d[base + 2 * L + 1] << 8)
        if v <= prev or v < 0x8000:
            break
        prev = v; L += 1
    return L

found = {}
for op in (0xB9, 0xBD):
    for site, addr, _ in hits[op]:
        if 0x8000 <= addr <= 0xFFFF:
            # table is at SNES addr in DBR bank; try bank = site's bank (LoROM)
            for bank in range(32):
                ro = bank * 0x8000 + (addr - 0x8000)
                if 0 <= ro < N:
                    L = runlen(ro)
                    if L >= 8:
                        found[(op, site, addr, bank)] = (ro, L)
for (op, site, addr, bank), (ro, L) in sorted(found.items(), key=lambda x: -x[1][1])[:60]:
    print('  op=%02X site=%06X addr=%04X bank=%2d table_rom=%06X len=%d' %
          (op, site, addr, bank, ro, L))
