# -*- coding: utf-8 -*-
"""Same as kana16 but with the katakana->hiragana rewrite applied to BOTH the
item table and the bank-$09 name entries (the game then really shows hiragana)."""
import collections
import kuniokun_map as km
C, FA, FB = km.CODE, km.FA, km.FB
orig = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()
BASE_T = {0x00, 0x01} | set(range(0x10, 0x20)) | {0x20, 0x72, 0x85, 0x86, 0x93}

def is_kata(ch):
    return len(ch) == 1 and u'\u30a1' <= ch <= u'\u30f6'
def kata_to_hira(ch):
    return chr(ord(ch) - 0x60)
char2code = {}
for code, ch in C.items():
    if 0 <= code < 0xE0:
        char2code.setdefault(ch, code)

def transform(code):
    """katakana code -> hiragana code (if the hiragana exists)."""
    ch = C.get(code)
    if ch and is_kata(ch):
        h = char2code.get(kata_to_hira(ch))
        if h is not None:
            return h
    return code

def tiles_of(codes):
    t = set(BASE_T)
    for c in codes:
        t.add(FA[c]); t.add(FB[c])
    return t
def pairs_of(t):
    return [p for p in range(128) if 2*p not in t and 2*p+1 not in t]
def report(label, cs):
    t = tiles_of(cs)
    pr = pairs_of(t)
    print('%-34s protected %3d tiles -> %3d pairs -> %2d slots' % (label, len(t), len(pr), len(pr)//2))
    return len(pr)//2

# ---- item table
raw_item, hira_item, changed = set(), set(), 0
o = 0x01DBC3
for i in range(1, 111):
    p = orig[o+i*2] | (orig[o+i*2+1] << 8)
    if not p:
        continue
    j = 0x10000 + p
    while j < 0x01E096 and orig[j] != 0xF2:
        b = orig[j]
        if b < 0xE0:
            raw_item.add(b)
            t = transform(b)
            if t != b:
                changed += 1
            hira_item.add(t)
        j += 1
print('item table: %d codes, %d of them katakana (rewritten)' % (len(raw_item), changed))

# ---- name table, whole plausible span
base = orig[0x48000] | (orig[0x48001] << 8)
raw_name, hira_name = set(), set()
nchg, entries = 0, 0
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
    entries += 1
    for b in txt:
        raw_name.add(b)
        t = transform(b)
        if t != b:
            nchg += 1
        hira_name.add(t)
print('name table: %d entries, %d codes, %d katakana rewritten' % (entries, len(raw_name), nchg))

report('items raw', raw_item)
report('items kata->hira', hira_item)
report('names raw', raw_name)
report('names kata->hira', hira_name)
report('items+names kata->hira', hira_item | hira_name)
