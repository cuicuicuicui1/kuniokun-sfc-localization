"""The typewriter must not write the live BG3 HDMA table ($03AA-$03C8).

The original loader initializes $03E7 per message. Unlike $03C4 this byte is
not inside an indirect renderer data record. The model explicitly traverses
the original HDMA table; absence of a CPU LDA $03C4 is not a safety proof.
Run against the previous ROM to see the negative case fail after one tick.
"""
from pathlib import Path
import sys
from dialogue_model import make_cpu, tick, flush

rom = Path(sys.argv[1] if len(sys.argv)>1 else 'kuniokun_cn.smc').read_bytes()
template = rom[0x1EACC:0x1EAEB]
base = 0x03AA
assert rom[0x1EACA:0x1EACC] == base.to_bytes(2,'little')
assert rom[0x1EBA6:0x1EBAF] == bytes.fromhex('9C E8 03 9C E9 03 9C E7 03'), 'loader initialization changed'

def hdma_records(w):
    p=base;line=0;records=[]
    while w[p]:
        count=w[p]&127
        records.append((line, p+1, bytes(w[p+1:p+5])))
        line += count or 128;p += 5
        assert p<=base+30, 'unexpected HDMA table extension'
    return records,p

for buttons in ((),(0x31A,),(0x31C,)):
    c=make_cpu(rom);w=c.bus.wram;w[base:base+len(template)]=template
    records,end=hdma_records(w)
    assert records[-1][:2]==(216,0x03C4) and end==0x03C8
    for f in range(60):
        for address in buttons:w[address]=0x80 if f<15 else 0
        tick(c)
        assert bytes(w[base:base+len(template)])==template, ('pace overwrote live HDMA',f,hex(w[0x03C4]),buttons)
        assert 0<=w[0x03E7]<=6, ('counter not bounded',f,w[0x03E7])
        flush(c)
print('PASS: normal/held/released ticks preserve all HDMA records, including scanline-216 H scroll; counter uses loader-owned byte $03E7')
