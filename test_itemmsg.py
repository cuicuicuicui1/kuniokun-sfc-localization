# -*- coding: utf-8 -*-
"""Run the drawer's $DE branch on the built ROM and check what it writes.

A battle message pastes an item name in as [$DE][8x16 id] per hanzi, a code the
message drawer did not know: it fell through to the fixed-glyph path, so each
byte drew its own wrong glyph and a two hanzi name came out as four fragments.
build_itemmsg() adds the branch.  The glyph is 8x16 (one column, tiles t/t+1),
it is staged through the $0B00 queue (the message box is drawn during active
display, so there is no VRAM DMA), and the routine leaves through $03:FA7A so
the column advances exactly once and the id byte is eaten.

The slot is SLOT0 + (column & 3): the glyphs of one name sit in four consecutive
columns, so their low bits are always distinct.
"""
import sys
import sim65816 as S

import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
rom=(ROOT/'kuniokun_cn.smc').read_bytes()
par=json.loads((ROOT/'cn_build_params.json').read_text(encoding='utf-8'))
if not par.get('itemsg', b'\xc9\xde' in rom[0x1F0200:0x1F0600]):
    print('SKIP: item-message hook absent in this build')
    sys.exit(0)
assert b'\xc9\xde' in rom[0x1F0200:0x1F0600], 'missing item-message dispatch'
SLOTPAIR_ROM = 0x1F0180
SLOTS = par['slots']
LABEL_SETS = par.get('label_sets',2)
LABEL_NAME_GLYPHS = par.get('label_name_glyphs',4)
N_ENT = SLOTS + 2 * LABEL_SETS + LABEL_NAME_GLYPHS
SLOT0 = SLOTS + 2 * LABEL_SETS
ITEMMSG_FILE = 0x1F5400               # $3E:D400
ITEMMSG_CPU = (0x3E, 0xD400)
GLYPH_ROM = 0x1F8000
ITEM_PREFIX = 0xDE


def slotpair():
    left = rom[SLOTPAIR_ROM:SLOTPAIR_ROM + N_ENT]
    return list(left)


def run(ident, row, col, cursor=0, idx=0):
    cpu = S.CPU(rom)
    cpu.pbr, cpu.db, cpu.pc, cpu.s = 0x3E, 0x03, ITEMMSG_CPU[1], 0x01FF
    cpu.m8 = cpu.x8 = True
    cpu.bus.wr(0, 0x03E9, idx)
    cpu.bus.wr(0, 0x03EA + idx, ITEM_PREFIX)
    cpu.bus.wr(0, 0x03EA + idx + 1, ident)
    cpu.bus.wr(0, 0x036E, row)
    cpu.bus.wr(0, 0x036F, col)
    cpu.bus.wr(0, 0x09DF, cursor)
    cpu.bus.wr(0, 0x09E0, 0)
    cpu.push8(0xF2)
    cpu.push8(0xA9)
    for _ in range(20000):
        if (cpu.pbr,cpu.pc)==(0x03,0xF2AA):break
        cpu.step()
    else:raise AssertionError('item-message hook did not return')
    assert cpu.s==0x1FF and cpu.m8 and cpu.x8 and cpu.db==3
    q = bytes(cpu.bus.rd(0, 0x0B00 + i) & 0xFF for i in range(256))
    return (cpu.bus.rd(0, 0x03E9), cpu.bus.rd(0, 0x036F),
            cpu.bus.rd(0, 0x09DF), q)


fails = []
# the feature's real marker: the drawer's dispatch carries CMP #$DE
IDENT = 7
ROW, COL = 5, 20
gl = rom[GLYPH_ROM + 32 * IDENT:GLYPH_ROM + 32 * IDENT + 32]
tiles = {}
for c in range(4):
    tiles[c] = slotpair()[SLOT0 + (c & 3)]

for c in range(4):
    idx, colf, cur, q = run(IDENT, ROW, COL + c, 0, 0)
    want_t = tiles[c]
    branch = ('cell %d (col %d): ' % (c, COL + c))
    if idx != 1:
        fails.append(branch + '$03E9 = %d, expected 1 (the id byte eaten)' % idx)
    if colf != COL + c + 1:
        fails.append(branch + '$036F = %d, expected %d (one column)' % (colf, COL + c + 1))
    if cur != 44:
        fails.append(branch + 'queue cursor %d, expected 44' % cur)
        continue
    ent = q[0:36]
    addr = ent[0] | (ent[1] << 8)
    want_addr = 0x6000 + want_t * 8
    if addr != want_addr or ent[2] != 0x80 or ent[3] != 0x20:
        fails.append(branch + 'tile entry header %04X/%02X/%02X, expected %04X/80/20'
                     % (addr, ent[2], ent[3], want_addr))
    if ent[4:36] != gl:
        fails.append(branch + 'the 32 staged bytes are not glyph %d' % IDENT)
    # the two cells: the address comes from the ROM's own row tables
    clo = rom[0x01FA8E + ROW]
    chi = rom[0x01FA7E + ROW]
    want_c = ((chi << 8) | clo) + (COL + c)
    cell = q[36:44]
    got_c = cell[0] | (cell[1] << 8)
    if got_c != want_c:
        fails.append(branch + 'cell address %04X, expected %04X' % (got_c, want_c))
    if (cell[2], cell[3]) != (0x81, 0x04):
        fails.append(branch + 'cell header %02X/%02X, expected 81/04' % (cell[2], cell[3]))
    want_w = ((0x24 << 8) | (want_t & 0xFF))
    got_w = cell[4] | (cell[5] << 8)
    got_w2 = cell[6] | (cell[7] << 8)
    if got_w != want_w or got_w2 != ((0x24 << 8) | ((want_t + 1) & 0xFF)):
        fails.append(branch + 'cells %04X/%04X, expected %04X/%04X'
                     % (got_w, got_w2, want_w, (0x24 << 8) | ((want_t + 1) & 0xFF)))

# consecutive columns must use consecutive (and distinct) slots
used = [tiles[c] for c in range(4)]
if len(set(used)) != 4:
    fails.append('the four columns share slots: %s' % used)

# a full queue must give the frame back: no traffic, index unchanged
idx, colf, cur, q = run(IDENT, ROW, COL, 0x100 - 20, 0)
if any(q):
    fails.append('a nearly full queue still staged %d bytes' % sum(1 for b in q if b))
if colf != COL:
    fails.append('a nearly full queue advanced the column to %d' % colf)
if idx != 255:
    fails.append('a nearly full queue left $03E9 = %d, expected 255 (the consumer '
                 'increments it)' % idx)

print('item glyph table entry %d, name slots %d..%d -> tiles %s'
      % (IDENT, SLOT0, SLOT0 + 3, used))
print()
if fails:
    print('FAIL (%d)' % len(fails))
    for f in fails[:10]:
        print('  ' + f)
else:
    print('PASS: a $DE code takes the glyph id that follows it, stages the 32 byte '
          '8x16 glyph into the pair of slot SLOT0 + (column & 3) through the $0B00 '
          'queue, writes the two cells at the ROM row table\'s address, eats the id '
          'byte and advances exactly one column; the four columns of a name are '
          'four distinct slots; and a full queue gives the frame back untouched')

sys.exit(1 if fails else 0)
