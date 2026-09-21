"""Check the killer structural hypothesis: does every entry's translated text carry its OWN
$F2 terminator inside its own slot, or does it run past its slot into the next entry
(which would make the game render "chinese prefix + japanese tail")?

usage: python check_term.py <rom>
"""
import json
import sys

ROM = sys.argv[1] if len(sys.argv) > 1 else 'kuniokun_cn.smc'
ORIG = 'dl/roms/kuniokun__SF8127.smc'
d = open(ROM, 'rb').read()
o = open(ORIG, 'rb').read()
tr = json.load(open('cn_translation.json', encoding='utf-8'))

# the entry offsets we know about, sorted; plus the slot end = next entry start
offs = sorted(int(k, 16) for k in tr)
SLOT_END = {}
for i, off in enumerate(offs):
    SLOT_END[off] = offs[i + 1] if i + 1 < len(offs) else 0x01E982

over = []
noTerm = []
for off in offs:
    end = SLOT_END[off]
    try:
        p = d.index(b'\xF2', off)
    except ValueError:
        noTerm.append((off, end))
        continue
    if p >= end:
        over.append((off, end, p))
    # also: original slot length vs mine
print('rom %s: entries=%d, running past own slot=%d, no F2 at all=%d' % (ROM, len(offs), len(over), len(noTerm)))
for off, end, p in over[:40]:
    slot_len = end - off
    my = d[off:p]
    orig = o[off:o.index(b'\xF2', off)]
    print('  %06X slot=%3d mytext=%3d (F2 at +%d)  mine=%s  orig=%s' % (
        off, slot_len, p - off, p - off, my.hex(), orig.hex()))
if noTerm:
    print('  no terminator:', [(hex(a), hex(b)) for a, b in noTerm[:10]])