"""CPU/queue-model checks; deliberately do not claim PPU timing or full-game QA."""
from pathlib import Path
import json,sys,os,hashlib
ROOT=Path(__file__).resolve().parent;SRC=ROOT/'source';sys.path.insert(0,str(SRC));os.chdir(SRC)
import cnbuild5 as cb,dialogue_model as D
cb.load_build_params();rom=(ROOT/'new-build/native-rebuild-candidate.sfc').read_bytes();p=json.loads((SRC/'cn_build_params.json').read_text(encoding='utf8'));cells=json.loads((SRC/'cn_glyph_cell.json').read_text(encoding='utf8'))
N=cb.SLOTS+2*cb.LABEL_SETS+cb.LABEL_NAME_GLYPHS;lo=rom[cb.E3_SLOTPAIR:cb.E3_SLOTPAIR+2*N];hi=rom[cb.E3_SLOTHI:cb.E3_SLOTHI+2*N];pairs=[a+256*b for a,b in zip(lo,hi)]
checks=[]
def call(c,b,pc,long=False,m8=True,x8=True):
 c.pbr=c.db=b;c.pc=pc;c.s=0x1ff;c.m8=m8;c.x8=x8
 if long:c.push8(3)
 c.push8(0xdf);c.push8(0xff)
 for _ in range(80000):
  if (c.pbr,c.pc)==(b if not long else 3,0xe000):assert c.s==0x1ff;return
  c.step()
 raise AssertionError(('call timeout',b,hex(pc)))
def draw(c,wire,row,col,index=0):
 w=c.bus.wram;w[0x36e]=row;w[0x36f]=col;w[0x3e8]=len(wire);w[0x3e9]=index;w[0x3ea:0x3ea+len(wire)]=wire;w[0x12]=wire[index];c.a=0x6600|wire[index]
 call(c,3,0xfa30);assert c.db==3 and c.m8 and c.x8;return D.flush(c)
# Every pool bitmap through the actual drawer; source IDs above slot count must work.
c=D.make_cpu(rom);w=c.bus.wram;sample_count=0
for ch,(page,gid) in cells.items():
 w[0x3e5]=1;w[0x3e6]=5;w[0x9de]=0x9a;w[0x9e0:0x9e2]=b'\xf8\xff';entries=draw(c,bytes([0xc0+page,gid]),5,6)
 assert len(entries)==4,(ch,entries)
 slot=13+3
 for half in (0,1):
  tile=pairs[slot+half*N];off=(p['pool_bank0']+page)*0x8000+gid*64+half*32;expected=rom[off:off+32];actual=b''.join(v.to_bytes(2,'little') for v in c.vram[0x6000+tile*8:0x6000+tile*8+16]);assert actual==expected,(ch,half,tile)
 assert w[0x3e9]==1 and w[0x36f]==8
 assert w[0x9de]==0x9a and w[0x9e0:0x9e2]==b'\xf8\xff'
 sample_count+=1
checks.append({'name':'all pool glyph source/cell/queue contract','count':sample_count})
# Consecutive rolling rows across both 15->0 ring wrap and DE/body interleaving.
visible={};c=D.make_cpu(rom);w=c.bus.wram;w[0x3e6]=15
letters=list(cells.items());counter=0
for logical in range(40):
 row=logical&15;current={}
 for col in range(0,26,2):
  ch,(page,gid)=letters[counter%len(letters)];counter+=1
  wire=bytes([0xde,counter%len(p['item_chars'])]) if col==10 else bytes([0xc0+page,gid])
  entries=draw(c,wire,row,col);slot=w[0x3e5]*13+col//2
  assert slot<39
  if wire[0]==0xde:src=0x1fa000+wire[1]*64
  else:src=(p['pool_bank0']+page)*0x8000+gid*64
  for half in (0,1):
   tile=pairs[slot+half*N];current[tile]=rom[src+half*32:src+half*32+32]
  for oldlogical,old in visible.items():
   if logical-oldlogical<3:
    assert not set(old)&set(current),('shared rolling rows',logical,oldlogical)
    for tile,expected in old.items():
     actual=b''.join(v.to_bytes(2,'little') for v in c.vram[0x6000+tile*8:0x6000+tile*8+16]);assert actual==expected,('visible old row mutated',logical,oldlogical,tile)
 visible[logical]=current
 visible={i:v for i,v in visible.items() if logical-i<3}
checks.append({'name':'rolling 3-row lifetime with DE/name/body sharing and 15->0 wrap','rows':40,'glyphs':counter})
# Full queues must defer without altering the source index/row/column/font data.
for byte_count in (169,180,200,240):
 c=D.make_cpu(rom);w=c.bus.wram;w[0x9df]=byte_count;w[0xb00:0xc00]=b'\xa5'*256;w[0x36e]=5;w[0x36f]=6;w[0x3e8]=2;w[0x3ea:0x3ec]=b'\xc0\x01';w[0x12]=0xc0;before=bytes(w[0xb00:0xc00]);call(c,3,0xfa30)
 assert w[0x3e9]==255 and bytes(w[0xb00:0xc00])==before and w[0x9df]==byte_count and w[0x36e:0x370]==bytes([5,6])
