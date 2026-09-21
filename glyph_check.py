"""Content-level acceptance for the patched ROM's first dialogue.

Chain that has to hold end to end:
  1. the codes the game itself put in the message buffer (read out of WRAM by the
     emulator) -> (page, slot) for every Chinese cell
  2. (page, slot) -> the character, decided by the glyph pool bitmap alone
  3. the glyph pool bytes for that cell == a fresh render of that character
  4. the bytes the patch actually left in VRAM == those same pool bytes
  5. the tile numbers in the BG tilemap == the slot pair the patch reserved

Nothing is read by eye; every step is a byte comparison.  The message is not
stored as one contiguous run in the ROM (the engine assembles it from table
pieces), so step 1 starts from the emulator's RAM dump and step 6 corroborates
it against the translated table entry that the message quotes.
"""
import json
import re

import cnbuild5 as cb
from cnfont8 import render8x16
from sfc_tools import pack_8x8

ROM = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/kuniokun_cn.smc'
DUMP = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/kfix16.log'
TRANS = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/cn_translation.json'

# the game's own message buffer at $03EA, frame 1383 (hw/v17.lua): the first five
# bytes are the macro-generated speaker name "りき  :", then the Chinese codes.
BUFFER = bytes.fromhex('47 26 00 00 09 CB 3F CD 49 C6 01 C5 15 C5 29 01 F2')

rom = open(ROM, 'rb').read()
trans = json.load(open(TRANS, encoding='utf-8'))

# ---------------------------------------------------------------- slot table
blob = rom[cb.B3_SLOTPAIR:cb.B3_SLOTPAIR_LIMIT]
SLOTPAIR = []
for b in blob:
    if b == 0:
        break
    SLOTPAIR.append(b)
assert SLOTPAIR == sorted(SLOTPAIR) and all(t % 2 == 0 for t in SLOTPAIR)
SLOTS = len(SLOTPAIR)
print('slot table: %d slots, tiles %03X..%03X' % (SLOTS, SLOTPAIR[0], SLOTPAIR[-1]))

# ------------------------------------------------- codes the game produced
codes = []
i = 5
while i < len(BUFFER) - 1:
    if cb.PREFIX0 <= BUFFER[i] < cb.PREFIX0 + 16:
        codes.append((BUFFER[i] - cb.PREFIX0, BUFFER[i + 1]))
        i += 2
    else:
        i += 1
print('codes in the game buffer:',
      ' '.join('%02X:%02X' % (cb.PREFIX0 + p, s) for p, s in codes))
assert len(codes) == 5, codes

# ------------------------------------------- pool bitmap -> character
def glyph32(ch):
    g = render8x16(ch, cb.FONT_PATH, 16, cb.GLYPH_THRESH, cb.GLYPH_WIDEN)
    return pack_8x8(g[:8]) + pack_8x8(g[8:])


chars = sorted({c for s in trans.values() for c in s if c != ' '})
by_glyph = {}
for ch in chars:
    by_glyph.setdefault(glyph32(ch), []).append(ch)

PAGES = 16
cell_char = {}
for page in range(PAGES):
    for slot in range(SLOTS):
        off = (cb.POOL_BANK0 + page) * 0x8000 + slot * 32
        g = rom[off:off + 32]
        if g == b'\x00' * 32:
            continue
        for ch in by_glyph.get(g, []):
            cell_char[(page, slot)] = ch

scene = ''.join(cell_char.get(c, '?') for c in codes)
print('the game drew: %r' % scene)
assert '?' not in scene

# ------------------------------------------------------------- the dump
cells = []
for line in open(DUMP, encoding='utf-8'):
    m = re.match(r'CELL row=(\d+) col=(\d+) top=([0-9A-F]+) bot=([0-9A-F]+) '
                 r'slot=(\d+) glyph=([0-9A-F]+)', line)
    if m:
        cells.append(dict(row=int(m.group(1)), col=int(m.group(2)),
                          top=int(m.group(3), 16), bot=int(m.group(4), 16),
                          slot=int(m.group(5)), glyph=bytes.fromhex(m.group(6))))
cells.sort(key=lambda c: c['col'])
assert [c['col'] for c in cells] == [5, 6, 7, 8, 9], [c['col'] for c in cells]
assert len(cells) == len(codes)

bad = 0
for k, c in enumerate(cells):
    page, sid = codes[k]
    top = SLOTPAIR[sid]
    pool_off = (cb.POOL_BANK0 + page) * 0x8000 + sid * 32
    pool = rom[pool_off:pool_off + 32]
    want = glyph32(scene[k])
    ok_t = (top == c['top'] and c['bot'] == top + 1)
    ok_p = (pool == c['glyph'])
    ok_w = (pool == want)
    print('col %d %r page %2d slot %-3d tile %03X/%03X  tilemap=%s '
          'vram==pool=%s pool==render=%s'
          % (c['col'], scene[k], page, sid, top, top + 1,
             'ok' if ok_t else 'MISMATCH', ok_p, ok_w))
    if not (ok_t and ok_p and ok_w):
        bad += 1
        print('    pool %s' % pool.hex(' '))
        print('    vram %s' % c['glyph'].hex(' '))
        print('    want %s' % want.hex(' '))

# ------------------- corroborate against the translated table entry it quotes
label = bytes([0xCB, 0x3F, 0xCD, 0x49, 0xC6, 0x01])
off = rom.find(label)
assert off == 0x1E804, hex(off)
entry = rom[off:off + 8]
dec = ''.join(cell_char.get((entry[2 * k] - cb.PREFIX0, entry[2 * k + 1]), '?')
              for k in range(3))
print('ROM 0x%06X entry %s -> %r' % (off, entry.hex(' '), dec))
assert dec == scene[:3], (dec, scene)
print('table entry terminates with %s (segment separator)' % entry[6:].hex(' '))
assert entry[6:] == b'\xF2\xF3'
key = '%06X' % off
print('translation[%s] = %r' % (key, trans.get(key)))

print('ALL CONTENT CHECKS PASSED' if not bad else '%d CELLS FAILED' % bad)