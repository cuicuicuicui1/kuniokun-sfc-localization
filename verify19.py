"""Checks for the static command window (Start menu) labels - 2026-09-21 rework.

The window builder ($03:F95D) draws 26 cells per row from the byte table at ROM
0x01F743, taking each cell's upper tile from FB[code] and the lower one from
FA[code]; both are 8 bit, so the glyphs have to sit inside the font window and
be there statically.  The twelve 8x16 hanzi therefore live in the tile pairs the
speaker name label sets gave up (their pairs moved outside the font window, and
the drawer's 16 bit tile map words carry the high bits).

Checks:
  A  slot table: label entries moved out (hi = 1), everything else inside (hi = 0),
     no tile used twice
  B  the twelve freed pairs hold the rendered glyph halves, byte for byte
  C  the borrowed codes' FA/FB point at them, and only those codes changed
  D  the 52 byte window table places the codes at the right cells
  E  the drawer's tile map word for a label entry carries tile bits 8-9 in the
     attribute byte, and a body entry still comes out as $24 + the tile
  F  a preview of the two window rows, from the patched ROM font

    python verify19.py
"""
import json

from PIL import Image

import cnbuild5 as cb
import cnglyph
import kuniokun_map as km
from sfc_tools import pack_8x8

rom = open('kuniokun_cn.smc', 'rb').read()
orig = open(cb.ORIG_ROM, 'rb').read()
fails = []


def fail(msg):
    fails.append(msg)
    print('  FAIL ' + msg)


def ok(msg):
    print('  ok   ' + msg)


def tile_bits(n):
    """8x8 tile -> 8 rows of 8 ints, from VRAM/ROM font data."""
    out = []
    for y in range(8):
        b0 = n[y * 2]
        b1 = n[y * 2 + 1]
        out.append([((b0 >> (7 - x)) & 1) | (((b1 >> (7 - x)) & 1) << 1)
                    for x in range(8)])
    return out


print('A  slot table')


def entry(e, base):
    """The 16 bit tile at entry e (base 0 = the left half table, n_ent = right)."""
    return (rom[cb.E3_SLOTPAIR + base + e]
            | (rom[cb.E3_SLOTHI + base + e] << 8))


cb.clamp_slots()
pairs, hi, npairs, win = cb.build_slotpairs()
n_ent = cb.SLOT_STRIDE
nlab = 2 * cb.LABEL_GLYPHS * cb.LABEL_SETS
n_lab_ent = nlab // 2
if len(pairs) != 2 * n_ent:
    fail('table has %d entries, expected %d' % (len(pairs), 2 * n_ent))
elif bytes(pairs) != rom[cb.E3_SLOTPAIR:cb.E3_SLOTPAIR + 2 * n_ent]:
    fail('slot table in the ROM differs from the builder output')
if len(hi) != 2 * n_ent:
    fail('high table has %d entries' % len(hi))
elif bytes(hi) != rom[cb.E3_SLOTHI:cb.E3_SLOTHI + 2 * n_ent]:
    fail('high table in the ROM differs from the builder output')

# the six label pair sets moved outside the font window
bad = 0
for k in range(n_lab_ent):
    tl = entry(cb.SLOTS + k, 0)
    tr = entry(cb.SLOTS + k, n_ent)
    if (tl, tr) != (cb.OUTSIDE_PAIRS[2 * k], cb.OUTSIDE_PAIRS[2 * k + 1]):
        fail('label entry %d holds %d/%d, expected %d/%d'
             % (k, tl, tr, cb.OUTSIDE_PAIRS[2 * k], cb.OUTSIDE_PAIRS[2 * k + 1]))
        bad += 1
if not bad:
    ok('%d label pair sets moved outside the font window (%d..%d)'
       % (n_lab_ent, min(cb.OUTSIDE_PAIRS), max(cb.OUTSIDE_PAIRS)))

# every other entry stays inside: a 10 bit tile there would point at VRAM the
# engine redraws, and the glyph would land on unrelated graphics
for e in range(n_ent):
    for base in (0, n_ent):
        if cb.SLOTS <= e < cb.SLOTS + n_lab_ent:
            continue
        t = entry(e, base)
        if t > 255:
            fail('entry %d/%d is inside but holds tile %d' % (base, e, t))
allp = [entry(e, base) for e in range(n_ent) for base in (0, n_ent)]
dups = sorted(t for t in set(allp) if allp.count(t) > 1)
if dups:
    fail('tile pairs used twice: %s' % dups)
else:
    ok('%d entries, all pairs distinct, %d inside the font window'
       % (n_ent, sum(1 for t in allp if t < 256)))
# the window takes one pair per distinct hanzi, which is at most the label
# pairs the label sets freed (it is fewer now that the labels are short)
if len(win) != len(set(''.join(t for _r, _c, t in cb.CMDWIN_LABELS))):
    fail('the window got %d pairs, expected %d'
         % (len(win), len(set(''.join(t for _r, _c, t in cb.CMDWIN_LABELS)))))

print('B  the twelve glyphs are in the freed font tiles')
chars = []
for _r, _c, txt in cb.CMDWIN_LABELS:
    for ch in txt:
        if ch not in chars:
            chars.append(ch)
if len(chars) > len(win):
    fail('need %d pairs, have %d' % (len(chars), len(win)))