checks.append({'name':'queue pressure retry','count':4})
# ABI helper supports both register widths without truncating live Y/hidden B.
for m8 in (False,True):
 for x8 in (False,True):
  c=D.make_cpu(rom);w=c.bus.wram;w[0x36e]=7;w[0x36f]=10;w[0x3e6]=7;w[0x3e5]=2;c.a=0x66c2;c.y=0x5a if x8 else 0x345a;c.d=0;c.c=True;c.n=True;original=(c.a,c.y,c.c,c.n)
  call(c,3,0xc000,long=True,m8=m8,x8=x8) if False else None
  c.pbr=0x30;c.db=3;c.pc=0xc000;c.s=0x1ff;c.m8=m8;c.x8=x8;c.push8(3);c.push8(0xdf);c.push8(0xff)
  for _ in range(300):
   if (c.pbr,c.pc)==(3,0xe000):break
   c.step()
  assert (c.pbr,c.pc,c.s)==(3,0xe000,0x1ff)
  assert (c.a,c.y,c.c,c.n)==original and c.x==31 and c.m8==m8 and c.x8==x8
checks.append({'name':'positional helper complete ABI','cases':4})
# Keep both enemy nameplates and the resident player glyphs through all body writes.
c=D.make_cpu(rom);w=c.bus.wram;hud=p['hud_pairs'];held={}
for plate,record in [(2,1),(3,467)]:
 rec=rom[cb.NAME_RECORD_BASE+record*16:cb.NAME_RECORD_BASE+record*16+4]
 w[0x10]=plate;w[0x1c03+plate]=0x20;w[0x1b46+plate*4:0x1b4a+plate*4]=rec
 call(c,0,0x8c34);D.flush(c)
 for glyph in (0,1):
  if rec[glyph*2]<0xc0:continue
  prefix,gid=rec[glyph*2:glyph*2+2]
  for half in (0,1):
   tile=hud[(plate&1)*2+glyph+half*4];off=(p['pool_bank0']+prefix-0xc0)*0x8000+gid*64+half*32;held[tile]=rom[off:off+32]
for ch,(page,gid) in cells.items():
 draw(c,bytes([0xc0+page,gid]),4,6)
 for tile,expected in held.items():
  actual=b''.join(v.to_bytes(2,'little') for v in c.vram[0x6000+tile*8:0x6000+tile*8+16]);assert actual==expected,(ch,'enemy HUD overwritten',tile)
layout=json.loads((ROOT/'new-build/ui-layout.json').read_text(encoding='utf8'))
for plate in (0,1):
 w[0x10]=plate
 for cell in range(4):
  w[0x18]=plate*4+cell
  c.pbr=0;c.db=0;c.pc=0x8c91;c.s=0x1ff;c.m8=c.x8=True
  # Hook is JSL: execute that hook, then stop before original caller continues.
  for _ in range(100):
   if (c.pbr,c.pc)==(0,0x8c95):break
   c.step()
  else:raise AssertionError('player HUD gateway failed to return')
  expected=rom[0x185800+2*(plate*4+cell):0x185802+2*(plate*4+cell)];assert w[0x22:0x24]==expected
  assert c.s==0x1ff and c.db==0 and c.m8 and c.x8
checks.append({'name':'persistent two-enemy HUD plus isolated player name ABI','body_glyphs':len(cells),'new_enemy_record':467})
# Generic loader executes the native macro expansion for all main entries.
readback=json.loads((ROOT/'new-build/main-readback.json').read_text(encoding='utf8'));maxbuf=0
for row in readback:
 c=D.make_cpu(rom);w=c.bus.wram;w[0x373]=0;w[0x34a:0x34c]=row['id'].to_bytes(2,'little');w[0x34c:0x34e]=(0x200).to_bytes(2,'little');w[0x35d]=0x3e;w[0x35e]=0x44
 call(c,3,0xeb68);assert w[0x36a:0x36c]==(0x8000+(row['offset']&0x7fff)).to_bytes(2,'little');call(c,3,0xeb9e);maxbuf=max(maxbuf,w[0x3e8]);assert w[0x3e8]<200,(row['id'],w[0x3e8]);assert w[0x3e5]==0 and w[0x3e6]==0
checks.append({'name':'all main first slices native loader/macros','count':len(readback),'max_decoded_bytes':maxbuf})
result={'status':'pass','sha256':hashlib.sha256(rom).hexdigest(),'checks':checks,'scope':'65816/queue model; no claim of NMI timing, natural routes or hardware'};(ROOT/'qa').mkdir(exist_ok=True)
(ROOT/'qa/positional-model.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False,indent=2))
