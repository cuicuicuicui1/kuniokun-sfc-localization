"""Message DE 16x16 regression. Original narrow status ABI is separate.

Uses four existing runtime slots, both tile pairs. Buffer token index selects
slots so automatic line wrapping never aliases the previous name character.
"""
from pathlib import Path
import json,sys
from dialogue_model import make_cpu,flush
root=Path(__file__).resolve().parent
rom=(root/'kuniokun_cn.smc').read_bytes()
p=json.loads((root/'cn_build_params.json').read_text('utf8'))
if not p['itemsg']:
 print('SKIP: item-message hook absent in this build');sys.exit(0)
assert p.get('item_message_width')==2
n=p['slots']+2*p['label_sets']+p['label_name_glyphs']
base=p['slots']+2*p['label_sets']
lo=rom[0x1F0180:0x1F0180+n*2];hi=rom[0x1F0700:0x1F0700+n*2]
pairs=[a+256*b for a,b in zip(lo,hi)]

def call(c):
 c.pbr=c.db=3;c.pc=0xFA30;c.s=0x1FF;c.m8=c.x8=True
 c.push8(0xDF);c.push8(0xFF)
 for _ in range(50000):
  if (c.pbr,c.pc)==(3,0xE000):
   assert c.s==0x1FF and c.db==3 and c.m8 and c.x8, 'DE ABI mismatch'
   return
  c.step()
 raise AssertionError('DE consumer failed to return')

for start in (0,1,17,19,20,23,24,25):
 for row in (0,5,15):
  codes=bytes.fromhex('de3cde13de73de74')
  c=make_cpu(rom,codes);w=c.bus.wram;w[0x36E]=row;w[0x36F]=start
  expected={};cells={}
  for index in (0,2,4,6):
   w[0x3E9]=index;w[0x12]=0xDE
   w[0xB00:0xC00]=b'\xA5'*256
   r,col=w[0x36E],w[0x36F]
   if col>=p['wrap_col']:r=(r+1)&15;col=0
   call(c)
   assert w[0x3E9]==index+1, 'DE ID consumption'
   assert w[0x36E]==r and w[0x36F]==col+2, 'DE width/wrap'
   slot=base+((index>>1)&3)
   ident=codes[index+1]
   glyph=rom[p['menu_item_glyph_rom']+ident*64:p['menu_item_glyph_rom']+ident*64+64]
   for half,t in enumerate((pairs[slot],pairs[n+slot])):
    expected[t]=[int.from_bytes(glyph[half*32+j:half*32+j+2],'little') for j in range(0,32,2)]
    cell=int.from_bytes(bytes((rom[0x1FA8E+r],rom[0x1FA7E+r])),'little')+col+half
    cells[cell]=0x2400|t;cells[cell+32]=0x2400|(t+1)
   flush(c)
   for t,words in expected.items():
    assert c.vram[0x6000+t*8:0x6000+t*8+16]==words, ('live DE name glyph overwritten',start,row,index,t)
   for addr,value in cells.items():assert c.vram[addr]==value, ('name map cells lost',start,row,addr)
print('PASS full DE glyph halves/words, four live glyphs, odd/even starts and row15 wrap')
# Empty versus busy byte queue; keep train displacement and graphics neighbor.
for cursor,col,expected_size in ((0,0,200),(55,0,200),(56,0,0),(0,2,88),(167,2,88),(168,2,0),(240,25,0)):
 c=make_cpu(rom,bytes.fromhex('de3c'));w=c.bus.wram
 w[0x12]=0xDE;w[0x36E]=15;w[0x36F]=col;w[0x9DF]=cursor
 w[0x9DE]=0xA5;w[0x9E0]=0xF8;w[0x9E1]=0xFF
 before=(bytes(w[0x9DD:0x9E2]),bytes(w[0xB00:0xC00]))
 call(c)
 assert w[0x9DE]==0xA5 and bytes(w[0x9E0:0x9E2])==b'\xF8\xFF'
 if expected_size:
  assert w[0x9DF]==cursor+expected_size and w[0x3E9]==1
 else:
  assert bytes(w[0x9DD:0x9E2])==before[0] and bytes(w[0xB00:0xC00])==before[1]
  assert w[0x3E9]==255 and w[0x36E]==15 and w[0x36F]==col, 'busy draw changed state'
print('PASS byte queue capacity/deferral and graphics/train isolation')
