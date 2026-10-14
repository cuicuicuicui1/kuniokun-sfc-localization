from pathlib import Path
import json,hashlib,sys,os
ROOT=Path(__file__).resolve().parent
from runtime_paths import source_tree
SRC=source_tree();sys.path.insert(0,str(SRC));os.chdir(SRC)
from dis65 import disasm
m=json.loads((ROOT/'port-manifest.json').read_text(encoding='utf-8'));opt=Path(m['inputs']['opt']['path']).read_bytes();jp=Path(m['inputs']['jp']['path']).read_bytes();rom=(ROOT/'candidate-ui.sfc').read_bytes();hooks=[]
for rel in m['optimization_relocations']:
 off=rel['source']
 if off>=0x100000:continue
 raw=opt[off:off+4];bk=off//0x8000;addr=0x8000+off%0x8000;new=rom[off:off+4]
 _,n,label=next(iter(disasm(opt,bk,addr,1,m8=True,x8=True)));assert n==4 and raw[0] in [0x22,0x5c]
 target=(raw[3],int.from_bytes(raw[1:3],'little'));dest=({0x20:0x35,0x22:0x36}[target[0]],target[1]+0x2000)
 assert (new[3],int.from_bytes(new[1:3],'little'))==dest
 hooks.append({'rom_offset':f'{off:06X}','cpu_source':f'{bk:02X}:{addr:04X}','jp_bytes':jp[off:off+4].hex(),'optimized_instruction':label,'target_old':f'{target[0]:02X}:{target[1]:04X}','target_port':f'{dest[0]:02X}:{dest[1]:04X}','opcode_retained':new[0]==raw[0],'native_width_assumption':'M8/X8; cold observation for visited roots recorded separately'})
assert len(hooks)==46
# Addresses must be described by their CPU locations as well as ROM offsets.
ins=json.loads((ROOT/'decoded-instructions.json').read_text());refs=[i for i in ins if i['bank']==0x20 and i['length']==3 and int.from_bytes(bytes.fromhex(i['raw'])[1:3],'little')>=0x8000]
report={'status':'pass','candidate_sha256':hashlib.sha256(rom).hexdigest(),'source_sha256':hashlib.sha256(opt).hexdigest(),'native_hook_count':len(hooks),'hooks':hooks,'reachable_instruction_count':len(ins),'source_widths_observed':sorted(set((i['m8'],i['x8']) for i in ins)),'bank20_high_absolute_operands':refs,'notes':['Code/data parity guard separately reconstructs complete declared payload instead of accepting any changed opcode inside a broad allocation.','Original-bank source diff classifier records every byte but is not a proof of natural full-game behavior.','Unvisited hook roots remain static/model evidence only.']}
(ROOT/'native-hook-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('PASS',len(hooks),'native hook operands and opcodes,',len(ins),'reachable instructions')
