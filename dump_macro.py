import mos65xx

o = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()


def dis(a, b, label):
    print('=== %s: ROM 0x%06X..0x%06X ===' % (label, a, b))
    for i in mos65xx.disassemble(o[a:b], address=a):
        print('%06X  %s' % (i.address, i.text))
    print()


dis(0x01EC2D, 0x01ECF0, 'macro handlers E0..E9 (0x01EC2D..)')
dis(0x01FCA0, 0x01FDC0, 'control-code handler 0x01FC9E..')

print('=== macro jump table @0x01EC0D (16 words) ===')
for k in range(16):
    v = o[0x01EC0D + 2 * k] | (o[0x01EC0E + 2 * k] << 8)
    print('  code $%02X -> $%04X' % (0xE0 + k, v))

print()
print('=== record table bank $09 = ROM 0x048000, first 12 records x 16 B ===')
for r in range(12):
    rec = o[0x048000 + 16 * r:0x048000 + 16 * r + 16]
    print('  %2d: %s' % (r, rec.hex(' ')))