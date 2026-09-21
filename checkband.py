"""Static proof that the patch can never draw outside the font window.

The coloured band came from label glyph tiles living above tile 255: the layers
whose character base is $C000 read those VRAM bytes as *tile map cells*, so every
label draw rewrote a scene row.  The drawer keeps the tile number of a slot in
two places - the pair base byte in the slot table and a high byte (bits 8-9) in
the table at $3E:8700 - so "no tile above 255" is exactly "every high byte is 0".

Run after every build that changes the tile budget.
"""
import sys
sys.path.insert(0, '.')
import cnbuild5 as cb

import json
rom = open(cb.OUT_ROM, 'rb').read()
par = json.load(open(cb.BASE + '/cn_build_params.json', encoding='utf-8'))
n = (par['slots'] + cb.LABEL_GLYPHS * cb.LABEL_SETS
     + cb.LABEL_NAME_GLYPHS * cb.LABEL_NAME_SETS)
print('slot stride %d entries, table %d bytes at ROM 0x%06X, high table at 0x%06X'
      % (n, 2 * n, cb.E3_SLOTPAIR, cb.E3_SLOTHI))
lo = rom[cb.E3_SLOTPAIR:cb.E3_SLOTPAIR + 2 * n]
hi = rom[cb.E3_SLOTHI:cb.E3_SLOTHI + 2 * n]
bad = [i for i, b in enumerate(hi) if b]
print('slot pair bases   : %s' % ' '.join('%02X' % b for b in lo[:16]))
print('slot pair high    : %s' % ' '.join('%02X' % b for b in hi[:16]))
print('entries with a non-zero high byte: %d' % len(bad))
if bad:
    for i in bad[:10]:
        print('   entry %d: base $%02X high $%02X -> tile %d'
              % (i, lo[i], hi[i], lo[i] | (hi[i] << 8)))
    raise SystemExit('FAIL: the drawer can address tiles above 255')
print('OK: every label and body tile is inside the font window (0..255)')

# ---- the engine's own fixed prompts must keep their glyphs -------------------
# The choice window and the other fixed prompts are drawn by the engine from the
# font block.  Any tile the drawer uploads a hanzi into loses that glyph, so no
# prompt-table tile may be inside the drawer's pool.
import kuniokun_map as km
orig = open(cb.ORIG_ROM, 'rb').read()
# the prompt tables hold *tile numbers*, not codes (see prompt_table_tiles)
need = cb.prompt_table_tiles()
pool = set()
for i in range(len(lo)):
    base = lo[i] | (hi[i] << 8)
    pool.add(base)
    pool.add(base + 1)
bad = sorted(need & pool)
print('prompt-table tiles: %d ; reserved by the build: %s ; groups: %s'
      % (len(need), par.get('prompt_clobbered'), par.get('protect_groups')))
print('prompt tiles still inside the drawer pool: %s' % bad)
if bad:
    raise SystemExit('FAIL: the option window would show garbled cells at %s' % bad)
print('OK: every prompt-table glyph is out of the drawer\'s reach')
