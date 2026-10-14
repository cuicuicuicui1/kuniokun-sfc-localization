from runtime_paths import source_tree
from pathlib import Path
import json,sys,os,collections,hashlib
ROOT=Path(__file__).resolve().parent
SRC=source_tree();sys.path.insert(0,str(SRC));os.chdir(SRC)
from dialogue_model import make_cpu
rom=(ROOT/'candidate-ui.sfc').read_bytes();manifest=json.loads((ROOT/'port-manifest.json').read_text(encoding='utf-8'))
def call(c,pc):
 c.pbr=c.db=3;c.pc=pc;c.s=0x1ff;c.m8=c.x8=True;c.push8(0xdf);c.push8(0xff)
 for _ in range(10000):
  if (c.pbr,c.pc)==(3,0xe000):return
  c.step()
 raise AssertionError(('loader stuck',pc))
cases=[];danger=[];worst=(0,None)
for key in manifest['extended_messages']:
 mid=int(key,16)
 # Full native speaker IDs and all 15 mirrored common substitutions.
 for speaker in (0,0x11f,0x1d3,0x200,0x201):
  for common in range(0x3c,0x4b):
   c=make_cpu(rom);w=c.bus.wram;w[0x373]=0;w[0x34a:0x34c]=mid.to_bytes(2,'little');w[0x34c:0x34e]=speaker.to_bytes(2,'little');w[0x35d]=w[0x35e]=common
   call(c,0xeb68)
   for page in range(40):
    before=bytes(w[0x44a:0x550]);ptr=int.from_bytes(w[0x36a:0x36c],'little')
    call(c,0xeb9e);length=w[0x3e8];buf=bytes(w[0x3ea:0x3ea+length]);record=(key,speaker,common,page)
    if length>worst[0]:worst=(length,record)
    if length>=96 or before!=bytes(w[0x44a:0x550]):danger.append({'case':record,'length':length,'buffer':buf.hex()})
    cases.append((record,length))
    if not buf:break
   else:raise AssertionError(('parser never finishes',key,speaker,common))
result={'candidate_sha256':hashlib.sha256(rom).hexdigest(),'message_substitution_cases':len(manifest['extended_messages'])*5*15,'decoded_slices':len(cases),'max_slice_bytes':worst,'over_96_bytes':danger}
(ROOT/'buffer-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('native decode slices',len(cases),'max',worst,'>=96 bytes',len(danger));print(danger[:2])
