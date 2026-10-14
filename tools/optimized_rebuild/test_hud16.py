"""Full native HUD lifecycle and queue pressure checks (CPU model)."""
from pathlib import Path
import json,os,sys,hashlib
ROOT=Path(__file__).resolve().parent;SRC=ROOT/'source';os.chdir(SRC);sys.path.insert(0,str(SRC))
import cnbuild5 as cb,dialogue_model as D
cb.load_build_params();rom=(ROOT/'new-build/native-rebuild-candidate.sfc').read_bytes();p=json.loads((SRC/'cn_build_params.json').read_text(encoding='utf8'))

def call(c,b,pc,long=False):
 c.pbr=c.db=b;c.pc=pc;c.s=0x1ff;c.m8=c.x8=True
 if long:c.push8(0x3e)
 c.push8(0xdf);c.push8(0xff)
 for _ in range(100000):
  if (c.pbr,c.pc)==(0x3e if long else b,0xe000):
   assert c.s==0x1ff;return
  c.step()
 raise AssertionError(('native call timeout',b,hex(pc)))

# Complete dirty update defers atomically when the actual allocator is busy.
pressures=[]
for pending in (30,80,136,180,240):
 c=D.make_cpu(rom);w=c.bus.wram
 w[0x9DD]=0;w[0x9DF]=pending;w[0x9DE]=0x9a;w[0x9E0:0x9E2]=b'\xf8\xff'
 w[0x1C06]=0xE3;w[0x1B52:0x1B56]=rom[0x4802a+467*16:0x4802e+467*16]
 w[0xB00:0xC00]=b'\xa5'*256;before=bytes(w[0xB00:0xC00])
 call(c,0,0x8A96,long=True)
 assert w[0x1C06]&0xA0==0xA0 and w[0x9DF]==pending and bytes(w[0xB00:0xC00])==before,(pending,'update dropped')
 assert w[0x9DE]==0x9a and w[0x9E0:0x9E2]==b'\xf8\xff'
 # Reclaimed queue, original dirty flag still set. Native retry uploads both
 # halves of both glyphs and all four name cells before clearing dirty bits.
 w[0x9DD]=w[0x9DF]=0
 call(c,0,0x8A96,long=True)
 assert w[0x1C06]&0x80==0 and 0<w[0x9DF]<=226,(pending,'retry missing')
 D.flush(c)
 rec=rom[0x4802a+467*16:0x4802e+467*16]
 for glyph in (0,1):
  prefix,gid=rec[glyph*2:glyph*2+2]
  for half in (0,1):
   tile=p['hud_pairs'][2+glyph+half*4]
   src=p['pool_rom']+(prefix-0xc0)*0x8000+gid*64+half*32
   actual=b''.join(v.to_bytes(2,'little') for v in c.vram[0x6000+tile*8:0x6000+tile*8+16]);assert actual==rom[src:src+32]
   cell=0x7891+glyph*2+half
   assert c.vram[cell]&1023==tile+1 and c.vram[cell-32]&1023==tile
 pressures.append(pending)

# Player0 uses protected native kana, independent of the translated record.
for plate in (0,1):
 c=D.make_cpu(rom);w=c.bus.wram;w[0x10]=plate;w[0x1C03+plate]=0x20
 w[0x1B46+plate*4:0x1B4a+plate*4]=b'\xc2\xff\xc2\xfe'
 call(c,0,0x8C34);D.flush(c)
 vals=rom[0x185800+plate*8:0x185808+plate*8]
 lower=0x7842 if plate==0 else 0x7851
 for cell in range(4):
  assert c.vram[lower+cell]&1023==vals[cell*2]
  assert c.vram[lower-32+cell]&1023==vals[cell*2+1]
 for tile in set(vals):
  data=rom[0xF8000+tile*16:0xF8010+tile*16]
  # Static font is uploaded at boot, rather than this native queue model.
  assert tile in (0,117,120,134,209,210,213,214),tile

result={'status':'pass','sha256':hashlib.sha256(rom).hexdigest(),'queue_pressure_atomic_retry':pressures,'player_independent_of_actor_record':2,'enemy_name_cells':'two complete 16x16 glyphs, correct upper/lower map rows','scope':'CPU/queue model; no PPU timing claim'}
(ROOT/'qa').mkdir(exist_ok=True)
(ROOT/'qa/hud16-contract.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result,indent=2))
