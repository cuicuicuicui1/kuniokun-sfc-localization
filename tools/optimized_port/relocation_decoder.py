"""Decode reachable optimization instructions before relocating operands.
Input widths derive from native hook sites (8-bit A/X); REP/SEP and branches
are tracked per path. Native calls keep their original caller contract.
"""
from collections import deque
from dis65 import disasm,MODES

def decode_payload(rom, roots, spans):
    queue=deque((bank,addr,True,True) for bank,addr in sorted(roots))
    seen=set(); decoded={}; failures=[]
    def covered(bank,addr):
        return bank in spans and any(lo<=addr-0x8000<hi for lo,hi in spans[bank])
    def add(bank,addr,m,x):
        if covered(bank,addr): queue.append((bank,addr,m,x))
    while queue:
        bank,pc,m,x=queue.popleft()
        if (bank,pc,m,x) in seen: continue
        seen.add((bank,pc,m,x))
        assert covered(bank,pc),('unknown entry point',bank,pc)
        off=bank*0x8000+pc-0x8000
        op=rom[off]
        assert op not in (0,2,0xdb),('reachable trap/data',hex(off))
        _,size,text=next(iter(disasm(rom,bank,pc,1,m8=m,x8=x)))
        raw=rom[off:off+size]
        record={'offset':off,'bank':bank,'address':pc,'length':size,'m8':m,'x8':x,'text':text,'raw':raw.hex()}
        if off in decoded:
            assert decoded[off]['length']==size,('ambiguous instruction width',hex(off))
        else:decoded[off]=record
        if op in (0xc2,0xe2):
            if raw[1]&0x20:m=op==0xe2
            if raw[1]&0x10:x=op==0xe2
        assert op!=0x28,('PLP needs explicit saved flags flow',hex(off))
        if op in (0x60,0x6b,0x40):continue
        if op in (0x10,0x30,0x50,0x70,0x90,0xb0,0xd0,0xf0,0x80):
            delta=int.from_bytes(raw[1:2],'little',signed=True)
            add(bank,(pc+size+delta)&0xffff,m,x)
            if op==0x80:continue
        if op==0x82:
            add(bank,(pc+size+int.from_bytes(raw[1:3],'little',signed=True))&0xffff,m,x);continue
        if op in (0x4c,0x20):
            add(bank,int.from_bytes(raw[1:3],'little'),m,x)
            if op==0x4c:continue
        if op in (0x5c,0x22):
            add(raw[3],int.from_bytes(raw[1:3],'little'),m,x)
            if op==0x5c:continue
        assert op not in (0x6c,0x7c,0xdc),('indirect code target requires explicit roots',hex(off))
        add(bank,pc+size,m,x)
    occupied={}
    for off,r in sorted(decoded.items()):
        for b in range(off,off+r['length']):
            assert b not in occupied,('overlapping instruction boundary',hex(off),hex(occupied.get(b,0)))
            occupied[b]=off
    return decoded
