"""Dump raw bytes of extracted strings to identify the placeholder/hole codes."""
import json

d = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()
recs = json.load(open('kuniokun_text.json', encoding='utf-8'))
print('records:', len(recs))
print('keys:', list(recs[0].keys()))

for r in recs[:14]:
    off = r['text_rom_off']
    ln = min(r['nbytes'] + 2, 64)
    raw = d[off:off + ln]
    print()
    print('idx %-4s off 0x%06X nbytes %s' % (r['index'], off, r['nbytes']))
    print('   bytes: %s' % ' '.join('%02X' % b for b in raw))
    print('   text : %r' % r['text'])

# histogram of all bytes used across table 1 (the big script table)
from collections import Counter
c = Counter()
for r in recs:
    if r['table_rom_off'] == 0x0193B5:
        off = r['text_rom_off']
        c.update(d[off:off + r['nbytes']])
print()
print('=== byte histogram, main script table ===')
for b, n in sorted(c.items()):
    print('  0x%02X : %6d' % (b, n))