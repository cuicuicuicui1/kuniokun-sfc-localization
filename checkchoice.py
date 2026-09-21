"""Static checks for the Chinese yes/no choice box.

The box is not drawn from a string: three script blocks at $03:F465/$F47B/$F491
each fill the 64 byte cell buffer at $040A and upload it to one map row
($7BA0/$7BC0/$7BE0, the addresses coming from the tables at $03:F455/$F458).
The text row is eight pixels tall in the original -- the kana are the single
tiles $44/$45/$46 -- so the two options are drawn as 16x16 cells spanning the
text row and the bottom row.  This checks, against the built ROM:

  1. the two block scripts name the expected cells and keep every attribute
     (the attributes carry the corner tiles' flips);
  2. the font tiles those cells name hold exactly the 是/否 bitmaps, ink colour
     1 on a colour 2 background;
  3. every tile the box draws -- including the cursor's arrow and blank, which
     come from the table at $03:F3C7 rather than from the block scripts -- is
     outside the drawer's tile pool, so a hanzi upload cannot land on it;
  4. the region's non-tile bytes are byte-identical to the original ROM, i.e.
     the old blind kana rewrite (which corrupted $A4 into $54 and, worse, the
     second prompt set's block pointers) is really gone.

Run after every build that touches the choice box, the font or the tile budget.
"""
import sys
sys.path.insert(0, '.')
import json

import cnbuild5 as cb
import cnglyph

rom = open(cb.OUT_ROM, 'rb').read()
orig = open(cb.ORIG_ROM, 'rb').read()
cb.load_build_params()          # PROMPT_CLOBBERED is a build-time fixed point
fail = []


def check(ok, msg):
    print('%s %s' % ('OK  ' if ok else 'FAIL', msg))
    if not ok:
        fail.append(msg)


# ---- 1. the two block scripts ---------------------------------------------
for off, tiles, label in ((cb.CHOICE_BLOCK_UP, cb.CHOICE_ROW_UP_TILES, 'text row $7BC0'),
                          (cb.CHOICE_BLOCK_DN, cb.CHOICE_ROW_DN_TILES, 'bottom row $7BE0')):
    body = rom[off:off + 22]
    obody = orig[off:off + 22]
    check(body[0] == 0x22 and body[1] == 0x14,
          '%s: block header is $22 $14 (byte index, count)' % label)
    got = tuple(body[2 + 2 * i] for i in range(10))
    check(got == tiles,
          '%s: tiles %s' % (label, ' '.join('%02X' % t for t in got)))
    attrs = tuple(body[3 + 2 * i] for i in range(10))
    oattrs = tuple(obody[3 + 2 * i] for i in range(10))
    check(attrs == oattrs,
          '%s: attributes unchanged (%s)'
          % (label, ' '.join('%02X' % a for a in attrs)))

# the row the script uploads to: $0395 -> VRAM word address
rows = [rom[0x01F458 + i] | (rom[0x01F455 + i] << 8) for i in range(3)]
check(rows == [0x7BA0, 0x7BC0, 0x7BE0],
      'row addresses %s' % ' '.join('$%04X' % r for r in rows))

# ---- 2. the font bitmaps ---------------------------------------------------
for tiles, ch in ((cb.CHOICE_YES_TILES, '是'), (cb.CHOICE_NO_TILES, '否')):
    g = [[1 if v else 2 for v in row] for row in cnglyph.render16x16(ch)]
    quads = ([row[:8] for row in g[:8]], [row[:8] for row in g[8:]],
             [row[8:] for row in g[:8]], [row[8:] for row in g[8:]])
    want = b''.join(cb.pack_8x8(q) for q in quads)
    got = b''.join(rom[cb.km.FONT + t * 16:cb.km.FONT + t * 16 + 16] for t in tiles)
    check(got == want,
          '%s: font tiles %s hold the 16x16 glyph (ink 1 on colour 2)'
          % (ch, ' '.join('%02X' % t for t in tiles)))

# ---- 3. nothing the box draws is in the drawer's pool ----------------------
par = json.load(open(cb.BASE + '/cn_build_params.json', encoding='utf-8'))
n = (par['slots'] + cb.LABEL_GLYPHS * cb.LABEL_SETS
     + cb.LABEL_NAME_GLYPHS * cb.LABEL_NAME_SETS)
lo = rom[cb.E3_SLOTPAIR:cb.E3_SLOTPAIR + 2 * n]
hi = rom[cb.E3_SLOTHI:cb.E3_SLOTHI + 2 * n]
pool = set()
for i in range(len(lo)):
    base = lo[i] | (hi[i] << 8)
    pool.add(base)
    pool.add(base + 1)
cursor = tuple(rom[0x01F3C7 + i] for i in range(2))
check(cursor == (0x47, 0x49),
      'cursor table $03:F3C7 = arrow $%02X, blank $%02X' % cursor)
need = set(cb.CHOICE_YES_TILES) | set(cb.CHOICE_NO_TILES) | set(cursor)
bad = sorted(need & pool)
check(not bad, 'no choice-box tile is inside the drawer pool (clashes: %s)' % bad)
check(need <= cb.protected_tiles(),
      'every choice-box tile is protected (%s)'
      % ' '.join('%02X' % t for t in sorted(need)))

# the cursor cells are the two the cursor routine writes ($03:F3C3 = $7BD2/$7BD6;
# the routine reads the low bytes at $F3C3+Y and the high bytes at $F3C4+Y with
# Y = 2 * index, so the pairs are interleaved low,high,low,high)
caddr = [rom[0x01F3C3 + 2 * i] | (rom[0x01F3C4 + 2 * i] << 8) for i in range(2)]
check(caddr == [0x7BD2, 0x7BD6],
      'cursor cells %s' % ' '.join('$%04X' % a for a in caddr))
check(cb.CHOICE_ROW_UP_TILES[1] == 0x49 and cb.CHOICE_ROW_UP_TILES[5] == 0x49,
      'the two cursor cells are blank in the script (the cursor overwrites them)')

# ---- 4. the region is not kana-rewritten any more --------------------------
lo_t, hi_t = cb.PROMPT_TABLE
diff = [o for o in range(lo_t, hi_t)
        if rom[o] != orig[o] and not (0x40 <= orig[o] <= 0x5F)]
check(not diff,
      'no non-tile byte of the prompt region was rewritten (%d bytes differ)'
      % len(diff))
ptrs = orig[0x01F4A7:0x01F4AD]
check(rom[0x01F4A7:0x01F4AD] == ptrs,
      'second prompt set block pointers intact (%s)'
      % ' '.join('%02X' % b for b in ptrs))

print()
if fail:
    raise SystemExit('%d choice-box check(s) FAILED' % len(fail))
print('OK: the choice box draws 是 / 否 and nothing can overwrite it')
