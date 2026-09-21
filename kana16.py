# -*- coding: utf-8 -*-
"""Can the font window hold 16x16 CN glyphs AND the original kana the game still draws?

The resident Japanese text (item window + speaker names) is pure kana, so it only
needs the kana tiles.  Katakana in the item table can be rewritten to hiragana
(same sound, no meaning change) which frees the katakana tiles.
"""
import collections
import kuniokun_map as km

C, FA, FB = km.CODE, km.FA, km.FB
orig = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()
BASE_T = {0x00, 0x01} | set(range(0x10, 0x20)) | {0x20, 0x72, 0x85, 0x86, 0x93}

print('hiragana codes:', min(x for x, ch in C.items() if ch in km.HIRA) if hasattr(km, 'HIRA') else '?')
# code ranges by script
def script_of(code):
    ch = C.get(code)
    if not ch or len(ch) != 1:
        return 'other'
    if ch in 'ぁあぃいぅうぇえぉおかがきぎくぐけげこごさざしじすずせぜそぞただちぢっつづてでとどなにぬねのはばぱひびぴふぶぷへべぺほぼぽまみむめもゃやゅゆょよらりるれろゎわゐゑをん':
        return 'hira'
    if ch in 'ァアィイゥウェエォオカガキギクグケゲコゴサザシジスズセゼソゾタダチヂッツヅテデトドナニヌネノハバパヒビピフブプヘベペホボポマミムメモャヤュユョヨラリルレロヮワヰヱヲンヴ':
        return 'kata'
    return 'other'

def tiles_of(codes):
    t = set(BASE_T)
    for c in codes:
        t.add(FA[c]); t.add(FB[c])
    return t

def pairs_of(t):
    return [p for p in range(128) if 2*p not in t and 2*p+1 not in t]

# ---------------- item table
item_codes = collected = set()
o = 0x01DBC3
for i in range(1, 111):
    p = orig[o+i*2] | (orig[o+i*2+1] << 8)
    if not p:
        continue
    j = 0x10000 + p
    while j < 0x01E096 and orig[j] != 0xF2:
        if orig[j] < 0xE0:
            collected.add(orig[j])
        j += 1
item_scripts = collections.Counter(script_of(c) for c in collected)
print('items: %d codes  %s' % (len(collected), dict(item_scripts)))
item_hira = set(c for c in collected if script_of(c) != 'kata')   # after katakana->hiragana rewrite

# ---------------- name table
base = orig[0x48000] | (orig[0x48001] << 8)
name_all, name_real = set(), set()
for idn in range(0, 560):
    off = 9*0x8000 + (base + idn*16 - 0x8000)
    ent = orig[off:off+16]
    txt = []
    for b in ent[:4]:
        if b == 0x00:
            break
        txt.append(b)
    if not txt:
        continue
    name_all.update(txt)
    if all(script_of(b) == 'hira' for b in txt):
        name_real.update(txt)
print('names: %d codes (any) / %d codes (hiragana-only entries)' % (len(name_all), len(name_real)))
print('  scripts any:', dict(collections.Counter(script_of(c) for c in name_all)))

for label, cs in (('items(any script)', collected),
                  ('items after kata->hira', item_hira),
                  ('names hira only', name_real),
                  ('items+hira names', item_hira | name_real),
                  ('items(any)+names(any)', collected | name_all),
                  ('kata->hira items + names(any)', item_hira | name_all)):
    t = tiles_of(cs)
    pr = pairs_of(t)
    print('%-28s protected %3d tiles -> %3d free pairs -> %2d slots' % (label, len(t), len(pr), len(pr)//2))
