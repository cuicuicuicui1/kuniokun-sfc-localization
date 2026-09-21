"""Pick safe prefix codes for the Chinese 2-byte encoding.

Constraints:
  * only bytes that reach the drawer (ROM 0x01FA30, codes < $F0) matter for the
    dialogue path, plus macro-expanded bytes copied from the 16-byte record table
    at bank $09 (ROM 0x048000 + v*16).  Both macro copiers read from record
    OFFSET 0 and take at most 4 bytes (stopping at $00 for the $EC95 variant).
  * the id byte must survive the macro expander untouched -> ids must be <= $DF
    (0xE0-0xEF are macros, $F0+ are controls, $F3 ends the expansion).
"""
from collections import Counter

o = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()

# bytes that can be macro-injected: record offsets 0..3, stop at first $00
inj = Counter()
recs = 0
for base in range(0x048000, 0x058000, 16):
    rec = o[base:base + 16]
    if len(rec) < 4:
        continue
    recs += 1
    for b in rec[:4]:
        if b == 0:
            break
        inj[b] += 1

print('records scanned:', recs)
print('distinct injected code values:', len(inj))
print('injected codes sorted:', ' '.join('%02X' % c for c in sorted(inj)))

unused = [c for c in range(0x100) if c not in inj]
print()
print('codes NEVER injected (macro-safe): %d' % len(unused))
print('  ', ' '.join('%02X' % c for c in unused))

# also require: not used anywhere in the extracted original text (my encoder keeps
# a few single-byte codes; the rest are free)
import json
TR = json.load(open('cn_translation.json', encoding='utf-8'))
txtcodes = set()
for v in TR.values():
    txtcodes.add(0)  # space
for c in (0x01, 0x09, 0x0C):  # KEEP1
    txtcodes.add(c)

cand = [c for c in unused if 0xC0 <= c <= 0xDF and c not in txtcodes]
print()
print('prefix candidates in $C0-$DF, never injected:')
print('  ', ' '.join('%02X' % c for c in cand), ' -> %d pages = %d glyphs (ids 0..223)' % (len(cand), len(cand) * 224))

# sanity: does $C4 (used by the original text) get injected?
print()
print('spot check: inj[$C4] =', inj.get(0xC4, 0), ' inj[$F2] =', inj.get(0xF2, 0),
      ' inj[$F4] =', inj.get(0xF4, 0), ' inj[$E2] =', inj.get(0xE2, 0))