"""Verify full HUD source glyphs, live VRAM and screenshot strokes."""
from pathlib import Path
import hashlib,json
from PIL import Image
ROOT=Path(__file__).resolve().parent
rom=(ROOT/'new-build/native-rebuild-candidate.sfc').read_bytes()
p=json.loads((ROOT/'source/cn_build_params.json').read_text(encoding='utf8'))
opt=Path(json.loads((ROOT/'inputs.json').read_text(encoding='utf8'))['opt']['path']).read_bytes()
expected={}
for i,code in enumerate(opt[0x73C7:0x73CB]):
 tile=opt[0x1FA9E+code];expected[0x7842+i]=(tile,opt[0xF8000+tile*16:0xF8010+tile*16])
for plate,record in [(1,513),(2,467),(3,0x11F)]:
 name=rom[0x4802A+record*16:0x4802E+record*16]
 lower=[0x7842,0x7851,0x7882,0x7891][plate]
 for glyph in (0,1):
  prefix,gid=name[glyph*2:glyph*2+2]
  if prefix<0xC0:continue
  source=p['pool_rom']+(prefix-0xC0)*0x8000+gid*64
  for half in (0,1):
   tile=([209,213][half] if plate==1 else p['hud_pairs'][(plate&1)*2+glyph+half*4])
   for yhalf in (0,1):
    addr=lower+glyph*2+half-(32 if yhalf==0 else 0)
    expected[addr]=(tile+yhalf,rom[source+half*32+yhalf*16:source+half*32+yhalf*16+16])

checks=[]
for dirname,tag,frame in [('hud16-display','hud16-display',20),('hud16-after-status-p1','hud16-after-status-p1',150)]:
 v=(ROOT/f'qa/{dirname}/{tag}-{frame}.vram').read_bytes();im=Image.open(ROOT/f'qa/{dirname}/{tag}-{frame}.png').convert('RGB');pixels=0
 for addr,(tile,bits) in expected.items():
  assert int.from_bytes(v[addr*2:addr*2+2],'little')&1023==tile,(dirname,hex(addr),'map identity')
  assert v[0xC000+tile*16:0xC010+tile*16]==bits,(dirname,tile,'glyph identity')
  row,col=divmod(addr-0x7800,32)
  for y in range(8):
   for x in range(8):
    if bits[y*2]&(128>>x):
     assert min(im.getpixel((col*8+x,row*8+y-1)))>=220,(dirname,hex(addr),x,y,'clipped/overwritten stroke');pixels+=1
 checks.append({'core':'Mesen','directory':dirname,'full_source_and_VRAM_cells':len(expected),'visible_source_strokes':pixels})
# Independent Snes9x cold boot and four-display fixture; no imported Mesen state.
im=Image.open(ROOT/'qa/hud16-snes-cold/frame-5050.png').convert('RGB');pixels=0
for addr,(tile,bits) in expected.items():
 row,col=divmod(addr-0x7800,32)
 for y in range(8):
  for x in range(8):
   if bits[y*2]&(128>>x):
    assert min(im.getpixel((col*8+x,row*8+y-1)))>=220,('Snes9x',hex(addr),x,y);pixels+=1
checks.append({'core':'Snes9x','directory':'hud16-snes-cold','visible_source_strokes':pixels})
result={'status':'pass','sha256':hashlib.sha256(rom).hexdigest(),'names':['くにお','力','翔子','春正'],'checks':checks,'scope':'four controlled native HUD display parameters, cold-boot-derived checkpoints; both halves visible without HDMA changes'}
(ROOT/'qa/hud16-pixels.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False,indent=2))
