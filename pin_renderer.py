"""Pin down the text renderer's exact bytes/entry, and bank $03 free space."""
import mos65xx

d = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()


def snes(off):
    return '$%02X:%04X' % (off // 0x8000, 0x8000 + (off % 0x8000))


def dump(a, b):
    print('=== ROM 0x%06X-0x%06X (SNES %s) ===' % (a, b, snes(a)))
    i = a
    while i < b:
        print('%06X %-9s: %s' % (i, snes(i), ' '.join('%02X' % x for x in d[i:i + 16])))
        i += 16


def dis(a, b, base=None):
    base = base if base is not None else 0x8000 + a % 0x8000
    print('--- disasm 0x%06X (addr base %04X) ---' % (a, base))
    try:
        ins = mos65xx.disassemble(d[a:b], offset=a, address=base)
    except Exception as e:
        print('err', e)
        return
    for x in ins:
        print('  %06X %04X: %-22s %s' % (x.offset, x.address, x.text, x.mode))


# main renderer entry area
dump(0x00FC50, 0x00FD20)
dis(0x00FC6E, 0x00FD20, 0xFC6E)

# the JSR $F969 helper
print()
dump(0x00F960, 0x00F990)
dis(0x00F969, 0x00F990, 0xF969)

# bank $03 layout: free-space scan
print()
print('=== bank $03 (ROM 0x18000-0x1FFFF) free runs ===')
lo, hi = 0x18000, 0x20000
RUNCH = {0x00: 'zero', 0xFF: 'ff'}
i = lo
while i < hi:
    b = d[i]
    if b in RUNCH:
        j = i
        while j < hi and d[j] == b:
            j += 1
        if j - i >= 64:
            print('  %s run %06X-%06X  (%d bytes)' % (RUNCH[b], i, j - 1, j - i))
        i = j
    else:
        i += 1

print()
print('=== whole-ROM free runs >= 512 bytes (for placement) ===')
i = 0
n = len(d)
while i < n:
    b = d[i]
    if b in (0x00, 0xFF):
        j = i
        while j < n and d[j] == b:
            j += 1
        if j - i >= 512:
            print('  %s run %06X-%06X  (%d bytes)' % (RUNCH[b], i, j - 1, j - i))
        i = j
    else:
        i += 1