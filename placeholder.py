"""Identify the high placeholder codes (0xE2/0xEB/0xED/0xEF...) and how they are filled."""
from collections import Counter
import json
import re

d = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()
recs = json.load(open('kuniokun_text.json', encoding='utf-8'))

MAIN = 0x0193B5
c = Counter()
n = 0
for r in recs:
    if r['table_rom_off'] == MAIN:
        off = r['text_rom_off']
        c.update(d[off:off + r['nbytes']])
        n += 1
print('main table strings:', n)
print('=== full byte histogram (main table) ===')
for b in range(256):
    if c[b]:
        print('  0x%02X : %6d' % (b, c[b]))

print()
print('=== how many strings contain each high code ===')
hi = sorted(b for b in c if 0xC0 <= b <= 0xF1)
for b in hi:
    cnt = sum(1 for r in recs if r['table_rom_off'] == MAIN
              and b in d[r['text_rom_off']:r['text_rom_off'] + r['nbytes']])
    print('  0x%02X : in %d strings' % (b, cnt))

print()
print('=== search code for CMP #$E2/$EB/$ED/$EF etc ===')
for b in hi:
    pat = bytes([0xC9, b])
    hits = [m.start() for m in re.finditer(re.escape(pat), d)]
    if hits:
        print('  C9 %02X : %d hits at %s' % (b, len(hits), ' '.join('%06X' % h for h in hits[:8])))

print()
print('=== strings containing 0xE2 or 0xEB (first 20) ===')
shown = 0
for r in recs:
    if r['table_rom_off'] != MAIN:
        continue
    raw = d[r['text_rom_off']:r['text_rom_off'] + r['nbytes']]
    if 0xE2 in raw or 0xEB in raw:
        print('  [%4s] %s' % (r['index'], ' '.join('%02X' % x for x in raw[:26])))
        print('        %r' % r['text'])
        shown += 1
        if shown >= 20:
            break