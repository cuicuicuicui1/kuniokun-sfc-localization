"""an16: score a hw/v61 dump against the builder's own expectations.

For every non blank cell of the box text area (tile map words $7C00-$7FFF) the
cell's tile pair is looked up in the slot table and the tile data in VRAM is
compared byte for byte with the glyph pool of the built ROM.  A cell whose tile
pair is not one of my slots is checked against the original font tiles the
engine builds from its FA/FB tables (that is how the speaker name is drawn).

usage: python an16.py <tag> [frame ...]
"""
import os
import sys

import cnbuild5 as cb
import sfc_tools as st

TAG = sys.argv[1] if len(sys.argv) > 1 else 'kfix8a'
FRAMES = [int(a) for a in sys.argv[2:]]
HW = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hw')

rom = open('kuniokun_cn.smc', 'rb').read()
params = __import__('json').load(open('cn_build_params.json', encoding='utf-8'))
cb.clamp_slots()
cb.SLOTS = params['slots']
NSLOT = params['slots']
_hi = list(rom[cb.E3_SLOTHI:cb.E3_SLOTHI + 2 * NSLOT])
left = [rom[cb.E3_SLOTPAIR + i] | (_hi[i] << 8) for i in range(NSLOT)]
right = [rom[cb.E3_SLOTPAIR + NSLOT + i] | (_hi[NSLOT + i] << 8) for i in range(NSLOT)]

# tile data in the dump lives at VRAM word $6000: byte offset ($6000 - $6000) * 2
# tile map words $7C00-$7FFF: byte offset ($7C00 - $6000) * 2 = 0x3800
dumps = sorted(f for f in os.listdir(HW) if f.startswith(TAG + '_f') and f.endswith('_vram.bin'))
if FRAMES:
    dumps = [f for f in dumps if int(f.split('_f')[1].split('_')[0]) in FRAMES]


def tile_bytes(v, t, half):
    """16 words = 32 bytes of tile t, upper or lower half of a glyph cell."""
    base = (0x6000 + t * 8 - 0x6000) * 2 + half * 32
    return bytes(v[base:base + 32])


def word(v, w):
    o = (w - 0x6000) * 2
    return v[o] | (v[o + 1] << 8)


# slot -> (page, slot index) by the pair values; two independent pairs per slot
by_pair = {}                       # (tile, half) -> (slot, side)
for s in range(NSLOT):
    by_pair[(left[s], 0)] = (s, 'L')
    by_pair[(right[s], 0)] = (s, 'R')

# the glyph pool of this build, per (page, slot): two 32 byte halves
pool_cache = {}


def pool(page, slot):
    key = (page, slot)
    if key not in pool_cache:
        off = cb.POOL_ROM + page * 0x8000 + slot * cb.POOL_STRIDE
        pool_cache[key] = rom[off:off + cb.POOL_STRIDE]
    return pool_cache[key]


# what glyph sits in which (page, slot), from the builder's maps
cell = __import__('json').load(open('cn_glyph_cell.json', encoding='utf-8'))
slot_of = {}
for ch, (page, sl) in cell.items():
    slot_of[(page, sl)] = ch

# original font: the engine renders code C as FA[C] in the upper cell and FB[C]
# in the lower one, uploaded from the font at ROM 0x0F8000
font = open(cb.ORIG_ROM, 'rb').read()


def font_tile(code):
    """The 16 bytes the engine will have in VRAM for the glyph of code C."""
    fa = font[0x01FA9E + code]
    fb = font[0x01FB9E + code]
    return fa, fb


orig_tiles = {}
for code in range(0x100):
    fa, fb = font_tile(code)
    orig_tiles[(fa, 0)] = code
    orig_tiles[(fb, 1)] = code

AREA_ROWS, AREA_COLS = 16, 64

for name in dumps:
    frame = int(name.split('_f')[1].split('_')[0])
    v = open(os.path.join(HW, name), 'rb').read()
    cn_ok = cn_bad = orig_hi = orig_lo = 0
    unknown = []
    blank = 0
    rows_seen = {}
    for r in range(AREA_ROWS):
        for c in range(AREA_COLS):
            w = word(v, 0x7C00 + r * 0x40 + c)
            if w == 0x2C00:
                blank += 1
                continue
            tile = w & 0x3FF
            pal = w & 0x3C00
            half = 0 if c < 32 else 1
            key = (tile, half)
            if key in by_pair and pal == 0x2400:
                s, side = by_pair[key]
                # which (page, slot) is in this slot?  the drawer picks the slot
                # by glyph, and the pool bytes are what must be in VRAM
                want = None
                for pg in range(params['pages']):
                    if (pg, s) not in slot_of:
                        continue
                    p = pool(pg, s)
                    off = 0 if side == 'L' else 32
                    if p[off:off + 32] == tile_bytes(v, tile, 0):
                        want = (pg, s, slot_of[(pg, s)])
                        break
                if want:
                    cn_ok += 1
                    rows_seen.setdefault(r, []).append((c, want[2]))
                else:
                    cn_bad += 1
                    unknown.append((r, c, tile, 'CN pair but pool mismatch'))
            elif key in orig_tiles and pal == 0x2400:
                if half == 0:
                    orig_hi += 1
                else:
                    orig_lo += 1
                rows_seen.setdefault(r, []).append((c, 'orig$%02X' % orig_tiles[key]))
            else:
                unknown.append((r, c, tile, 'pal $%04X' % pal))
    print('%s F=%d  CN cells exact %d  mismatched %d  original font %d (%d/%d)  '
          'blank %d  unknown %d'
          % (TAG, frame, cn_ok, cn_bad, orig_hi + orig_lo, orig_hi, orig_lo,
             blank, len(unknown)))
    for r in sorted(rows_seen):
        items = sorted(rows_seen[r])
        txt = ''.join(str(x[1]) for x in items[:40])
        print('    row %2d: %s' % (r, txt))
    for u in unknown[:8]:
        print('    unknown row %d col %d tile %03X %s' % u)
print('dumps analysed: %d' % len(dumps))