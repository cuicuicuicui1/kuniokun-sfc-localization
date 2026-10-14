"""Same native consumers on normal rc2 and no-HP-loss variant."""
from pathlib import Path
import json,hashlib,zlib,sys,argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'source'))
import sim65816 as S
from make_nohp import install,PATCHES
ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('normal',type=Path);parser.add_argument('hack',type=Path);parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
old=args.normal.read_bytes();new=args.hack.read_bytes();rebuilt,writes=install(old);assert rebuilt==new
allowed=set(range(0x7FDC,0x7FE0))
for off,expected,replacement,_ in PATCHES:allowed.update(range(off,off+len(bytes.fromhex(expected))))
diff=[i for i,(a,b) in enumerate(zip(old,new)) if a!=b];assert set(diff)<=allowed
assert new[0x9EA6-0x8000:0x9EDB-0x8000]==old[0x9EA6-0x8000:0x9EDB-0x8000]
assert new[0x17ED0:0x17EE5]==old[0x17ED0:0x17EE5]
assert new[0x10144B:0x101452]==old[0x10144B:0x101452]
checks=[]
def cpu(rom,b,pc,x=0,y=0):
 c=S.CPU(rom);c.pbr=c.db=b;c.pc=pc;c.s=0x1ff;c.x=x;c.y=y;c.a=0xA500;c.m8=c.x8=True;c.c=True;return c

def until(c,bank,pc):
 for _ in range(10000):
  if (c.pbr,c.pc)==(bank,pc):return
  c.step()
 raise AssertionError(('did not return',c.pbr,hex(c.pc)))

# Both players, nonlethal/lethal/zero damage and all 8bit HP edges.
for player in (0,1):
 for hp in (1,5,25,127,200,255):
  for damage in (0,1,4,25,127,255):
   for variant,rom in [('normal',old),('nohp',new)]:
    c=cpu(rom,0,0x9E87,player);w=c.bus.wram;w[0x10E+player]=hp;w[0x10E+(player^1)]=77;w[0x1BA9+player]=damage;w[0x110:0x114]=b'\x12\x34\x56\x78';until(c,0,0x9E9B)
    assert w[0x10E+player]==(hp if variant=='nohp' else max(0,hp-damage)),(variant,player,hp,damage)
    assert w[0x10E+(player^1)]==77 and w[0x110:0x114]==b'\x12\x34\x56\x78';assert c.x==player and c.db==0 and c.s==0x1ff and c.a>>8==0xA5
checks.append({'name':'native player damage, both player slots, 6 HP x 6 damage, old/new control','cases':144})

# Equipment signed drain uses original FD2B helper, no altered math or healing.
for player in (0,1):
 for hp in (1,25,255):
  for entry,end,delta in [(0xE0AE,0xE0BE,5),(0xE0E4,0xE0F4,1)]:
   for variant,rom in [('normal',old),('nohp',new)]:
    c=cpu(rom,1,entry,player);c.bus.wram[0x10E+player]=hp;until(c,1,end);assert c.bus.wram[0x10E+player]==(hp if variant=='nohp' else max(0,hp-delta));assert c.s==0x1ff
checks.append({'name':'both native equipment HP drains, both players, old/new','cases':24})

for player in (0,1):
 for variant,rom in [('normal',old),('nohp',new)]:
  c=cpu(rom,0,0x9EE8,y=player);c.bus.wram[0x10E+player]=25;until(c,0,0x9EF8);assert c.bus.wram[0x10E+player]==(25 if variant=='nohp' else 5)
  c=cpu(rom,2,0xFEC5,x=player);c.bus.wram[0x10E+player]=25;until(c,2,0xFEE2);assert c.bus.wram[0x10E+player]==(25 if variant=='nohp' else 0)
  c=cpu(rom,0x20,0x9440,y=player);c.bus.wram[0x10E+player]=25;until(c,0x20,0x9451);assert c.bus.wram[0x10E+player]==(25 if variant=='nohp' else 0)
  c=cpu(rom,0x20,0x8618);c.bus.wram[0x1BA6]=player;c.bus.wram[0x10E+player]=25;until(c,0x20,0x8623);assert c.bus.wram[0x10E+player]==(25 if variant=='nohp' else 0);assert c.bus.wram[0xE11+player]==0x11
checks.append({'name':'special weapon, train, optimized lethal effect/item, both players','cases':16})

# All five non-player actor slots still lose HP and die at zero.
for slot in range(2,7):
 for hp in (1,25,255,512,2000):
  for damage in (1,25,255):
   values=[]
   for rom in (old,new):
    c=cpu(rom,0,0x9EA6,x=slot);w=c.bus.wram;w[0x12A6+slot]=hp&255;w[0x12AD+slot]=hp>>8;w[0x1BA9+slot]=damage;until(c,0,0x9EC0);values.append(w[0x12A6+slot]+256*w[0x12AD+slot]);assert w[0x10E:0x110]==b'\x00\x00'
   assert values==[max(0,hp-damage)]*2,(slot,hp,damage,values)
for slot in range(2,7):
 c=cpu(new,0x20,0x9440,y=slot);c.bus.wram[0x12A6+slot]=25;c.bus.wram[0x12AD+slot]=2;until(c,0x20,0x9451);assert c.bus.wram[0x12A6+slot]==c.bus.wram[0x12AD+slot]==0
checks.append({'name':'all5 NPC/enemy damage and lethal effect unchanged','cases':155})

# The exact input guard rejects a different ROM. Duplicate run is deterministic.
for data in (new,old[:-1],bytes([old[0]^1])+old[1:]):
 try:install(data)
 except ValueError:pass
 else:raise AssertionError('wrong input accepted')
assert install(old)[0]==new
result={'status':'pass','target':{'sha256':hashlib.sha256(new).hexdigest(),'crc32':f'{zlib.crc32(new):08X}'},'changed_bytes':len(diff),'patch_sites':len(PATCHES),'checks':checks,'wrong_source_rejected':3,'scope':'native CPU consumer tests, not cycle-accurate PPU or all story routes'}
args.report.parent.mkdir(parents=True,exist_ok=True)
args.report.write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result,indent=2))