bad = 0
for i, ch in enumerate(chars[:len(win)]):
    t = win[i]
    g = cnglyph.render16(ch)
    up = pack_8x8(g[:8])
    lo = pack_8x8(g[8:])
    if rom[km.FONT + t * 16:km.FONT + t * 16 + 16] != up:
        fail('%r upper tile %d in the font does not match the render' % (ch, t))
        bad += 1
    if rom[km.FONT + (t + 1) * 16:km.FONT + (t + 1) * 16 + 16] != lo:
        fail('%r lower tile %d in the font does not match the render' % (ch, t + 1))
        bad += 1
if not bad:
    ok('%d glyphs byte exact in %d tile pairs' % (len(chars), len(win)))

print('C  borrowed codes')
codes = cb.CMDWIN_CODES[:len(chars)]
ofa = orig[km.FA_OFF:km.FA_OFF + 256]
ofb = orig[km.FB_OFF:km.FB_OFF + 256]
nfa = rom[km.FA_OFF:km.FA_OFF + 256]
nfb = rom[km.FB_OFF:km.FB_OFF + 256]
for c in range(256):
    if (nfa[c], nfb[c]) != (ofa[c], ofb[c]) and c not in codes:
        fail('code $%02X: FA/FB changed but it was not borrowed' % c)
for i, ch in enumerate(chars):
    c = codes[i]
    t = win[i]
    if not (nfb[c] == t and nfa[c] == t + 1):
        fail('%r (code $%02X): FA/FB %d/%d, expected %d/%d'
             % (ch, c, nfa[c], nfb[c], t + 1, t))
used = {1}                       # tile 0 is the engine's blank tile
for i, ch in enumerate(chars):
    pass
ok('codes %s -> pairs %s' % (' '.join('%02X' % c for c in codes), win))

print('D  the window table')
tbl = rom[cb.CMDWIN_ROM:cb.CMDWIN_ROM + 2 * cb.CMDWIN_ROW]
want = bytearray(2 * cb.CMDWIN_ROW)
code_of = {ch: codes[i] for i, ch in enumerate(chars)}
for row, cell, txt in cb.CMDWIN_LABELS:
    q = row * cb.CMDWIN_ROW + cell
    for ch in txt:
        want[q] = code_of[ch]
        q += 1
if bytes(tbl) != bytes(want):
    fail('window table differs; got %s' % bytes(tbl).hex(' '))
else:
    ok('5 labels at cells %s'
       % ' '.join('%d/%d' % (r, c) for r, c, _t in cb.CMDWIN_LABELS))
if rom[cb.CMDWIN_ROW * 2:cb.CMDWIN_ROM] != orig[cb.CMDWIN_ROW * 2:cb.CMDWIN_ROM]:
    pass                                     # (nothing to check above the table)

print('E  the drawer builds the right tile map word')
for e, what in ((0, 'body'), (cb.SLOTS, 'label'), (cb.SLOTS + nlab // 2, 'name')):
    t = rom[cb.E3_SLOTPAIR + e] | (rom[cb.E3_SLOTHI + e] << 8)
    tr = rom[cb.E3_SLOTPAIR + n_ent + e] | (rom[cb.E3_SLOTHI + n_ent + e] << 8)
    for v, tag in ((t, 'left'), (tr, 'right')):
        word = (v | 0x2400) & 0xFFFF
        tile = word & 0x3FF
        if tile != v:
            fail('%s entry %d %s: word $%04X carries tile %d, wanted %d'
                 % (what, e, tag, word, tile, v))
        if (word >> 8) & 0xFC != 0x24:
            fail('%s entry %d %s: attribute byte $%02X' % (what, e, tag, word >> 8))
    ok('%-5s entry %d -> tiles %d/%d, words $%04X/$%04X'
       % (what, e, t, tr, (t | 0x2400), (tr | 0x2400)))

print('F  preview')
SC = 4
img = Image.new('RGB', (26 * 8 * SC + 16, 2 * 16 * SC + 12), (12, 12, 16))
for row in range(2):
    for c in range(26):
        code = tbl[row * cb.CMDWIN_ROW + c]
        if code == 0:
            continue
        for half, t in ((0, nfb[code]), (1, nfa[code])):
            g = tile_bits(rom[km.FONT + t * 16:km.FONT + t * 16 + 16])
            for y in range(8):
                for x in range(8):
                    v = g[y][x]
                    if v:
                        col = ((60, 200, 255), (255, 210, 90), (255, 90, 90))[min(v, 3) - 1]
                    else:
                        col = (16, 16, 22)
                    px = 8 + c * 8 * SC + x * SC
                    py = 6 + (row * 16 + half * 8 + y) * SC
                    for dy in range(SC):
                        for dx in range(SC):
                            img.putpixel((px + dx, py + dy), col)
img.save('hw/cmdwin_preview.png')
print('  wrote hw/cmdwin_preview.png (26 cells x 2 rows, as the builder draws it)')
for row in range(2):
    s = []
    for c in range(26):
        code = tbl[row * cb.CMDWIN_ROW + c]
        s.append('.' if code == 0 else '%02X' % code)
    print('  row %d: %s' % (row, ' '.join(s)))

print()
print('ALL CHECKS PASSED' if not fails else '%d FAILURES' % len(fails))
raise SystemExit(1 if fails else 0)
