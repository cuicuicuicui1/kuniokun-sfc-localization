# -*- coding: utf-8 -*-
"""Decide the tile budget: protection set variants x {aligned pairs, consecutive pairs}."""
import kuniokun_map as km
C, FA, FB = km.CODE, km.FA, km.FB
orig = open('dl/roms/kuniokun__SF8127.smc','rb').read()

inv = {}
for code, ch in km.CODE.items():
    if len(ch) == 1:
        inv.setdefault(ch, code)
KANA = {}
for ch, code in inv.items():
    o = ord(ch)
    if 0x30A1 <= o <= 0x30F6 and chr(o - 0x60) in inv:
        KANA[code] = inv[chr(o - 0x60)]
print('katakana->hiragana code map: %d entries, e.g. %s'
      % (len(KANA), ' '.join('%02X->%02X(%s)' % (k, v, C[k]) for k, v in list(KANA.items())[:6])))

def rw(bs, on):
    return bytes(KANA.get(b, b) if on else b for b in bs)

base = set([0x00, 0x01]) | set(range(0x10, 0x20)) | {0x20, 0x72, 0x85, 0x86, 0x93}
LIT = {0x00, 0x0D, 0x21, 0x33, 0x34, 0x35}

def codes_from(region, on):
    return {b for b in rw(region, on) if 0 < b < 0xE0}

item_raw = orig[0x01DCA1:0x01E096]
names_raw = b''.join(orig[0x4802A + i*16:0x4802A + i*16 + 4] for i in range(560))
d = orig[0x00F9DB:0x00FB00]; y = 0; scr = bytearray()
while y < len(d) and d[y] != 0xFF:
    y += 2
    cnt = d[y]; y += 1
    if cnt == 0:
        continue
    n = cnt & 0x7F
    if cnt & 0x80:
        scr += d[y:y+n]
    y += n

def measure(name, on):
    codes = set([0x01, 0x09, 0x0C]) | codes_from(item_raw, on) | codes_from(bytes(names_raw), on) | codes_from(bytes(scr), on)
    prot = set(base) | set(LIT)
    for c in codes:
        prot.add(FA[c]); prot.add(FB[c])
    free = [t for t in range(256) if t not in prot]
    fs = set(free)
    al = [t for t in free if t % 2 == 0 and (t+1) in fs]
    used = set(); cons = []
    for t in free:
        if (t+1) in fs and t not in used and (t+1) not in used:
            cons.append(t); used.add(t); used.add(t+1)
    print('%-26s codes %3d  protected %3d  aligned-4 %2d  aligned-pairs %3d -> slots %2d | consecutive %3d -> slots %2d'
          % (name, len(codes), len(prot),
             sum(1 for t in range(0, 256, 4) if all((t+i) not in prot for i in range(4))),
             len(al), len(al)//2, len(cons), len(cons)//2))
    return prot

p_on = measure('katakana rewritten', True)
p_off = measure('katakana as-is', False)
print()
print('tiles freed by the rewrite: %s' % ' '.join('%02X' % t for t in sorted(p_off - p_on)))
