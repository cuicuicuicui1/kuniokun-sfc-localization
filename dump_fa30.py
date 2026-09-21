import mos65xx
import re

o = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()

print('--- ROM 0x01F9E0 .. 0x01FB00 ---')
for i in mos65xx.disassemble(o[0x01F9E0:0x01FB00], address=0x01F9E0):
    print('%06X  %s' % (i.address, i.text))

print()
print('--- hex of 0x01FA20..0x01FA9E ---')
for r in range(0x01FA20, 0x01FA9E, 16):
    print('%06X  %s' % (r, o[r:r + 16].hex(' ')))

pats = [(b'\xbf\x9e\xfa\x03', 'LDA $03FA9E,X'),
        (b'\xbf\x9e\xfb\x03', 'LDA $03FB9E,X'),
        (b'\x20\x30\xfa', 'JSR $FA30 (bank 3 -> ROM 0x01FA30)'),
        (b'\x20\x75\xfc', 'JSR $FC75 (bank 1 -> ROM 0x00FC75)'),
        (b'\x20\x77\xfc', 'JSR $FC77'),
        (b'\x22\x30\xfa\x03', 'JSL $03FA30')]
print()
for pat, name in pats:
    print(name, [hex(m.start()) for m in re.finditer(re.escape(pat), o)])