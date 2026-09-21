import re, sys
sys.path.insert(0, 'C:/Users/<user>/.zcode/workspace/default/sfc-recon')
import mos65xx

BASE = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/'
rom = open(BASE + 'dl/roms/kuniokun__SF8127.smc', 'rb').read()

PATTERNS = {
    'JSR $EEF5 (consumer)': bytes([0x20, 0xF5, 0xEE]),
    'JSR $FA30 (drawer)': bytes([0x20, 0x30, 0xFA]),
    'JSR $ED25 (loader)': bytes([0x20, 0x25, 0xED]),
    'JMP $EEF5': bytes([0x4C, 0xF5, 0xEE]),
    'JSL/JML $03EEF5': bytes([0x22, 0xF5, 0xEE, 0x03]),
    'REF $03E8 (abs)': bytes([0xAD, 0xE8, 0x03]),
    'REF $03E9 (abs)': bytes([0xAD, 0xE9, 0x03]),
    'REF $036F (abs)': bytes([0xAD, 0x6F, 0x03]),
    'REF $09DF (abs)': bytes([0xAD, 0xDF, 0x09]),
    'REF $0B00 (abs)': bytes([0xAD, 0x00, 0x0B]),
    'WR $0B00 (abs,X)': bytes([0x9D, 0x00, 0x0B]),
    'WR $0B00 (abs,Y)': bytes([0x99, 0x00, 0x0B]),
    'WR $2118 (DMA script)': bytes([0x8D, 0x18, 0x21]),
}

def snes(off):
    return '%02X:%04X' % (off // 0x8000, 0x8000 + off % 0x8000)

for name, pat in PATTERNS.items():
    hits = [m.start() for m in re.finditer(re.escape(pat), rom)]
    print('%-24s %3d hits: %s' % (name, len(hits), ' '.join(snes(h) for h in hits[:24])))
print()

# disassemble the region around the consumer and its neighbours
for base, ln, label in [(0x01EE80, 0x120, 'consumer 0x01EEF5 area'),
                        (0x01EDD0, 0x120, 'driver? 0x01EDD0'),
                        (0x01EF60, 0x120, 'after consumer')]:
    print('=== %s (%s) ===' % (label, snes(base)))
    buf = rom[base:base + ln]
    for ins in mos65xx.disassemble(buf, address=0x8000 + (base % 0x8000)):
        print('  %04X: %-22s %s' % (ins.address, ins.text, ins.mode))
    print()