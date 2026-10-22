"""Incremental repair of the native slot reels on exact UI base 8890880C."""
from pathlib import Path
import argparse,hashlib,json,zlib
from slot_reels_patch import install,BASE_SHA
TARGET_SHA='facad37c1e98bef1508fe5e1fec2f0ffcfa86e1ac779ba7a0f5007f0bb7688fb'

def build(raw,original):
    rom=bytearray(raw);meta=install(rom,original)
    rom[0x7FDC:0x7FE0]=bytes(4);check=(sum(rom)+510)&65535
    rom[0x7FDC:0x7FE0]=(check^65535).to_bytes(2,'little')+check.to_bytes(2,'little')
    assert sum(rom)&65535==check
    assert hashlib.sha256(rom).hexdigest()==TARGET_SHA,'Output differs from reviewed slot repair'
    allowed=[(0x7FDC,0x7FE0),(0x1F3C9,0x1F3CD),(meta['slot_code'],meta['slot_code']+meta['slot_code_bytes'])]
    changed=[i for i,(a,b) in enumerate(zip(raw,rom)) if a!=b]
    assert all(any(lo<=i<hi for lo,hi in allowed) for i in changed)
    meta.update(input_sha256=BASE_SHA,size=len(rom),changed_bytes=len(changed),
        sha256=hashlib.sha256(rom).hexdigest(),crc32=f'{zlib.crc32(rom):08X}')
    return bytes(rom),meta

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path)
    p.add_argument('--optimization',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--report',required=True,type=Path);a=p.parse_args()
    paths=[x.resolve() for x in [a.source,a.optimization,a.output,a.report]]
    if len(set(paths))!=4 or a.output.exists() or a.report.exists():raise ValueError('Inputs/outputs must differ; existing outputs protected')
    raw=a.source.read_bytes();original=a.optimization.read_bytes()
    rom,meta=build(raw,original);second,_=build(raw,original);assert rom==second
    a.output.parent.mkdir(parents=True,exist_ok=True);a.report.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_bytes(rom);a.report.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(meta,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
