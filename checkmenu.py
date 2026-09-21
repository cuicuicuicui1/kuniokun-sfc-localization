"""Static checks for the command window's pool-drawn labels (CMDWIN=2).

In this mode the five menu labels are two characters each, and their glyphs are
ordinary pool glyphs: the window's own draw loop still reads FA/FB for every
cell, so all the build has to get right is which tiles those codes name and
which cells name which code.  The tiles are the glyph's slot (left half t/t+1,
right half u/u+1); the tile *data* is staged at run time by the uploader stub,
which this also checks the wiring of.

    python checkmenu.py            # checks the ROM built with CMDWIN=2
"""
import sys
sys.path.insert(0, '.')
import json

import cnbuild5 as cb
import kuniokun_map as km

if cb.CMDWIN != 2:
    raise SystemExit('this check is for a CMDWIN=2 build (current: %r)' % cb.CMDWIN)

path = sys.argv[1] if len(sys.argv) > 1 else cb.OUT_ROM
print('checking %s' % path)
rom = open(path, 'rb').read()
orig = open(cb.ORIG_ROM, 'rb').read()
cb.load_build_params()
fail = []


def check(ok, msg):
    print('%s %s' % ('OK  ' if ok else 'FAIL', msg))
    if not ok:
        fail.append(msg)


# ---- the codes: two per glyph, pointing at the slot's tiles -----------------
chars = []
for _r, _c, txt in cb.MENU_LABELS:
    for ch in txt:
        if ch not in chars:
            chars.append(ch)
fa = rom[km.FA_OFF:km.FA_OFF + 256]
fb = rom[km.FB_OFF:km.FB_OFF + 256]
par = json.load(open(cb.BASE + '/cn_build_params.json', encoding='utf-8'))
cell = par['cell']
n = (par['slots'] + cb.LABEL_GLYPHS * cb.LABEL_SETS
     + cb.LABEL_NAME_GLYPHS * cb.LABEL_NAME_SETS)
lo = rom[cb.E3_SLOTPAIR:cb.E3_SLOTPAIR + 2 * n]
hi = rom[cb.E3_SLOTHI:cb.E3_SLOTHI + 2 * n]
entries = [lo[i] | (hi[i] << 8) for i in range(len(lo))]
# the slot table's entries are [left bases][right bases]
ok = True
for i, ch in enumerate(chars):
    slot = cell[ch][1]
    t, u = entries[slot], entries[par['slots'] + slot]
    x, y = cb.CMDWIN_CODES[2 * i], cb.CMDWIN_CODES[2 * i + 1]
    if (fb[x], fa[x], fb[y], fa[y]) != (t, t + 1, u, u + 1):
        ok = False
        print('   %r: codes %02X/%02X name (%02X,%02X,%02X,%02X), slot %d is '
              '(%02X,%02X,%02X,%02X)' % (ch, x, y, fb[x], fa[x], fb[y], fa[y],
                                         slot, t, t + 1, u, u + 1))
check(ok, '%d label glyphs: every code names its slot\'s tiles' % len(chars))

# the codes must be ones nothing else draws
check(list(cb.CMDWIN_CODES[:2 * len(chars)]) == list(cb.CMDWIN_CODES[:2 * len(chars)])
      and all(c in cb.CMDWIN_CODES for c in cb.CMDWIN_CODES[:2 * len(chars)]),
      'the label codes come from the reserved list (%s)'
      % ' '.join('%02X' % c for c in cb.CMDWIN_CODES[:2 * len(chars)]))

# ---- the cell table --------------------------------------------------------
tbl = rom[cb.CMDWIN_ROM:cb.CMDWIN_ROM + cb.CMDWIN_ROW * 2]
want = bytearray(cb.CMDWIN_ROW * 2)
for row, cellno, txt in cb.MENU_LABELS:
    q = row * cb.CMDWIN_ROW + cellno
    for ch in txt:
        i = chars.index(ch)
        want[q] = cb.CMDWIN_CODES[2 * i]
        want[q + 1] = cb.CMDWIN_CODES[2 * i + 1]
        q += 2
check(bytes(tbl) == bytes(want),
      'the cell table is two codes per glyph at the cursor\'s own cells')

# ---- the uploader ----------------------------------------------------------
code = rom[cb.MENU_STUB:cb.MENU_STUB + 240]
check(code[:3] == bytes([0x08, 0xE2, 0x30]), 'the uploader starts php / sep #$30')
check(bytes([0xAD, cb.MENU_LOAD & 0xFF, cb.MENU_LOAD >> 8]) in code,
      'the uploader reads the pending counter at $%04X' % cb.MENU_LOAD)
check(bytes([0xAC, 0x9A, 0x03, 0xB9, 0x51, 0xF8]) in code and bytes([0x5C]) in code,
      'the uploader replays the instructions the hook ate and jumps back')
hook = rom[cb.MENU_HOOK:cb.MENU_HOOK + 5]
check(hook[0] == 0x5C and hook[4] == 0xEA,
      'the dispatcher at $%04X is hooked (%s)' % (cb.MENU_HOOK, hook.hex(' ')))
bk = hook[3]
ad = hook[1] | (hook[2] << 8)
check((bk, ad) == (cb.MENU_STUB >> 15, 0x8000 + (cb.MENU_STUB & 0x7FFF)),
      'the hook points at the uploader ($%02X:%04X)' % (bk, ad))

# the table the uploader reads: [vram t][vram u][pool addr][pool bank]
tab = rom[cb.MENU_TAB:cb.MENU_TAB + 7 * len(chars)]
ok = True
for i, ch in enumerate(chars):
    slot = cell[ch][1]
    t, u = entries[slot], entries[par['slots'] + slot]
    page = cell[ch][0]
    src = cb.POOL_ROM + page * 0x8000 + slot * cb.POOL_STRIDE
    want = bytes([(0x6000 + t * 8) & 0xFF, (0x6000 + t * 8) >> 8,
                  (0x6000 + u * 8) & 0xFF, (0x6000 + u * 8) >> 8,
                  0x8000 + (src & 0x7FFF) & 0xFF, (0x8000 + (src & 0x7FFF)) >> 8,
                  src >> 15])
    got = tab[7 * i:7 * i + 7]
    if got != want:
        ok = False
        print('   %r: table %s want %s' % (ch, got.hex(' '), want.hex(' ')))
check(ok, 'the uploader table matches the glyphs\' slots and pool addresses')

# ---- the arm site ----------------------------------------------------------
arm = rom[cb.MENUCLOSE_STUB3:cb.MENUCLOSE_STUB3 + 60]
check(rom[cb.ARM_SITE] == 0x5C, 'the arming stub is hooked at $%06X' % cb.ARM_SITE)
check(bytes([0xA9, 0x01, 0x8D, cb.MENU_LOAD & 0xFF, cb.MENU_LOAD >> 8]) in arm,
      'the menu\'s open step arms the uploader')

print()
if fail:
    raise SystemExit('%d menu check(s) FAILED' % len(fail))
print('OK: the command window names pool slots and the uploader is wired to them')
