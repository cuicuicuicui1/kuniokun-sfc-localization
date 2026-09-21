"""Derive the original font's byte codes from the 1013 known text pairs.

Each entry has its original Japanese string and the raw bytes it was read from,
so aligning the two gives the code for every kana / symbol character.
"""
import json, io, re, sys

rom = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()
jp = json.load(io.open('kuniokun_text.json', encoding='utf-8'))
MAC = re.compile(r'\{[^}]*\}')
table = {}
conflicts = {}

for e in jp:
    off, txt = e['text_rom_off'], e['text']
    raw = rom[off:off + e['nbytes']]
    parts = []
    pos = 0
    for m in MAC.finditer(txt):
        parts.append(('lit', txt[pos:m.start()]))
        parts.append(('mac', m.group(0)))
        pos = m.end()
    parts.append(('lit', txt[pos:]))
    i = 0
    for kind, s in parts:
        if kind == 'mac':
            # a macro is one byte in the stream for $E0-$EF, two for the F-codes
            if s in ('{F2F3}', '{F2F4}', '{F2F6}'):
                i += 2
            else:
                i += 1
            continue
        for ch in s:
            if ch == '\u3000':
                ch = ' '
            n = 2 if ord(ch) > 0x2000 and not (0x3040 <= ord(ch) <= 0x30FF) else 1
            if n == 2:
                w = raw[i] | (raw[i + 1] << 8)
                key = ('w', w)
            else:
                key = ('b', raw[i])
            prev = table.get(key)
            if prev is None:
                table[key] = ch
            elif prev != ch:
                conflicts.setdefault(key, set()).update((prev, ch))
            i += n
single = {k[1]: v for k, v in table.items() if k[0] == 'b'}
double = {k[1]: v for k, v in table.items() if k[0] == 'w'}
print('single-byte codes: %d   two-byte codes: %d   conflicts: %d'
      % (len(single), len(double), len(conflicts)))
for k in list(conflicts)[:10]:
    print('   conflict', k, conflicts[k])
if len(sys.argv) > 1 and sys.argv[1] == 'dump':
    for c in sorted(single):
        print('  %02X = %s' % (c, single[c]))
