"""Find the macro dispatch table: which $E0-$EF byte calls which handler."""
import re

data = open('C:/Users/<user>/.zcode/workspace/default/sfc-recon/work_kuniokun_2mb.smc', 'rb').read()
targets = {0xEDAE: 'tableA($035A)', 0xEDC5: 'tableB($035C)', 0xEE05: 'tableC($035D/$035E)',
           0xEE21: 'decimal($035F/$0360)', 0xEE5B: 'copy', 0xED43: 'load6($0359)',
           0xED25: 'copy-until-F2', 0xEDDC: 'copy-ptr-until-F2'}

print('=== 16 bit code-address occurrences of the handlers ===')
for addr, name in targets.items():
    pat = bytes([addr & 0xFF, addr >> 8])
    hits = [m.start() for m in re.finditer(re.escape(pat), data)]
    shown = []
    for h in hits:
        bank, off = h // 0x8000, 0x8000 + (h % 0x8000)
        shown.append('%02X:%04X' % (bank, off))
    print('$%04X %-24s %d hits: %s' % (addr, name, len(hits), ' '.join(shown[:14])))

print()
print('=== window around $03:EB00-$03:EC00 (macro dispatch?) ===')
base = 0x03 * 0x8000
print(data[base + 0x6B00:base + 0x6C00].hex(' '))
print()
print('=== window around $03:EEDA-$03:EF10 (message start) ===')
print(data[base + 0x6EDA:base + 0x6F20].hex(' '))