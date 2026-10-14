"""Optional no-HP-loss variant of the exact optimized Chinese rc2 ROM.
No font or localization build is run. Never overwrites the source/output.
"""
from pathlib import Path
import argparse,hashlib,json,zlib
SHA='2129698c8e9f8d438b2a4480b2c764a965e5203e0c78af83d7b712c6136299d6'
SIZE=0x400000
# Final physical offsets and complete native opcode guards.
PATCHES=[
 (0x1E8A,'DD A9 1B','4C 9B 9E','player battle damage: keep current HP, retain native hit/HUD update'),
 (0x1EF5,'99 0E 01','EA EA EA','special weapon self-damage'),
 (0xE0BB,'9D 0E 01','EA EA EA','equipment HP drain -5'),
 (0xE0F1,'9D 0E 01','EA EA EA','equipment HP drain -1'),
 (0x17ECB,'9D 0E 01','EA EA EA','native train player HP-zero path; enemy kill remains'),
 (0x10061B,'9E 0E 01','EA EA EA','optimized player HP-zero item path'),
 (0x101446,'99 0E 01','EA EA EA','optimized lethal effect player branch; enemy branch remains'),
]

def install(raw):
 if len(raw)!=SIZE or hashlib.sha256(raw).hexdigest()!=SHA:raise ValueError('requires exact optimized localization rc2 (CRC32 1F37BC30)')
 rom=bytearray(raw);writes=[]
 for off,old,new,label in PATCHES:
  expected=bytes.fromhex(old);replacement=bytes.fromhex(new)
  if rom[off:off+len(expected)]!=expected:raise ValueError(f'consumer bytes changed at {off:06X}')
  assert len(expected)==len(replacement)
  rom[off:off+len(replacement)]=replacement;writes.append({'offset':off,'cpu':f'{off//32768:02X}:{32768+off%32768:04X}','old':old,'new':new,'purpose':label})
 rom[0x7FDC:0x7FE0]=bytes(4);chk=(sum(rom)+510)&65535;rom[0x7FDC:0x7FE0]=(chk^65535).to_bytes(2,'little')+chk.to_bytes(2,'little');assert sum(rom)&65535==chk
 return bytes(rom),writes

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--report',required=True,type=Path);a=p.parse_args()
 source=a.source.resolve();output=a.output.resolve();report=a.report.resolve()
 if output.exists() or report.exists() or len({source,output,report})!=3:raise ValueError('output/report exists or aliases an input')
 raw=source.read_bytes();rom,writes=install(raw)
 output.parent.mkdir(parents=True,exist_ok=True);report.parent.mkdir(parents=True,exist_ok=True)
 with output.open('xb') as f:f.write(rom)
 result={'status':'candidate','variant':'v2.0-rc2-nohp','source':{'sha256':SHA,'crc32':'1F37BC30','size':SIZE},'target':{'sha256':hashlib.sha256(rom).hexdigest(),'crc32':f'{zlib.crc32(rom):08X}','size':len(rom)},'writes':writes,'scope':'player HP loss from combat, HP-draining equipment, native train and optimized lethal effect; original healing/init/load and enemy damage retained'}
 with report.open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
