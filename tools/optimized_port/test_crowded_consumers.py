from runtime_paths import source_tree
from pathlib import Path
import sys,json,os,hashlib,itertools
ROOT=Path(__file__).resolve().parent;SRC=source_tree();sys.path.insert(0,str(SRC));os.chdir(SRC)
from dialogue_model import make_cpu,flush
rom=(ROOT/'candidate-ui.sfc').read_bytes();par=json.loads((ROOT/'cn_build_params.json').read_text(encoding='utf-8'));manifest_path=ROOT/'port-manifest.json'
if not manifest_path.exists():manifest_path=ROOT.parent/'port-full-v15-20261012/port-manifest.json'
cells=json.loads(manifest_path.read_text(encoding='utf-8'))['extended_glyphs']['cells'];hud=par['hud_pairs']
def call(c,bank,pc,long=False):
 c.pbr=c.db=bank;c.pc=pc;c.s=0x1fff;c.m8=c.x8=True
 if long:c.push8(bank)
 c.push8(0xdf);c.push8(0xff)
 for _ in range(50000):
  if (c.pbr,c.pc)==(bank,0xe000):assert c.s==0x1fff;return
  c.step()
 raise AssertionError(('consumer timeout',bank,pc))
def actors(w,recordA,recordB):
 # All seven slots exist in this game, only four native HUD plate entries.
 for slot in range(7):
  w[0xe01+slot]=0x80 if slot<2 else 0x81;w[0x122f+slot]=int(slot>=4)
  w[0x124d+slot]=(recordA+slot)&255;w[0x1246+slot]=(recordA+slot)>>8;w[0xf01+slot]=(slot+2);w[0x1331+slot]=int(slot in (2,3));w[0x12a6+slot]=123;w[0x12ad+slot]=0
 for plate,rec in [(2,recordA),(3,recordB)]:
  w[0x1c03+plate]=0xa0;w[0x1b46+plate*4:0x1b4a+plate*4]=rom[0x4802a+rec*16:0x4802e+rec*16]
def actorGuard(w):return bytes(w[0xe00:0x149f])+bytes(w[0x1d20:0x1ddf])
def checkHUD(c,recordA,recordB):
 w=c.bus.wram
 for plate,recid in [(2,recordA),(3,recordB)]:
  rec=rom[0x4802a+recid*16:0x4802e+recid*16]
  for g,half in itertools.product((0,1),(0,1)):
   tile=hud[(plate&1)*2+g+half*4];off=(par['pool_bank0']+rec[g*2]-0xc0)*0x8000+rec[g*2+1]*64+half*32
   want=[int.from_bytes(rom[off+i:off+i+2],'little') for i in range(0,32,2)]
   assert c.vram[0x6000+tile*8:0x6000+tile*8+16]==want,('visible HUD mismatch',plate,recid,g,half)
count=0;deferred=0;maxAttempts=0
for record in range(514):
 if rom[0x4802a+record*16]<0xc0 or rom[0x4802c+record*16]<0xc0:continue
 other=(record+173)%514
 while rom[0x4802a+other*16]<0xc0 or rom[0x4802c+other*16]<0xc0:other=(other+1)%514
 for cursor,readpos,velocity in [(0,0,8),(8,0,0xfff8),(40,0,8),(120,0,0xfff8),(200,0,8),(255,0,0xfff8),(255,255,8)]:
  c=make_cpu(rom);w=c.bus.wram;actors(w,record,other);guard=actorGuard(w);w[0x9dd]=readpos;w[0x9df]=cursor;w[0x9de]=0xa5;w[0x9e0:0x9e2]=velocity.to_bytes(2,'little');w[0xb00:0xc00]=bytes([0xa5])*256;w[0xc00:0xc10]=bytes([0x6d])*16
  for attempt in range(4):
   start=w[0x9df];previous=bytes(w[0xb00:0xb00+start]);call(c,0,0x8a96,True)
   assert actorGuard(w)==guard,'HUD touched NPC/battle/story arrays';assert w[0x9de]==0xa5 and w[0x9e0:0x9e2]==velocity.to_bytes(2,'little'),'HUD touched train neighbors';assert w[0xc00:0xc10]==bytes([0x6d])*16,'HUD crossed queue page'
   # The native allocator legitimately resets a fully consumed queue.
   qstart=0 if readpos>=start else start
   if qstart==start:assert bytes(w[0xb00:0xb00+start])==previous
   w[0x9dd]=qstart;end=w[0x9df]
   assert qstart<=end<=255
   flush(c);w[0x9dd]=w[0x9df]=0;readpos=0
   if (w[0x1c05]|w[0x1c06])&128:deferred+=1
   else:break
  else:raise AssertionError('HUD never retries full plate')
  checkHUD(c,record,other);count+=1;maxAttempts=max(maxAttempts,attempt+1)
# Retain a full field of seven actors, both live HUDs, then interleave every new
# glyph with DE item names. This exercises multiple native consumers, not just
# independent bitmap/address comparisons.
c=make_cpu(rom);w=c.bus.wram;actors(w,0,467);guard=actorGuard(w)
for _ in range(3):
 call(c,0,0x8a96,True);flush(c)
 if not (w[0x1c05]|w[0x1c06])&128:break
checkHUD(c,0,467);interleaved=0
for ch,(page,slot) in cells.items():
 for codes in [bytes((0xc0+page,0x40+slot)),bytes((0xde,(slot*7+page)%256))]:
  w[0x3e8]=len(codes);w[0x3e9]=0;w[0x3ea:0x3ea+len(codes)]=codes;w[0x36e]=4+interleaved%2;w[0x36f]=0 if interleaved%3==0 else 6;w[0x12]=codes[0];c.a=0x6600|codes[0]
  call(c,3,0xfa30);flush(c);checkHUD(c,0,467)
  assert actorGuard(w)==guard and w[0xc00:0xc10]==bytes(16),'drawer changed actors or adjacent queue storage'
  interleaved+=1
r={'status':'pass','candidate_sha256':hashlib.sha256(rom).hexdigest(),'native_HUD_cases':count,'deferred_checks':deferred,'max_attempts':maxAttempts,'interleaved_newfont_item_cases':interleaved,'actor_slots_preserved':7,'scope':'real native outer HUD allocator and drawer in CPU/queue model; full/dirty/consumed queues, both train velocity signs, seven actor arrays, persistent two enemy plates; not seven simultaneous HUD plates'}
(ROOT/'crowd-model-checks.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(r)
