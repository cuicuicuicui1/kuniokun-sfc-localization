"""Surgical UI maintenance on the exact user-supplied edited rc3 ROM.

This deliberately does not rebuild message text from older JSON: the supplied
ROM contains additional third-party edits, all of which must survive intact.
"""
from pathlib import Path
import argparse,hashlib,json,sys,zlib
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'source'))
from ui_asm import Asm,snes_of_rom
from ui_display_patch import install

def build(raw,font):
    contract=json.loads((ROOT/'input-contract.json').read_text(encoding='utf8'))
    if len(raw)!=contract['input_size'] or hashlib.sha256(raw).hexdigest()!=contract['input_sha256']:
        raise ValueError('Wrong base: requires edited 20261017 rc3, CRC32 36C8B784; no patch was written')
    if hashlib.sha256(Path(font).read_bytes()).hexdigest()!=contract['font_sha256']:
        raise ValueError('Wrong font: requires exact Ark Pixel 12px zh_cn BDF input')
    cb=SimpleNamespace(Asm=Asm,snes_of_rom=snes_of_rom,FONT_ROM=0xF8000,
                       E3_SLOTPAIR=0x1F0180,E3_SLOTHI=0x1F0700,
                       ITEM_PREFIX=0xDE,STATUS_SCRIPT=0xF9DB,
                       hud_pairs=lambda:contract['hud_pairs'])
    rom=bytearray(raw)
    meta=install(rom,cb,contract['parameters'],contract['layout'],font)
    rom[0x7FDC:0x7FE0]=bytes(4);check=(sum(rom)+510)&65535
    rom[0x7FDC:0x7FE0]=(check^65535).to_bytes(2,'little')+check.to_bytes(2,'little')
    if hashlib.sha256(rom).hexdigest()!=contract['output_sha256']:
        raise ValueError('Output differs from reviewed release; nothing was written')
    # All external pointer/text edits and the external drawer parameter survive.
    assert raw[0x184100:0x186000]==rom[0x184100:0x186000]
    assert raw[0x188000:0x190000]==rom[0x188000:0x190000]
    assert raw[0x1F582A]==rom[0x1F582A]
    assert sum(rom)&65535==check
    meta.update(input_sha256=contract['input_sha256'],sha256=contract['output_sha256'],
                crc32=f'{zlib.crc32(rom):08X}',size=len(rom),scope='Slot choice + STATUS12 repair on frozen externally edited base')
    return bytes(rom),meta

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('--font',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path);p.add_argument('--report',required=True,type=Path)
    a=p.parse_args();paths=[x.resolve() for x in [a.source,a.font,a.output,a.report]]
    if len(set(paths))!=4 or a.output.exists() or a.report.exists():
        raise ValueError('Inputs/outputs must differ; never overwrite an existing output/report')
    raw=a.source.read_bytes();before=hashlib.sha256(raw).hexdigest()
    first,meta=build(raw,a.font);second,_=build(raw,a.font)
    assert first==second
    assert hashlib.sha256(a.source.read_bytes()).hexdigest()==before
    a.output.parent.mkdir(parents=True,exist_ok=True);a.report.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_bytes(first);a.report.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8')
    print('PASS identical builds; CRC32',meta['crc32'],'SHA256',meta['sha256'])
if __name__=='__main__':main()
