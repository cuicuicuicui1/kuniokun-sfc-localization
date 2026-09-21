import re, sys
sys.path.insert(0, 'C:/Users/<user>/.zcode/workspace/default/sfc-recon')
import mos65xx

BASE = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/'
rom = open(BASE + 'dl/roms/kuniokun__SF8127.smc', 'rb').read()

def snes(off):
    return '%02X:%04X' % (off // 0x8000, 0x8000 + off % 0x8000)

# bank $03 text/engine region: who calls the engine entry points?
for tgt, label in [(0xEEED, 'consumer entry'), (0xEEE5, 'EEE5'), (0xEF2B, 'EF2B'),
                   (0xEB2F, 'EB2F'), (0xFCC8, 'FCC8 msg start'), (0xFA0B, 'FA0B'),
                   (0xF9D4, 'F9D4 script interp'), (0xE970, 'E970 (my sanitize!)')]:
    pat = bytes([0x20, tgt & 0xFF, tgt >> 8])
    hits = [m.start() for m in re.finditer(re.escape(pat), rom)]
    print('JSR %-16s (%s): %d hits %s' % (label, snes(tgt + 0x018000), len(hits),
                                          ' '.join(snes(h) for h in hits)))

print()
# also JSL/JML forms
for tgt, label in [(0xEEED, 'consumer'), (0xEEF5, 'consumer2')]:
    for op, nm in [(0x22, 'JSL'), (0x5C, 'JML')]:
        pat = bytes([op, tgt & 0xFF, tgt >> 8, 0x03])
        hits = [m.start() for m in re.finditer(re.escape(pat), rom)]
        if hits:
            print('%s $03:%04X %s: %s' % (nm, tgt, label, ' '.join(snes(h) for h in hits)))

print()
for base, ln in [(0x01E982, 0x60), (0x01EA00, 0x60), (0x01EF0D, 0x70), (0x01EB10, 0x50)]:
    print('=== %s ===' % snes(base))
    for ins in mos65xx.disassemble(rom[base:base + ln], address=0x8000 + (base % 0x8000)):
        print('  %04X: %-24s %s' % (ins.address, ins.text, ins.mode))
    print()