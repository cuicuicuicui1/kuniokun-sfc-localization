"""Find every reference to any address operand FCxx so we can locate renderer entry points."""
import re

d = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()


def lorom(off):
    return off // 0x8000, 0x8000 + (off % 0x8000)


def snes(off):
    b, a = lorom(off)
    return '$%02X:%04X' % (b, a)


print('=== all occurrences of operand bytes 77 FC / 8E FC / 92 FC / C7 FC ===')
for want in (0x77, 0x8E, 0x92, 0xC7, 0xC9):
    pat = bytes([want, 0xFC])
    hits = [m.start() for m in re.finditer(re.escape(pat), d)]
    print()
    print('--- %02X FC : %d hits' % (want, len(hits)))
    for o in hits[:14]:
        # show 6 bytes before to decode the instruction
        print('    at %06X (%s)  ctx: %s' % (o, snes(o),
              ' '.join('%02X' % x for x in d[o - 6:o + 4])))

print()
print('=== search for JSL/JSR to bank 1 code region (22 xx FC 01 / 20 xx FC) ===')
for a in (0xFC77, 0xFC8E, 0xFC92, 0xFCC7, 0xFCC9, 0xF969, 0xFB9E, 0xFA9E):
    lo, hi = a & 0xFF, a >> 8
    for opc, nm in ((0x22, 'JSL'), (0x20, 'JSR'), (0x4C, 'JMP'), (0x5C, 'JML')):
        pat = bytes([opc, lo, hi]) if opc != 0x22 else bytes([opc, lo, hi, 0x01])
        hits = [m.start() for m in re.finditer(re.escape(pat), d)]
        if hits:
            print('  %s $%04X x%d: %s' % (nm, a, len(hits), ' '.join('%06X' % h for h in hits[:10])))

print()
print('=== who writes $22/$23/$24 as the text pointer (85 22 near BF xx DB 03)? ===')
for m in re.finditer(re.escape(bytes([0xBF])), d):
    o = m.start()
    if o + 4 > len(d):
        continue
    addr = d[o + 1] | (d[o + 2] << 8)
    bank = d[o + 3]
    if bank == 0x03 and 0xDB00 <= addr <= 0xDBFF:
        print('   LDA $%02X:%04X,X at ROM %06X (%s)  next: %s' % (
            bank, addr, o, snes(o), ' '.join('%02X' % x for x in d[o + 4:o + 12])))