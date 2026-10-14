from runtime_paths import source_tree
from pathlib import Path
import sys,os,json,hashlib
ROOT=Path(__file__).resolve().parent;SRC=source_tree();sys.path.insert(0,str(SRC));os.chdir(SRC)
from dialogue_model import make_cpu,flush
rom=(ROOT/'candidate-ui.sfc').read_bytes();par=json.loads((ROOT/'cn_build_params.json').read_text(encoding='utf-8'));m=json.loads((ROOT/'port-manifest.json').read_text(encoding='utf-8'))
def call(c,bk,pc):
 c.pbr=c.db=bk;c.pc=pc;c.s=0x1ff;c.m8=c.x8=True;c.push8(0xdf);c.push8(0xff)
 for _ in range(50000):
  if (c.pbr,c.pc)==(bk,0xe000):assert c.s==0x1ff;return
  c.step()
 raise AssertionError('native consumer did not return')
c=make_cpu(rom);w=c.bus.wram;hud=par['hud_pairs'];expected={}
for plate,record in [(2,0),(3,467)]:
 rec=rom[0x4802a+record*16:0x4802e+record*16];w[0x10]=plate;w[0x1c03+plate]=0x20;w[0x1b46+plate*4:0x1b4a+plate*4]=rec;call(c,0,0x8c34);flush(c)
 for g in (0,1):
  for half in (0,1):
   tile=hud[(plate&1)*2+g+half*(len(hud)//2)];off=(par['pool_bank0']+rec[g*2]-0xc0)*0x8000+rec[g*2+1]*64+half*32
   expected[tile]=[int.from_bytes(rom[off+j:off+j+2],'little') for j in range(0,32,2)]
checks=0
for ch,(page,slot) in m['extended_glyphs']['cells'].items():
 w[0x3e8]=2;w[0x3e9]=0;w[0x3ea:0x3ec]=bytes((0xc0+page,0x40+slot));w[0x12]=0xc0+page;w[0x36e]=4;w[0x36f]=6;c.a=0x6600|(0xc0+page)
 call(c,3,0xfa30);entries=flush(c);assert len(entries)==4,'extended glyph missing font/cell entries'
 for t,words in expected.items():assert c.vram[0x6000+t*8:0x6000+t*8+16]==words,(ch,'new pool overwrote either enemy HUD')
 checks+=1
result={'status':'pass','candidate_sha256':hashlib.sha256(rom).hexdigest(),'extended_glyphs':checks,'persistent_enemy_records':[0,467],'scope':'actual native drawer with hidden B and two live nameplates, including newly translated name; CPU/queue model only'}
(ROOT/'extended-hud-lifetime.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(result)
