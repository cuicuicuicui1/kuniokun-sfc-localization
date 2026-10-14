from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parent
m=json.loads((ROOT/'port-manifest.json').read_text(encoding='utf-8'));opt=Path(m['inputs']['opt']['path']).read_bytes();r=(ROOT/'candidate-ui.sfc').read_bytes()
expected={0x20:bytearray(opt[0x100000:0x102008]),0x22:bytearray(opt[0x110000:0x110108])}
for rel in m['optimization_relocations']:
 src,dst=rel['source'],rel['destination']
 if src<0x100000:continue
 bank=src//0x8000;p=src%0x8000;e=expected[bank]
 if rel['kind']=='DBR':e[p+1]={0x20:0x35,0x22:0x36,0x23:0x37}[opt[src+1]]
 elif rel['kind']=='bank-relative-ROM':e[p+1:p+3]=(int.from_bytes(opt[src+1:src+3],'little')+0x2000).to_bytes(2,'little')
 elif rel['kind']=='long-reference':e[p+1:p+3]=(int.from_bytes(opt[src+1:src+3],'little')+0x2000).to_bytes(2,'little');e[p+3]={0x20:0x35,0x22:0x36,0x23:0x37}[opt[src+3]]
# These are the four deliberately changed native interfaces, with exact bytes.
expected[0x20][0x109b:0x109f]=bytes.fromhex('5c 41 f7 03')
expected[0x22][0:5]=bytes.fromhex('5c 00 a3 38 ea')
expected[0x22][0x34]=0xa0
expected[0x22][0x50:0x54]=bytes.fromhex('5c 00 a6 38')
for key,rec in m['extended_messages'].items():
 mid=int(key,16)
 if mid>=0x301:
  p=0x70+(mid-0x300)*2
  expected[0x22][p:p+2]=(0x8000+rec['rom']%0x8000).to_bytes(2,'little')
regions=[(0x1aa000,bytes(expected[0x20])),(0x1b2000,bytes(expected[0x22]))]
def validate(rom):
 for off,raw in regions:
  if rom[off:off+len(raw)]!=raw:
   i=next(i for i,x in enumerate(raw) if rom[off+i]!=x)
   raise ValueError(f'optimized relocated code/data differs at {off+i:06X}')
validate(r)
negative=0
# At least every decoded opcode, rather than only altered operands, is guarded.
for ins in json.loads((ROOT/'decoded-instructions.json').read_text()):
 off=ins['offset'];new=(0x1aa000 if ins['bank']==0x20 else 0x1b2000)+off%0x8000
 bad=bytearray(r);bad[new]^=1
 try:validate(bad)
 except ValueError:negative+=1
 else:raise AssertionError(('mutation not rejected',new))
result={'status':'pass','candidate_sha256':hashlib.sha256(r).hexdigest(),'compared_bytes':sum(len(raw) for _,raw in regions),'decoded_opcodes_mutation_rejected':negative,'explicit_native_interface_adaptations':4,'scope':'complete declared code/data payload parity after exact relocations, macros table and four specified interface changes; not runtime proof'}
(ROOT/'payload-integrity.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(result)
