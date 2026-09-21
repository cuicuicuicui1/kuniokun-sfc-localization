"""Gather the facts needed before moving the Chinese glyphs from 8x16 to 16x16:

1. the speaker-name tables ($03:EAEF/$EAF1/$EAF3) -> how long a name can be, and
   whether any name byte falls into the Chinese prefix range (0xC5..)
2. how many distinct Chinese glyphs a single message needs (the true colouring
   window now that each glyph costs two tile pairs instead of one)
3. worst case line width in *units* (a 16 pixel glyph costs 2 units)
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
ROM = BASE + '/work_kuniokun_2mb.smc'
data = open(ROM, 'rb').read()
PREFIX0 = 0xC5


def ries(off, n):
    return data[off:off + n].hex(' ')


def snes(off):
    return '%02X:%04X' % (0x03, 0x8000 + (off & 0x7FFF))


def read_ptr(off):
    """2 byte pointer stored as (low, high) in bank $03."""
    lo, hi = data[off], data[off + 1]
    return 0x8000 + ((hi << 8 | lo) & 0x7FFF)


def dump_str(off, limit=64):
    out = []
    i = 0
    while i < limit and data[off + i] != 0xF2:
        out.append(data[off + i])
        i += 1
    return out


def name_tables():
    res = {}
    for lab, base_off in (('A', 0x01EAEF), ('B', 0x01EAF1), ('C', 0x01EAF3)):
        arr = read_ptr(base_off)
        arr_rom = arr - 0x8000 + 0x03 * 0x8000
        entries = []
        for i in range(24):
            p = data[arr_rom + 2 * i] | (data[arr_rom + 2 * i + 1] << 8)
            if p == 0:
                break
            s_rom = (p & 0x7FFF) + 0x03 * 0x8000
            entries.append((i, p, dump_str(s_rom)))
        res[lab] = (arr, arr_rom, entries)
    return res


print('=== speaker name tables (bank $03 loader at $EDAE/$EDC5/$EE05) ===')
worst = 0
bad_bytes = set()
for lab, (arr, arr_rom, entries) in name_tables().items():
    print('table %s: pointer array at $%04X (ROM 0x%06X), %d entries'
          % (lab, arr, arr_rom, len(entries)))
    for i, p, s in entries:
        vals = [v for v in s]
        worst = max(worst, len(vals))
        for v in vals:
            if v >= PREFIX0:
                bad_bytes.add(v)
        txt = ''.join(chr(v) if 0x20 < v < 0x7F else '.' for v in vals)
        print('   [%2d] $%04X len %2d  %-24s  %s' % (i, p, len(vals), txt,
                                                      ' '.join('%02X' % v for v in vals)))
print('longest name: %d units; name bytes >= $%02X: %s'
      % (worst, PREFIX0, sorted('%02X' % v for v in bad_bytes) or 'none'))

print()
print('=== per message distinct glyph demand ===')
tr = json.load(open(BASE + '/cn_translation.json', encoding='utf-8'))
recs = json.load(open(BASE + '/kuniokun_text.json', encoding='utf-8'))
keep1 = json.load(open(BASE + '/cn_build_params.json', encoding='utf-8'))['keep1']
KEEP1 = {k: int(v) for k, v in keep1.items()}
import re
TOKEN = re.compile(r'\{([0-9A-Fa-f]{2,4})\}')
print('keep1 codes: %s' % ' '.join('%s=%02X' % (k, v) for k, v in sorted(KEEP1.items())))
bad_keep = [k for k, v in KEEP1.items() if v >= PREFIX0]
print('keep1 codes inside the prefix range: %s' % (bad_keep or 'none'))

per_table = {}
for r in recs:
    per_table.setdefault(r['table_rom_off'], []).append(r)

for tab, rs in sorted(per_table.items()):
    rs.sort(key=lambda r: r['index'])
    worst_g = 0
    worst_u = 0
    worst_key = None
    for r in rs:
        s = tr['%06X' % r['text_rom_off']]
        chars = [c for c in re.sub(TOKEN, '', s)]
        g = set(c for c in chars if c != ' ' and c not in KEEP1)
        units = sum(2 if (c != ' ' and c not in KEEP1) else 1 for c in chars)
        if len(g) > worst_g:
            worst_g, worst_key = len(g), '%06X' % r['text_rom_off']
        worst_u = max(worst_u, units)
        if len(g) > 43:
            print('   !! %s needs %d distinct glyphs: %s' % (worst_key, len(g), s[:60]))
    print('table 0x%06X (%d entries): max %d distinct glyphs (entry %s), '
          'max %d units in one entry (%d cells + name budget)'
          % (tab, len(rs), worst_g, worst_key, worst_u, worst_u))