"""Rewrite verify18's command-window section for the hooked design."""
import io

p = 'verify18.py'
s = io.open(p, encoding='utf-8').read()

start = s.index("print('J  command window labels')")
end = s.index("print()\nprint('K  a pasted name gets one pair per glyph")

NEW = r'''print('J  command window labels')
chars = []
for _r, _c, txt in cb.CMDWIN_LABELS:
    for ch in txt:
        if ch not in chars:
            chars.append(ch)
need = len(chars) * 2
codes = cb.CMDWIN_CODES[:need]
n_entries = (cb.SLOTS + cb.LABEL_GLYPHS * cb.LABEL_SETS
             + cb.LABEL_NAME_GLYPHS * cb.LABEL_NAME_SETS)

# (a) only the borrowed codes may differ from the original FA/FB
ofa = orig[km.FA_OFF:km.FA_OFF + 256]
ofb = orig[km.FB_OFF:km.FB_OFF + 256]
nfa = rom[km.FA_OFF:km.FA_OFF + 256]
nfb = rom[km.FB_OFF:km.FB_OFF + 256]
for c in range(256):
    if (nfa[c], nfb[c]) != (ofa[c], ofb[c]) and c not in codes:
        fail('J code $%02X: FA/FB changed but it was not borrowed' % c)
print('   FA/FB changed only for the %d borrowed codes' % len(codes))

# (b) each borrowed code points at the borrowed slot entry's tiles, upper and
#     lower, and those two tiles are consecutive as the pair promises
bad = 0
for i, ch in enumerate(chars):
    e = i
    pa = rom[cb.E3_SLOTPAIR + e]
    pb = rom[cb.E3_SLOTPAIR + n_entries + e]
    ca, cb_ = codes[2 * i], codes[2 * i + 1]
    if (nfb[ca], nfa[ca]) != (pa, pa + 1):
        fail('J %r left half: FB/FA = %d/%d want %d/%d'
             % (ch, nfb[ca], nfa[ca], pa, pa + 1))
        bad += 1
    if (nfb[cb_], nfa[cb_]) != (pb, pb + 1):
        fail('J %r right half: FB/FA = %d/%d want %d/%d'
             % (ch, nfb[cb_], nfa[cb_], pb, pb + 1))
        bad += 1
if not bad:
    print('   %d hanzi resolve to the borrowed entries\' four tiles' % len(chars))

# (c) the staged queue entries: header points at those same tiles and the payload
#     is the glyph's half, in the order the window's two passes write them
from sfc_tools import pack_8x8
blob = rom[cb.CMDWIN_BLOB_ROM:cb.CMDWIN_BLOB_ROM + len(chars) * 72]
bad = 0
for i, ch in enumerate(chars):
    e = i
    pa = rom[cb.E3_SLOTPAIR + e]
    pb = rom[cb.E3_SLOTPAIR + n_entries + e]
    g = cnglyph.render16x16(ch)
    halves = (pack_8x8([r[:8] for r in g[:8]]) + pack_8x8([r[:8] for r in g[8:]]),
              pack_8x8([r[8:] for r in g[:8]]) + pack_8x8([r[8:] for r in g[8:]]))
    for k, (tile, data) in enumerate(((pa, halves[0]), (pb, halves[1]))):
        ent = blob[i * 72 + k * 36:i * 72 + k * 36 + 36]
        vm = 0x6000 + tile * 8
        want = bytes([vm & 0xFF, vm >> 8, 0x80, 0x20]) + data
        if ent != want:
            fail('J %r entry %d: does not stage the right half to tile %d'
                 % (ch, k, tile))
            bad += 1
if not bad:
    print('   %d staged queue entries carry the right half to the right tile'
          % (len(chars) * 2))

# (d) the hook is planted where the open routine sets up, and jumps into our bank
site = rom[cb.CMDWIN_HOOK_SITE:cb.CMDWIN_HOOK_SITE + 6]
if site[:1] != bytes([0x5C]):
    fail('J the hook site holds %s, not a JML' % site.hex(' '))
else:
    bk, ad = site[3], site[1] | (site[2] << 8)
    want_bk, want_ad = cb.snes_of_rom(cb.CMDWIN_HOOK_ROM)
    if (bk, ad) != (want_bk, want_ad):
        fail('J the hook jumps to $%02X:%04X, want $%02X:%04X'
             % (bk, ad, want_bk, want_ad))
    elif site[4:6] != bytes([0xEA, 0xEA]):
        fail('J the two leftover bytes are %s, want NOPs' % site[4:6].hex(' '))
    else:
        print('   JML planted at $%06X -> $%02X:%04X, leftovers NOPped'
              % (cb.CMDWIN_HOOK_SITE, bk, ad))

# (e) the table: only borrowed codes and spaces, labels where the layout says
tbl = rom[cb.CMDWIN_ROM:cb.CMDWIN_ROM + cb.CMDWIN_ROW * 2]
for row, cell, txt in cb.CMDWIN_LABELS:
    q = row * cb.CMDWIN_ROW + cell
    for ch in txt:
        ca, cb_ = codes[2 * chars.index(ch)], codes[2 * chars.index(ch) + 1]
        if tbl[q] != ca or tbl[q + 1] != cb_:
            fail('J table cell %d: %02X %02X want %02X %02X'
                 % (q, tbl[q], tbl[q + 1], ca, cb_))
        q += 2
outside = [b for b in tbl if b != 0 and b not in codes]
if outside:
    fail('J the table holds bytes that are not borrowed codes: %s' % outside)
if not fails:
    print('   5 labels placed in the 26x2 cell table, nothing else changed')

'''

s = s[:start] + NEW + s[end:]
io.open(p, 'w', encoding='utf-8').write(s)
print('verify18 J section rewritten')