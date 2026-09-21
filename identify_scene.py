"""Identify the first dialogue on screen from the glyph pool itself.

The pool is the ground truth: glyph (page, slot) sits at
ROM (0x21 + page)*0x8000 + slot*32.  Rendering every character used by the
translation and locating its 32 bytes in the pool gives the char -> (page, slot)
map without trusting any stale side file.
"""
import json

import cnbuild5 as cb
from cnfont8 import render8x16
from sfc_tools import pack_8x8

ROM = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/kuniokun_cn.smc'
rom = open(ROM, 'rb').read()
trans = json.load(open('C:/Users/<user>/.zcode/workspace/default/sfc-recon/'
                       'cn_translation.json', encoding='utf-8'))


def glyph32(ch):
    g = render8x16(ch, cb.FONT_PATH, 16, cb.GLYPH_THRESH, cb.GLYPH_WIDEN)
    return pack_8x8(g[:8]) + pack_8x8(g[8:])


# slot table
SLOTPAIR = []
for b in rom[cb.B3_SLOTPAIR:cb.B3_SLOTPAIR_LIMIT]:
    if b == 0:
        break
    SLOTPAIR.append(b)
SLOTS = len(SLOTPAIR)
PAGES = 12

chars = sorted({c for s in trans.values() for c in s if c not in ' '})
print('%d distinct translated characters' % len(chars))

by_glyph = {}
for ch in chars:
    by_glyph.setdefault(glyph32(ch), []).append(ch)

cell_of = {}
for page in range(PAGES):
    for slot in range(SLOTS):
        off = (cb.POOL_BANK0 + page) * 0x8000 + slot * 32
        g = rom[off:off + 32]
        if g == b'\x00' * 32:
            continue
        for ch in by_glyph.get(g, []):
            cell_of[ch] = (page, slot)

# what the emulator drew, in cell order: (page, slot) as read out of the RAM buffer
observed = [(6, 0x3F), (8, 0x49), (1, 0x01), (0, 0x15), (0, 0x29)]
inv = {v: k for k, v in cell_of.items()}
print('cells observed:', [(p, hex(s), inv.get((p, s), '??')) for p, s in observed])
scene = ''.join(inv.get(k, '?') for k in observed)
print('scene text: %r' % scene)

for k, v in trans.items():
    if scene in v:
        print('translation key %s = %r  (orig offset ROM 0x%s)' % (k, v, k))
        n = len(v)
        print('  stored bytes:', rom[int(k, 16):int(k, 16) + n * 2 + 8].hex(' '))
        break