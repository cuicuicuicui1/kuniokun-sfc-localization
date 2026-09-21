"""Check whether the Chinese prefix range $F8-$FF is safe.

The dialogue pipeline copies bytes from a 16-byte-record table at bank $09
(ROM 0x048000) into the message buffer; whatever reaches the consumer at
ROM 0x01EEF5 is interpreted as a character or control code.  If a record byte is
>= $F8 the original engine ignores it (jump table $F8-$FF -> CLC no-op), but my
patch turns $F8-$FF into a 2-byte Chinese code, so such bytes must be sanitized.
"""
from collections import Counter

o = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()

for lo, hi, tag in [(0x048000, 0x050000, 'bank $09 record table (32K)'),
                    (0x050000, 0x058000, 'next 32K')]:
    reg = o[lo:hi]
    print('=== %s  ROM 0x%06X..0x%06X ===' % (tag, lo, hi))
    print('  zero bytes     :', reg.count(0))
    # last non-zero offset -> real extent of the table
    last = max(i for i, b in enumerate(reg) if b) if any(reg) else -1
    print('  last non-zero  : +0x%X (record %d)' % (last, last // 16))
    hi8 = [i for i, b in enumerate(reg) if b >= 0xF8]
    f2 = [i for i, b in enumerate(reg) if b == 0xF2]
    print('  bytes >= $F8   : %d' % len(hi8), ['+%X(=rec %d:%d)' % (i, i // 16, i % 16) for i in hi8[:20]])
    print('  byte  == $F2   : %d' % len(f2), ['+%X(=rec %d:%d)' % (i, i // 16, i % 16) for i in f2[:20]])
    c = Counter(reg)
    print('  top byte values:', c.most_common(8))
    print()

print('=== full-message byte census (my 1013 original strings) ===')
import json
tr = json.load(open('cn_translation.json', encoding='utf-8'))
print('translated strings:', len(tr))
print('(codes $F8+ in my own encoded text are intentional)')