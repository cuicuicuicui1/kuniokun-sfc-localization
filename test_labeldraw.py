# -*- coding: utf-8 -*-
"""Run the status-label interpreter hook on the built ROM.

Enters the interpreter at $01:F971 with DBR = $01 and lets it walk the whole
script.  For every label code it must upload that glyph's 32 byte 8x16 bitmap
from $3f:8000 + id*32 into the pool slot the code's entry in the slot table
names, then write the two cells at the interpreter's cursor; the name field and
the colon must still take the engine's own FA/FB path.

Slots come from the code, not from the cursor: all 23 labels are on screen at
once, so each needs its own slot, and they must stay below the item values'
base so the two never collide.
"""
import os
import sys
import sim65816 as S
import kuniokun_map as km

rom = open('kuniokun_cn.smc', 'rb').read()
SLOTPAIR_ROM = 0x1F0180
GLYPH_ROM = 0x1F8000
SLOT_TABLE = 0x1F4B00
N_ENT = 36 + 2 * 3 + 2 * 1
SCRIPT = 0x00F9DB
ITEM_BASE0 = 24


def slotpair():
    left = rom[SLOTPAIR_ROM:SLOTPAIR_ROM + N_ENT]
    right = rom[SLOTPAIR_ROM + N_ENT:SLOTPAIR_ROM + 2 * N_ENT]
    return list(zip(left, right))


def blocks():
    out, y = [], SCRIPT
    while rom[y] != 0xFF:
        vmadd = rom[y] | (rom[y + 1] << 8)
        cnt = rom[y + 2]
        y += 3
        n = cnt & 0x7F
        vals = list(rom[y:y + n])
        y += n
        out.append((vmadd, cnt, 'text' if cnt & 0x80 else 'tiles', vals))
    return out


sp = slotpair()
tab = rom[SLOT_TABLE:SLOT_TABLE + 256]
label_codes = sorted(c for c in range(256) if tab[c] != 0xFF)
slots = {c: tab[c] for c in label_codes}

cpu = S.CPU(rom)
cpu.pbr, cpu.db, cpu.pc, cpu.s = 0x01, 0x01, 0xF971, 0x01FF
cpu.m8 = cpu.x8 = True
ups, tiles = [], []
state = {'dst': 0}
orig = cpu.io_write


def hook(addr, val):
    # cpu.vaddr, not a shadow of $2116/$2117: the interpreter sets the address
    # once per cell and lets VMAIN walk it to the lower half, so a shadow would
    # report the same address twice
    if addr == 0x2119:
        w = cpu.vlow | (val << 8)
        (ups if cpu.vaddr < 0x7000 else tiles).append((cpu.vaddr, w))
    orig(addr, val)


cpu.dma_visible = True   # the uploads are DMA; watch them like CPU writes
cpu.io_write = hook
cpu.push8(0)
cpu.push8(0)
try:
    cpu.run(max_steps=4000000)
except NotImplementedError:
    pass

print('label codes: %d, slots %d..%d' % (len(label_codes), min(slots.values()),
                                         max(slots.values())))

fails = []
# The interpreter is called with M and X 8 bit and its caller goes straight on to
# read the character index with `LDX $1BA6`.  A hook that leaves X 16 bit makes
# that load two bytes and shifts every index after it -- the status screen came
# out black.  So the flag state at the RTS matters as much as the writes.
if not cpu.x8:
    fails.append("X is 16 bit at the interpreter's return")
if not cpu.m8:
    fails.append("M is 16 bit at the interpreter's return")
if len(label_codes) != 23:
    fails.append('%d label codes, expected 23' % len(label_codes))
if max(slots.values()) >= ITEM_BASE0:
    fails.append('a label slot is %d, at or past the item base %d'
                 % (max(slots.values()), ITEM_BASE0))
if len(set(slots.values())) != len(slots):
    fails.append('two label codes share a slot')
