# -*- coding: utf-8 -*-
"""Run the item-name renderer on the built ROM and check what it writes.

Enters the original routine at $01:FC75 with A = n + 1 (record n), DBR = $01
and the VRAM cursor at $79C6 -- the status screen's buki row, column 6.  For
every two byte item code the routine must upload that glyph's 32 byte 8x16
bitmap from $3f:8000 + id*32 into the tile pair of the slot the cursor names,
then write the two tile map cells at the current column.  Digits and kana in
the same name must still take the engine's own FA/FB path.

The slot comes from the cursor: base 0 for $79c6 and one per column after
column 6, so the glyphs of one value must land in slots 0, 1, 2, ... and never
share a tile pair.  $7a06 and $7a46 must shift the base to 12 and 24.
"""
import json
import sys
import sim65816 as S
import kuniokun_map as km

rom = open('kuniokun_cn.smc', 'rb').read()
SLOTPAIR_ROM = 0x1F0180
GLYPH_ROM = 0x1F8000
TABLE = 0x1DBC3
_par = json.load(open('cn_build_params.json', encoding='utf-8'))
N_ENT = _par['slots'] + 2 * _par['label_sets'] + _par['label_name_glyphs']
ITEM_BASE0 = 24                     # the item values start above the
ITEM_SPAN = 4                       # status labels' slots 0..22


def slotpair():
    left = rom[SLOTPAIR_ROM:SLOTPAIR_ROM + N_ENT]
    right = rom[SLOTPAIR_ROM + N_ENT:SLOTPAIR_ROM + 2 * N_ENT]
    return list(zip(left, right))


def name_at(n):
    lo, hi = rom[TABLE + (n + 1) * 2], rom[TABLE + (n + 1) * 2 + 1]
    off = 0x18000 + ((lo | (hi << 8)) - 0x8000)
    out = []
    i = off
    while rom[i] not in (0xF2, 0xF3):
        if rom[i] == 0xDE:
            out.append(('g', rom[i + 1]))
            i += 2
        else:
            out.append(('k', rom[i]))
            i += 1
    return out


def run(record, cursor):
    cpu = S.CPU(rom)
    cpu.pbr, cpu.db, cpu.pc, cpu.s = 0x01, 0x01, 0xFC75, 0x01FF
    cpu.m8 = cpu.x8 = True
    cpu.a = record + 1
    cpu.bus.wr(0, 0x20, cursor & 0xFF)
    cpu.bus.wr(0, 0x21, cursor >> 8)
    ups, tiles = [], []
    state = {'dst': 0}
    orig = cpu.io_write

    def hook(addr, val):
        if addr == 0x2116:
            state['dst'] = (state['dst'] & 0xFF00) | val
        elif addr == 0x2117:
            state['dst'] = (state['dst'] & 0x00FF) | (val << 8)
        elif addr == 0x2119:
            w = cpu.vlow | (val << 8)
            (ups if state['dst'] < 0x7000 else tiles).append((state['dst'], w))
        orig(addr, val)

    cpu.dma_visible = True   # the uploads are DMA; watch them like CPU writes
    cpu.io_write = hook
    cpu.push8(0xDE)
    cpu.push8(0xAD)
    for _ in range(400000):
        if (cpu.pbr, cpu.pc) == (0x01, 0xDEAE):
            assert cpu.s == 0x1FF, 'status renderer stack imbalance'
            break
        cpu.step()
    else: raise AssertionError('status renderer did not return')
    return ups, tiles


sp = slotpair()
fails = []
checked = 0
for record in range(110):
    units = name_at(record)
    glyphs = [u for u in units if u[0] == 'g']
    if not glyphs:
        continue
    ups, tiles = run(record, 0x79C6)
    checked += 1
    if len(tiles) != 2 * len(units):
        fails.append('rec %d: %d tile map words for %d units'
                     % (record, len(tiles), len(units)))
        continue
    if len(ups) != 16 * len(glyphs):
        fails.append('rec %d: %d upload words for %d glyphs'
                     % (record, len(ups), len(glyphs)))
        continue
    gi = 0
    for k, (kind, v) in enumerate(units):
        up_t = tiles[2 * k][1] & 0x3FF
        dn_t = tiles[2 * k + 1][1] & 0x3FF
        up_a, dn_a = tiles[2 * k][0], tiles[2 * k + 1][0]
        if up_a != 0x79C6 + k or dn_a != 0x79C6 + k:
            fails.append('rec %d unit %d: cells at %04X/%04X, expected %04X'
                         % (record, k, up_a, dn_a, 0x79C6 + k))
        if kind == 'g':
            want = sp[ITEM_BASE0 + k][0]  # the slot follows the COLUMN (base 24
                                          # for row $79c6) and a digit in front
                                          # shifts the hanzi up
            if up_t != want or dn_t != want + 1:
                fails.append('rec %d unit %d: tiles %d/%d, slot %d is %d/%d'
                             % (record, k, up_t, dn_t, k, want, want + 1))
            got = b''.join(bytes([w & 0xFF, w >> 8])
                           for _a, w in ups[16 * gi:16 * gi + 16])
            if got != rom[GLYPH_ROM + v * 32:GLYPH_ROM + v * 32 + 32]:
                fails.append('rec %d unit %d: uploaded bytes are not glyph %d'
                             % (record, k, v))
            gi += 1
        else:
            if up_t != km.FB[v] or dn_t != km.FA[v]:
                fails.append('rec %d unit %d: kana/digit tiles %d/%d, want %d/%d'
                             % (record, k, up_t, dn_t, km.FB[v], km.FA[v]))

# the other two rows must shift the slot base
for cursor, base in ((0x7A06, ITEM_BASE0 + ITEM_SPAN),
                     (0x7A46, ITEM_BASE0 + 2 * ITEM_SPAN)):
    ups, tiles = run(0, cursor)
    got = [tiles[2 * k][1] & 0x3FF for k in range(3)]
    want = [sp[base + k][0] for k in range(3)]
    if got != want:
        fails.append('cursor %04X: slots %s, expected bases %s'
                     % (cursor, got, want))
    if tiles[0][0] != cursor:
        fails.append('cursor %04X: first cell at %04X' % (cursor, tiles[0][0]))

print('checked %d records with hanzi' % checked)
print('row $79C6 -> slot bases %s' % [sp[ITEM_BASE0 + k][0] for k in range(4)])
print('row $7A06 -> slot bases %s' % [sp[ITEM_BASE0 + ITEM_SPAN + k][0] for k in range(4)])
print('row $7A46 -> slot bases %s' % [sp[ITEM_BASE0 + 2 * ITEM_SPAN + k][0] for k in range(4)])
print()
if fails:
    print('FAIL (%d)' % len(fails))
    for f in fails[:12]:
        print('  ' + f)
else:
    print('PASS: every glyph went to its own slot, its own tile pair and its '
          'own bitmap; digits and kana still take the FA/FB path; the three '
          'rows use the slot bases 24 / 28 / 32')

# verify_all.py reads the exit code, so a FAIL has to leave one
sys.exit(1 if fails else 0)
