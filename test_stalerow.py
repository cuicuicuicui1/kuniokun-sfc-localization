"""Regression: F2 + blank filler may not erase the freshly written prior line.

Runs the real tick and drawer, then applies queued VRAM writes. The old
STALEROW delta=1 heuristic failed this lifecycle even though its isolated
stub tests passed. Exercise explicit F8 clearing separately with test_menuclose.
"""
from pathlib import Path
import sys
from dialogue_model import make_cpu,tick,flush

rom=Path(sys.argv[1] if len(sys.argv)>1 else 'kuniokun_cn.smc').read_bytes()
for row in (0,4,14,15):
    c=make_cpu(rom,[0x01,0x01,0x01,0xF2]); w=c.bus.wram
    w[0x36E]=w[0x391]=row
    for _ in range(40):
        tick(c);flush(c)
        if w[0x3E9]==3: break
    assert w[0x3E9]==3, "fixture failed to draw three characters"
    addr=0x7C00+row*64+3
    positions=[addr+i+d for d in (0,32) for i in range(3)]
    before=[c.vram[p] for p in positions]
    assert any(v&0x3FF for v in before), ('fixture did not draw',row,before)
    w[0x31A]=0
    for _ in range(40):
        tick(c);flush(c)
        after=[c.vram[p] for p in positions]
        assert after==before, ('fresh line erased by newline filler',row,before,after)
        if w[0x36E]==(row+1)&15 and w[0x36F]>=10: break
    else: raise AssertionError('fixture did not reach blank filler')
    assert w[0x36E]==(row+1)&15, ('newline did not advance row',row,w[0x36E])
    print('PASS: fresh row %d survives F2 + next-row blank filler'%row)
