import mos65xx
import kuniokun_map as km

o = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()

print('=== control jump table @0x01FCA8 (16 words) ===')
for k in range(16):
    v = o[0x01FCA8 + 2 * k] | (o[0x01FCA9 + 2 * k] << 8)
    print('  code $%02X -> $%04X' % (0xF0 + k, v))

print()
print('=== disasm 0x01FCC8 .. 0x01FD70 ===')
for i in mos65xx.disassemble(o[0x01FCC8:0x01FD70], address=0x01FCC8):
    print('%06X  %s' % (i.address, i.text))

print()
print('=== macro record table ROM 0x048000 (bank $09), 16 records ===')
for r in range(16):
    rec = o[0x048000 + 16 * r:0x048100 + 16 * r]
    rec = o[0x048000 + 16 * r:0x048000 + 16 * r + 16]
    dec, _ = km.decode(rec, 0, maxlen=16)
    print('  %2d: %s  | %s' % (r, rec.hex(' '), dec))