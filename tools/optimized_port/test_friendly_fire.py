from pathlib import Path
import sys,os,json,hashlib,itertools
ROOT=Path(__file__).resolve().parent
from runtime_paths import source_tree
SRC=source_tree();sys.path.insert(0,str(SRC));os.chdir(SRC)
from dialogue_model import make_cpu
m=json.loads((ROOT/'port-manifest.json').read_text(encoding='utf-8'));opt=Path(m['inputs']['opt']['path']).read_bytes();port=(ROOT/'candidate-ui.sfc').read_bytes()
def run(rom,bk,pc,left,right,flag,carry):
 c=make_cpu(rom);c.pbr=bk;c.db=0;c.pc=pc;c.x=0;c.a=0x6600;c.c=carry
 w=c.bus.wram;w[0xe21]=left;w[0xe22]=right;w[0x70]=flag
 for _ in range(100):
  if (c.pbr,c.pc)==(7,0xd872):break
  c.step()
 else:raise AssertionError('friendly-fire sound call not reached')
 return [c.a,c.x,c.y,c.db,c.s,c.m8,c.x8,c.n,c.z,c.c,w[0x70]]
count=0
for left,right,flag,carry in itertools.product(range(16),range(16),(0,0x80),(False,True)):
 a=run(opt,0x20,0x9058,left,right,flag,carry);b=run(port,0x35,0xb058,left,right,flag,carry);assert a==b,(left,right,flag,carry)
 assert a[-1]==(flag^0x80 if (left|right)<4 else flag),'native OR/gate/toggle behavior changed'
 count+=1
r={'status':'pass','candidate_sha256':hashlib.sha256(port).hexdigest(),'cases':count,'native_gating':'(player_action0 OR player_action1) < 4','scope':'menu command toggle and refusal branches at native sound consumer; source optimization comparison, CPU model only'}
(ROOT/'friendly-fire-parity.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(r)
