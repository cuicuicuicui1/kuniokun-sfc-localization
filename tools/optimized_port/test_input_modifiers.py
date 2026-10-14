from runtime_paths import source_tree
from pathlib import Path
import json,sys,os,itertools,hashlib
ROOT=Path(__file__).resolve().parent;SRC=source_tree();sys.path.insert(0,str(SRC));os.chdir(SRC)
from dialogue_model import make_cpu
m=json.loads((ROOT/'port-manifest.json').read_text(encoding='utf-8'));opt=Path(m['inputs']['opt']['path']).read_bytes();port=(ROOT/'candidate-ui.sfc').read_bytes()
def run(rom,bank,pc,setup):
 c=make_cpu(rom);c.pbr=bank;c.db=3;c.pc=pc;c.s=0x1ff;c.x=0;c.y=0;c.a=0x66a0;c.bus.wram[0x1ba6]=setup['player'];c.bus.wram[0xf0]=setup['lock'];c.bus.wram[0xf01+setup['player']]=setup['kind'];c.bus.wram[0x31a+setup['player']]=setup['held'];c.bus.wram[0x318+setup['player']]=setup['edge'];c.bus.wram[0x78:0x7a]=bytes([17,39]);c.c=setup['carry']
 c.push8(0);c.push8(0xdf);c.push8(0xff)
 for _ in range(5000):
  if (c.pbr,c.pc)==(0,0xe000):break
  c.step()
 else:raise AssertionError('modifier helper timeout')
 assert c.s==0x1ff
 # Stack includes relocated return addresses, excluded. DP mirror writes and
 # actor attribute data must match source optimization exactly.
 return {'registers':[c.pbr,c.pc,c.a,c.x,c.y,c.db,c.d,c.s,c.m8,c.x8,c.n,c.z,c.c], 'ram':bytes(c.bus.wram[:0x1f0])+bytes(c.bus.wram[0x200:0x1f00])}
count=0
for player,kind,held,edge,lock,carry in itertools.product((0,1),range(21),(0,0x60,0x70),(0,1,2,4,8,0x20),(0,1),(False,True)):
 setup=locals().copy();a=run(opt,0x20,0x9170,setup);b=run(port,0x35,0xb170,setup);assert a==b,(player,kind,held,edge,lock,carry);count+=1
result={'status':'pass','candidate_sha256':hashlib.sha256(port).hexdigest(),'cases':count,'actor_types':21,'player_slots':2,'held_masks':[0,0x60,0x70],'edge_masks':[0,1,2,4,8,0x20],'locks':[0,1],'carry_inputs':2,'scope':'native L+R+X modifier entry and original ROM comparison; separate from friendly-fire menu; CPU model only'}
(ROOT/'input-modifier-parity.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(result)
