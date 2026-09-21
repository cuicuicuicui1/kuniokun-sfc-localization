"""Dump the 0xE0-0xEF macro jump table + routines, and find all references to the renderer."""
import re

d = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()


def lorom(off):
    bank = off // 0x8000
    return (bank, 0x8000 + (off % 0x8000))


def snes(off):
    b, a = lorom(off)
    return '$%02X:%04X' % (b, a)


print('=== bytes ROM 0x01EB80..0x01ED40 ===')
for i in range(0x01EB80, 0x01ED40, 16):
    print('%06X (%s): %s' % (i, snes(i), ' '.join('%02X' % x for x in d[i:i + 16])))

print()
print('=== jump table at ROM 0x01EC0D (codes 0xE0-0xEF), 16-bit entries ===')
for i in range(16):
    lo = d[0x01EC0D + 2 * i]
    hi = d[0x01EC0E + 2 * i]
    tgt = lo | (hi << 8)
    rom = 0x18000 + (tgt - 0x8000)
    print('  code 0x%02X -> $%04X  (ROM 0x%06X)' % (0xE0 + i, tgt, rom))

print()
print('=== references to renderer entry points ===')
targets = {
    '0x00FC77 (JSR entry, table idx)': 0xFC77,
    '0x00FC8E (SEP/LDY loop entry)': 0xFC8E,
    '0x00FC92 (loop top)': 0xFC92,
    '0x00FCC7 (deco routine)': 0xFCC7,
    '0x00F969 (set $2115)': 0xF969,
}
for name, a in targets.items():
    lo, hi = a & 0xFF, a >> 8
    # JSR absolute: 20 lo hi ; JML long: 5C lo hi bank
    for opc, tag in ((0x20, 'JSR'), (0x4C, 'JMP'), (0x5C, 'JML')):
        hits = []
        for m in re.finditer(re.escape(bytes([opc, lo, hi])), d):
            o = m.start()
            if opc == 0x5C:
                hits.append((o, d[o + 3]))
            else:
                hits.append((o, None))
        if hits:
            print('  %-32s %s x%d: %s' % (name, tag, len(hits),
                  ' '.join('%06X(%s)' % (o, snes(o)) for o, _ in hits[:10])))
            for o, bk in hits[:6]:
                ctx = d[o - 6:o + 4]
                print('        ctx %06X: %s' % (o - 6, ' '.join('%02X' % x for x in ctx)))