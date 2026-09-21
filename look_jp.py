# -*- coding: utf-8 -*-
import kuniokun_map as km
import collections
orig = open('dl/roms/kuniokun__SF8127.smc','rb').read()
FA, FB = km.FA, km.FB

def dec(seg):
    out = []
    for b in seg:
        if b < 0xE0:
            out.append(km.CHAR.get(b, '{%02X}' % b))
        elif b == 0xF2:
            out.append('|')
        else:
            out.append('{%02X}' % b)
    return ''.join(out)

# ---- item table: pointer table at 0x01DBC3 (index0 empty), text 0x01DCA1..
ptrs = []
for i in range(0, 111):
    o = 0x01DBC3 + i*2
    p = orig[o] | (orig[o+1] << 8)
    ptrs.append(p and (0x10000 + p))
print('=== item names (%d) ===' % (len(ptrs)-1))
codes = collections.Counter()
for k, p in enumerate(ptrs[1:], 1):
    if not p: continue
    j = p
    while j < 0x01E096 and orig[j] != 0xF2:
        j += 1
    s = dec(orig[p:j])
    codes.update(b for b in orig[p:j] if b < 0xE0)
    if k <= 14 or k > len(ptrs)-4:
        print('  %3d @%06X  %s' % (k, p, s))
print('  distinct codes: %d' % len(codes))
print('  top codes: %s' % ' '.join('%s=%d' % (km.CHAR.get(c,'?'), n) for c, n in codes.most_common(20)))

# ---- name table
base = orig[0x48000] | (orig[0x48001] << 8)
print('\n=== speaker names (bank $09, base 0x%04X, 16 B entries) ===' % base)
names = []
for idn in range(0, 560):
    off = 9*0x8000 + (base + idn*16 - 0x8000)
    ent = orig[off:off+16]
    txt = []
    for b in ent[:4]:
        if b == 0x00: break
        txt.append(b)
    if not txt: continue
    names.append((idn, txt))
print('  non-empty entries in 0..559: %d' % len(names))
ncodes = collections.Counter()
seen = set()
for idn, txt in names:
    key = tuple(txt)
    if key in seen: continue
    seen.add(key)
    ncodes.update(txt)
    if len(seen) <= 30:
        print('  id %3d: %-12s %s' % (idn, ' '.join('%02X' % b for b in txt), dec(txt)))
print('  distinct entries: %d, distinct codes: %d' % (len(seen), len(ncodes)))
print('  chars: %s' % ''.join(km.CHAR.get(c,'?') for c in ncodes))
