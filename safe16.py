# -*- coding: utf-8 -*-
"""Is the original-font path safe in the current build?
Report: protected tiles, slot pairs, and whether the engine-drawn name glyphs
(tile 0x98 = り, 0x77 = き for りき), the scene tiles 0xE0/0xE1 and the box frame
0xF0 are all excluded from the slot table."""
import json
import sys
sys.path.insert(0, 'C:/Users/<user>/.zcode/workspace/default/sfc-recon')
import cnbuild5 as cb
cb.load_build_params()   # the switches this ROM was built with
import kuniokun_map as km

rom = open(cb.OUT_ROM, 'rb').read()
par = json.load(open('C:/Users/<user>/.zcode/workspace/default/sfc-recon/cn_build_params.json', encoding='utf-8'))
cb.SLOTS = par['slots']
def rom_of(bank, addr):
    return (bank % 0x40) * 0x8000 + (addr - 0x8000)
out = cb.OUT_ROM
LEFT = rom[cb.E3_SLOTPAIR:cb.E3_SLOTPAIR + cb.SLOTS]
RIGHT = rom[cb.E3_SLOTPAIR + cb.SLOTS:cb.E3_SLOTPAIR + 2 * cb.SLOTS]
pairs = list(LEFT) + list(RIGHT)
prot = cb.protected_tiles()
used = set()
for p in pairs:
    used.add(p)
    used.add((p + 1) & 0xFF)

print('ROM %s  crc32 %08X  size %d' % (out, __import__('zlib').crc32(rom) & 0xFFFFFFFF, len(rom)))
print('protected tiles: %d' % len(prot))
print('slot pairs: %d (slots %d)  tiles used by slots: %d' % (len(pairs), cb.SLOTS, len(used)))
for t, what in ((0x98, 'り (name)'), (0x77, 'き (name)'), (0xE0, 'scene bg'), (0xE1, 'scene bg'), (0xF0, 'box frame')):
    print('  tile 0x%02X %-12s protected=%s  used_by_slot=%s' % (t, what, t in prot, t in used))

# name table: the 560 records, first 4 bytes, codes -> tiles
tab = rom[rom_of(0x09, 0x802A):]
name_tiles = set()
for i in range(560):
    rec = tab[i * 16:i * 16 + 4]
    for b in rec:
        if b == 0:
            break
        name_tiles.add(km.FA[b]); name_tiles.add(km.FB[b])
print('name table tiles: %d  all protected=%s  any used by slot=%s'
      % (len(name_tiles), all(t in prot for t in name_tiles), sorted(name_tiles & used)))

# what does りき need?
rik = rom[rom_of(0x09, 0x802A) + 513 * 16:rom_of(0x09, 0x802A) + 513 * 16 + 4]
print('record 513 bytes: %s -> codes %s -> tiles %s'
      % (rik.hex(' '), list(rik), [(km.FA[b], km.FB[b]) for b in rik if b]))

# glyph cells of the probe characters
cell = json.load(open('C:/Users/<user>/.zcode/workspace/default/sfc-recon/cn_glyph_cell.json', encoding='utf-8'))
print('probe glyph cells:')
for ch in '猪肉包一个大阪啊':
    if ch in cell:
        page, slot = cell[ch]
        lt = LEFT[slot] if slot < cb.SLOTS else None
        rt = RIGHT[slot] if slot < cb.SLOTS else None
        print('  %s page %d slot %d tiles L(%d,%d) R(%d,%d)' % (ch, page, slot, lt, lt + 1, rt, rt + 1))
fxc = json.load(open('C:/Users/<user>/.zcode/workspace/default/sfc-recon/cn_build_params.json', encoding='utf-8'))
print('one byte codes:', fxc['fixed'], '@ $%02X' % fxc['fixed0'], ' pages:', fxc['pages'],
      ' prefix0 $%02X' % fxc['prefix0'])