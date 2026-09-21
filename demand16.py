# -*- coding: utf-8 -*-
"""How many CN slots would the *correct* protection set leave, and is that enough?

The box is wiped per message, so one message is on screen at a time: characters
that co-occur in one entry need different slots.  Protection must cover every
code the ORIGINAL drawer can still be asked to draw:
  * the untranslated item table (its window is drawn by the original renderer)
  * the speaker-name table in bank $09 (copied into the buffer by the {E2} macro)
  * digits/space/decor (hard-coded base set)
"""
import json, re, sys
import kuniokun_map as km
import cnbuild5 as cb

orig = open(cb.BASE + '/dl/roms/kuniokun__SF8127.smc', 'rb').read()
FA, FB = km.FA, km.FB
BASE_T = {0x00, 0x01} | set(range(0x10, 0x20)) | {0x20, 0x72, 0x85, 0x86, 0x93}

base_word = orig[0x48000] | (orig[0x48001] << 8)
name_codes = set()
for idn in range(0, 800):
    off = 9*0x8000 + (base_word + idn*16 - 0x8000)
    for b in orig[off:off+4]:
        if b == 0x00:
            break
        if b < 0xE0:
            name_codes.add(b)
item_codes = set(b for b in orig[0x01DCA1:0x01E096] if b < 0xF0 and b != 0x00)

def tiles_of(codes):
    t = set(BASE_T)
    for c in codes:
        t.add(FA[c]); t.add(FB[c])
    return t

rev = {}
for code, ch in km.CODE.items():
    if 0 <= code < 0xE0:
        rev.setdefault(ch, code)

def report(label, codes):
    t = tiles_of(codes)
    pairs = [p for p in range(128) if 2*p not in t and 2*p+1 not in t]
    print('%-22s protected %3d tiles -> %3d free pairs -> %2d slots' % (label, len(t), len(pairs), len(pairs)//2))
    return t, len(pairs)//2

report('base only', set())
tA, sA = report('base+items', item_codes)
tB, sB = report('base+names', name_codes)
tC, sC = report('base+items+names', item_codes | name_codes)

# ---------- text pipeline identical to main()
tr = json.load(open(cb.BASE + '/cn_translation.json', encoding='utf-8'))
textrecs = json.load(open(cb.BASE + '/kuniokun_text.json', encoding='utf-8'))
orig_text = {'%06X' % r['text_rom_off']: r['text'] for r in textrecs}
tbl_of = {'%06X' % r['text_rom_off']: r['table_rom_off'] for r in textrecs}

def windows_with(tiles, keep_extra=()):
    cb.derive_keep1.__globals__  # noqa
    keep = {}
    for ch, code in rev.items():
        if FA[code] in tiles and FB[code] in tiles:
            keep[ch] = code
    for ch in keep_extra:
        keep.setdefault(ch, rev[ch])
    saved = dict(cb.KEEP1)
    cb.KEEP1.clear(); cb.KEEP1.update(keep)
    fixed = {}
    for k, v in tr.items():
        if tbl_of.get(k) in cb.NO_TRANSLATE:
            continue
        fixed[k] = cb.align_tokens(orig_text[k], v)
    per_table = {}
    for ti, (table_off, count) in enumerate(cb.TABLES):
        recs = sorted([r for r in textrecs if r['table_rom_off'] == table_off], key=lambda r: r['index'])
        per_table[ti] = [] if table_off in cb.NO_TRANSLATE else [cb.glyphs_of(fixed['%06X' % r['text_rom_off']]) for r in recs]
    cb.KEEP1.clear(); cb.KEEP1.update(saved)
    w1, w10 = [], []
    for ti, gs in per_table.items():
        win = 1 if ti == 0 else 10
        for i in range(len(gs)):
            u = set()
            for j in range(i, min(i + win, len(gs))):
                u |= gs[j]
            (w1 if ti == 0 else w10).append(u)
    allw = w1 + w10
    return keep, per_table, max(len(w) for w in allw), sorted((len(w), i) for i, w in enumerate(allw))[-5:]

for label, tiles, slots in (('base+items', tA, sA), ('base+items+names', tC, sC)):
    keep, per_table, mx, top = windows_with(tiles)
    print('\n%s: KEEP1 would be %d chars -> %d slots' % (label, len(keep), slots))
    print('   max window (chars co-occurring in one entry) = %d  (top5 %s)' % (mx, top))
    print('   main-table worst entries: %s' % sorted((len(set(g)), i) for i, g in enumerate(per_table[0]))[-4:])
