"""Protect live HP/name/condition graphics, checking the actual built slot table.

The two original HP tile sets have identical 2bpp bitmaps; palette selection
remains in $19. Test all nine fill states for both palette branches, not just
the full red bar seen when opening Start in the hotel.
"""
from pathlib import Path
import json
rom=Path('kuniokun_cn.smc').read_bytes();orig=Path('dl/roms/kuniokun__SF8127.smc').read_bytes()
p=json.loads(Path('cn_build_params.json').read_text());n=p['slots']+2*p['label_sets']+p['label_name_glyphs']
reach=set()
for i in range(2*n):
 tile=rom[0x1F0180+i] | rom[0x1F0700+i]<<8
 reach.update((tile,tile+1))
shared=p.get('hud_bar_shared',False)
bar=set(range(0xE7,0xF0))|{0xF2}
if not shared:bar.update(range(0xF7,0x100))
assert not reach & bar, ('pool overwrites live HP tiles',sorted(reach & bar))
live=set(orig[0xFC55:0xFC75])
assert not reach & live, ('pool overwrites name/condition fields',sorted(reach & live))
for t in bar|live:
 start=0xF8000+t*16
 assert rom[start:start+16]==orig[start:start+16], ('live font bitmap overwritten',hex(t))
if shared:
 assert rom[0xAD9:0xADB]==bytes.fromhex('A9 00')
 assert rom[0xB77:0xB79]==bytes.fromhex('A9 E7')
 # Keep all remaining HP drawing instructions and palette selectors intact.
 for lo,hi in ((0xACC,0xAD9),(0xADB,0xAED),(0xAF0,0xB77),(0xB79,0xBC5)):
  assert rom[lo:hi]==orig[lo:hi], ('HP code changed unexpectedly',hex(lo))
 for fill in range(9):
  for enemy in (False,True):
   old=0xE7+fill+(16 if enemy else 0);new=0xE7+fill
   assert orig[0xF8000+old*16:0xF8000+(old+1)*16]==rom[0xF8000+new*16:0xF8000+(new+1)*16]
assert 0x108000+p['pages']*0x8000 <= 0x1F0000, 'glyph pool overwrites hook code'
print('PASS: live HP/name/condition tiles excluded; 18 original bar bitmaps/palettes retained; code bank safe')
