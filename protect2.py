import json, kuniokun_map as km

orig = open('dl/roms/kuniokun__SF8127.smc','rb').read()
FA, FB = km.FA, km.FB
def rom_of(bank9off):
    return (9 * 0x8000) + (bank9off - 0x8000)          # LoROM bank $09
base = orig[0x48000] | (orig[0x48001] << 8)
print('name table base word $09:8000 = 0x%04X' % base)
def entry_codes(idn):
    r = orig[rom_of(base + idn*16): rom_of(base + idn*16) + 16]
    out = []
    for b in r[:4]:
        if b == 0x00:
            break
        out.append(b)
    return out
good = []
for idn in range(0, 800):
    cs = entry_codes(idn)
    if cs and all(c < 0xE0 for c in cs):
        good.append((idn, cs))
name_codes = set(c for _, cs in good for c in cs)
print('plausible name entries: %d ; distinct codes %d' % (len(good), len(name_codes)))
for idn, cs in good[:10] + good[-10:]:
    print('   id %3d: %-14s' % (idn, ' '.join('%02X' % c for c in cs)))

item = set(b for b in orig[0x01DCA1:0x01E096] if b < 0xF0 and b != 0x00)
print('item region distinct codes: %d' % len(item))
def tiles_of(codes):
    t = {0x00, 0x01} | set(range(0x10, 0x20)) | {0x20, 0x72, 0x85, 0x86, 0x93}
    for c in codes:
        t.add(FA[c]); t.add(FB[c])
    return t
for label, cs in (('item only', item), ('name only', name_codes), ('item+name', item | name_codes)):
    t = tiles_of(cs)
    pairs = [p for p in range(128) if 2*p not in t and 2*p+1 not in t]
    print('%-10s -> %3d protected tiles, %3d free pairs, %3d slots' % (label, len(t), len(pairs), len(pairs)//2))
# how many of my translated characters can be reused for free (code already protected)?
tr = json.load(open('cn_translation.json'))
chars = set(''.join(tr.values()).replace('{', ' ').split())
chars = set(c for s in tr.values() for c in s if c not in '{}' and not c.isascii())
import re
chars = set()
for s in tr.values():
    for c in re.sub(r'\{[0-9A-Fa-f]{2,4}\}', '', s):
        chars.add(c)
print('distinct non-ascii chars in my translation:', len(chars))
rev = {}
for code, ch in getattr(km, 'CODE', {}).items():
    rev.setdefault(ch, code)
free = sorted(c for c in chars if rev.get(c, 0xFFFF) in tiles_of(item | name_codes) and rev.get(c) is not None)
hmm = sorted(c for c in chars if rev.get(c) is not None and rev.get(c) < 0xE0)
print('chars with an original code (could be KEEP1):', len(hmm))
print('  of which already protected (free):', len(free))
print('  ' + ''.join(free))
print('  expensive ones: ' + ''.join(c for c in hmm if c not in free))
