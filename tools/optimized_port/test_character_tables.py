"""Kunio-specific character-table boundary and non-text preservation guard."""
from pathlib import Path
import sys
START=0x4802A
END=0x4A04A
RECORDS=514
def validate_character_tables(target,source):
    for label,data in [('target',target),('source',source)]:
        if len(data)<0x50000 or len(data)%0x8000:
            raise ValueError(label+': expected an unheadered LoROM')
        a=int.from_bytes(data[0x48000:0x48002],'little')
        b=int.from_bytes(data[0x48002:0x48004],'little')
        if (a,b)!=(0x802A,0xA04A) or (b-a)!=RECORDS*16:
            raise ValueError(label+': native character-table boundary changed')
    bad=[]
    for i in range(RECORDS):
        o=START+i*16
        bad.extend(j for j in range(o+4,o+16) if target[j]!=source[j])
    bad.extend(j for j in range(END,0x50000) if target[j]!=source[j])
    if bad:
        raise ValueError(f'non-name parameters differ in {len(bad)} bytes; first ROM offset 0x{bad[0]:06X}')
    return {'records':RECORDS,'table_start':START,'table_end':END,'trailing_parameters_bytes':0x50000-END,'mismatches':0}
if __name__=='__main__':
    root=Path(__file__).resolve().parent
    rom=Path(sys.argv[1]) if len(sys.argv)>1 else root/'kuniokun_cn.smc'
    base=Path(sys.argv[2]) if len(sys.argv)>2 else root/'dl/roms/kuniokun__SF8127.smc'
    print('PASS',validate_character_tables(rom.read_bytes(),base.read_bytes()))
