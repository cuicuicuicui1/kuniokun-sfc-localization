from runtime_paths import source_tree
"""Execute the original patched combat callers; compare source optimizer with port.
This CPU model checks dispatch/ABI only, not AI, NMI timing or natural-route play.
"""
from pathlib import Path
import sys,os,json,hashlib,itertools
ROOT=Path(__file__).resolve().parent
SRC=source_tree()
sys.path.insert(0,str(SRC));os.chdir(SRC)
from dialogue_model import make_cpu
m=json.loads((ROOT/'port-manifest.json').read_text(encoding='utf-8'))
opt=Path(m['inputs']['opt']['path']).read_bytes();port=(ROOT/'candidate-ui.sfc').read_bytes()
assert hashlib.sha256(opt).hexdigest()==m['inputs']['opt']['sha256']
assert hashlib.sha256(port).hexdigest()==json.loads((ROOT/'ui-manifest.json').read_text(encoding='utf-8'))['candidate']['sha256']
paths={'action':(7,0xF5BA,{(7,0xF5C0),(7,0xF608)}),'retreat':(7,0xF370,{(7,0xF374),(7,0xF382)}),'anger':(0,0x9F75,{(0,0x9F7F),(0,0x9F99)})}
def run(rom,path,record,flag,seed,slot):
 bk,pc,stops=paths[path];c=make_cpu(rom);c.pbr=c.db=bk;c.pc=pc;c.s=0x1FF;c.m8=c.x8=True;c.a=0x66AA;c.x=slot;c.y=2
 w=c.bus.wram;w[0x124D+slot]=record&255;w[0x1246+slot]=record>>8
 w[0xF01+slot]=opt[0x4802A+record*16+4];w[0x1490+slot]=flag
 w[0x348]=seed;w[0x349]=(seed*3+17)&255;w[0x34A:0x34E]=bytes.fromhex('55 aa 55 aa')
 for i in range(1000):
  if (c.pbr,c.pc) in stops:
   return {'continuation':[c.pbr,c.pc],'message':int.from_bytes(w[0x34A:0x34C],'little'),'speaker':int.from_bytes(w[0x34C:0x34E],'little'),'A':c.a,'X':c.x,'Y':c.y,'M8':c.m8,'X8':c.x8,'stack':c.s,'random':bytes(w[0x348:0x34A]).hex(),'db':(0x35 if c.db==0x20 else c.db)}
  c.step()
 raise AssertionError(('caller timeout',path,record,flag))
messages=set();checks=0;enhanced_records=[]
for record in range(514):
 flag=opt[0x4802A+record*16+12]
 if flag&0x80:enhanced_records.append(record)
 for path,seed,slot in itertools.product(paths,tuple(range(0,32,2)),(2,6)):
  # Cover the record's actual optimized flag, plus the other branch.
  for testflag in (flag,flag^0x80):
   a=run(opt,path,record,testflag,seed,slot);b=run(port,path,record,testflag,seed,slot)
   assert a==b,(path,record,testflag,seed,a,b)
   if testflag&0x80:
    assert b['speaker']==record,(path,record,b)
    assert b['message']<0x34C,(path,record,b)
    messages.add(b['message'])
   assert b['stack']==0x1FF
   checks+=1
result={'status':'pass','candidate':json.loads((ROOT/'ui-manifest.json').read_text(encoding='utf-8'))['candidate'],'cases':checks,'records':514,'enhanced_records':enhanced_records,'optimized_messages_selected':[f'{i:03X}' for i in sorted(messages)],'paths':list(paths),'evidence_type':'CPU model from original native hook callers; source optimizer comparison','unverified':'natural encounters, AI behavior, timing and hardware'}
(ROOT/'optimized-combat-model-checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))