# The -- STATUS -- row is raw tile numbers: the hook never sees it, so a label
# slot sitting on one of its tiles would overwrite the row with a hanzi.
lit = set()
y = SCRIPT
while rom[y + 1] != 0xFF:
    cnt = rom[y + 2]
    n = cnt & 0x7F
    if not (cnt & 0x80):
        lit.update(rom[y + 3:y + 3 + n])
    y += 3 + n
lit.discard(0)
for c, sl in slots.items():
    t = sp[sl][0]
    if t in lit or t + 1 in lit:
        fails.append('label code $%02X uses slot %d (tiles %d/%d), which the '
                     'STATUS row draws' % (c, sl, t, t + 1))
        break

# walk the script and check every cell the interpreter wrote
want_ups, want_tiles = [], []
for vmadd, cnt, kind, vals in blocks():
    for k, c in enumerate(vals):
        a_up = vmadd + k
        a_dn = vmadd + k + 0x20          # VMAIN=$81: the next map row
        if kind != 'text':               # a literal tile run: blank upper, tile
            want_tiles += [(a_up, 0), (a_dn, c)]   # lower (see $F9A1)
            continue
        if c in slots:
            sl = slots[c]
            gid = rom[km.FA_OFF + c]     # the hook reads FA as the glyph id
            want_ups.append((sp[sl][0], gid))
            want_tiles += [(a_up, sp[sl][0]), (a_dn, sp[sl][0] + 1)]
        else:
            want_tiles += [(a_up, rom[km.FB_OFF + c]), (a_dn, rom[km.FA_OFF + c])]

got_tiles = [(a, w & 0x3FF) for a, w in tiles]
if got_tiles != want_tiles:
    nm = min(len(got_tiles), len(want_tiles))
    k = next((i for i in range(nm) if got_tiles[i] != want_tiles[i]), nm)
    fails.append('tile map: %d cells, expected %d; first difference at %d: '
                 'got %s want %s' % (len(got_tiles), len(want_tiles), k,
                                     got_tiles[k:k + 3], want_tiles[k:k + 3]))
if len(ups) != 16 * len(want_ups):
    fails.append('%d upload words, expected %d' % (len(ups), 16 * len(want_ups)))
else:
    for k, (tile, gid) in enumerate(want_ups):
        got = b''.join(bytes([w & 0xFF, w >> 8]) for _a, w in ups[16 * k:16 * k + 16])
        if got != rom[GLYPH_ROM + gid * 32:GLYPH_ROM + gid * 32 + 32]:
            fails.append('glyph %d: uploaded bytes are not glyph %d' % (k, gid))
            break

# The -- STATUS -- row is drawn from font tiles the pool also uses as slots, so
# the label hook puts them back from the font block on its first call.  Check
# the content, not just the writes: this is what the row actually shows.
if os.environ.get('LITFIX', '0') == '1':
  for t in lit:
    want_t = rom[0x0F8000 + t * 16:0x0F8000 + t * 16 + 16]
    # a VRAM word holds a byte PAIR: word i is bytes 2i and 2i+1
    got_t = bytes(b for i in range(8)
                  for b in (cpu.vram[(0x6000 + t * 8) + i] & 0xFF,
                            (cpu.vram[(0x6000 + t * 8) + i] >> 8) & 0xFF))
    if got_t != want_t:
        fails.append('tile $%02X in VRAM is not the font glyph: %s vs %s'
                     % (t, got_t.hex(' '), want_t.hex(' ')))

print('cells written: %d tile map words, %d upload words' % (len(tiles), len(ups)))
print()
if fails:
    print('FAIL (%d)' % len(fails))
    for f in fails[:10]:
        print('  ' + f)
else:
    print('PASS: every label glyph went to its own pool slot with its own '
          'bitmap; the name field and the colon still take FA/FB; no label '
          'slot reaches the item values')

# verify_all.py reads the exit code, so a FAIL has to leave one
sys.exit(1 if fails else 0)
