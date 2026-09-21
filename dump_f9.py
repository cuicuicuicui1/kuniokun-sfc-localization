import mos65xx

o = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()

print('=== disasm ROM 0x00F980 .. 0x00FA30 ===')
for i in mos65xx.disassemble(o[0x00F980:0x00FA30], address=0x00F980):
    print('%06X  %s' % (i.address, i.text))

print()
print('=== hex 0x00F9A0 .. 0x00F9E0 ===')
for r in range(0x00F9A0, 0x00F9E0, 16):
    print('%06X  %s' % (r, o[r:r + 16].hex(' ')))

print()
print('=== callers of this routine region: search for JSR/JMP to 0xF96x..0xF9Dx ===')
import re
for tgt in (0xF969, 0xF970, 0xF980, 0xF990, 0xF9A0, 0xF9B0, 0xF9C0, 0xF9D0):
    pat = bytes([0x20, tgt & 0xFF, tgt >> 8])
    hits = [hex(m.start()) for m in re.finditer(re.escape(pat), o)]
    pat2 = bytes([0x4C, tgt & 0xFF, tgt >> 8])
    hits2 = [hex(m.start()) for m in re.finditer(re.escape(pat2), o)]
    print('  JSR $%04X -> %s   JMP -> %s' % (tgt, hits, hits2))