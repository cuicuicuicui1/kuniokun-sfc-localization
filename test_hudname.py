"""Execute the REAL complete HUD renderer, including caller, queue and return.

The former test swallowed unknown opcodes, used glyph 0 as glyph 1's oracle,
and checked each cell with an empty queue. All three hid shipping regressions.
"""
from pathlib import Path
import sys
import json
import sim65816 as S

ROOT = Path(__file__).resolve().parent
rom = Path(sys.argv[1] if len(sys.argv)>1 else ROOT/'kuniokun_cn.smc').read_bytes()
par = json.loads((ROOT/'cn_build_params.json').read_text(encoding='utf-8'))
if rom[0xC91:0xC95] == bytes.fromhex('A4 18 B9 46'):
    assert not par.get('hudfix', False), 'metadata promises a missing HUD hook'
    print('SKIP: HUD hook is absent in this ROM')
    raise SystemExit(0)
assert rom[0xC91:0xC95] == bytes.fromhex('22 00 D0 3E'), 'HUD callee uses RTL: hook MUST be JSL, not JML'
SLOT0 = par['slots'] + 2*par.get('label_sets',2)
N = SLOT0 + par.get('label_name_glyphs',4)

def pair(gid,half):
    if par.get('hud_pairs'):
        i=(_plate & (1 if par.get('hud_orig', True) else 3))*2+gid
        return par['hud_pairs'][i+half*(len(par['hud_pairs'])//2)]
    i=SLOT0+gid+half*N
    return rom[0x1F0180+i] | rom[0x1F0700+i]<<8

def glyph(rec,gid):
    code,ident=rec[gid*2:gid*2+2]
    off=(par.get("pool_bank0",0x21)+code-0xC0)*0x8000+ident*64
    return rom[off:off+64]

def execute(rec, slot=0, cursor=0):
    global _plate
    _plate=slot
    c=S.CPU(rom);c.pc=0x8C34;c.db=0;c.x=0x5A;c.y=0x34
    w=c.bus.wr
    for i,b in enumerate(rec):w(0,0x1B46+slot*4+i,b)
    w(0,0x10,slot);w(0,0x1C03+slot,0x20)
    w(0,0x9DF,cursor);w(0,0x9E0,cursor>>8)
    w(0,0x1E,0xEF);w(0,0x1F,0xBE)
    for i in range(0x100):w(0,0xB00+i,0xA5)
    w(0,0xC00,0x6D)
    c.push8(0xF2);c.push8(0xA9)
    for _ in range(6000):
        if (c.pbr,c.pc)==(0,0xF2AA):break
        c.step()  # Unknown instructions are FAILURES, never successful returns.
    else:raise AssertionError(f'HUD did not return: PC={c.pbr:02X}:{c.pc:04X} S={c.s:04X} rec={rec.hex()} slot={slot} 17={c.bus.rd(0,0x17):02X}')
    assert c.s==0x1FF and c.db==0 and c.m8 and c.x8, 'caller ABI corrupted'
    assert c.bus.rd(0,0x1E)==0xEF and c.bus.rd(0,0x1F)==0xBE, 'scratch not restored'
    assert c.bus.rd(0,0xC00)==0x6D, 'queue overflowed into live workspace'
    end=c.bus.rd(0,0x9DF) | c.bus.rd(0,0x9E0)<<8
    assert cursor<=end<=255,(cursor,end)
    q=bytes(c.bus.rd(0,0xB00+i) for i in range(256))
    assert q[:cursor]==b'\xA5'*cursor, 'overwrote earlier queue entries'
    entries=[];i=cursor
    while i<end:
        address=int.from_bytes(q[i:i+2],'little'); mode=q[i+2];size=q[i+3]
        assert size in (2,32) and mode==0x80, f'broken queue header at {i}: {q[i:i+4].hex()}'
        assert i+4+size<=end,'partial queue entry'
        entries.append((address,q[i+4:i+4+size]));i+=4+size
    assert i==end
    want_glyphs={}
    want_cells=[]
    base=int.from_bytes(rom[0xC2C+slot*2:0xC2E+slot*2],'little')-4
    for k in range(4):
        gid=k//2;half=k%2
        if rec[gid*2]>=0xC0:
            t=pair(gid,half)
            assert t<256,'HUD caller cannot encode high tile bits'
            lower,upper=t+1,t
            if half==0:
                data=glyph(rec,gid)
                for h in range(2):want_glyphs[0x6000+pair(gid,h)*8]=data[h*32:(h+1)*32]
        else:
            lower=rom[0x1FA9E+rec[k]];upper=rom[0x1FB9E+rec[k]]
        want_cells += [(base+k,bytes((lower,0x24))),(base+k-32,bytes((upper,0x24)))]
    cells=[e for e in entries if len(e[1])==2]
    assert cells==want_cells, 'caller cell header/data was overwritten or misplaced'
    uploads=[e for e in entries if len(e[1])==32]
    for address,data in uploads:
        assert address in want_glyphs and data==want_glyphs[address], 'wrong glyph/page/half uploaded'
    if cursor==0:
        assert dict(uploads)==want_glyphs,'missing second glyph or non-Chinese blank misdecoded'
    return end,len(uploads)

count=0
for i in range(560):
    rec=rom[0x4802A+i*16:0x4802E+i*16]
    execute(rec,slot=i%4);count+=1
rec=rom[0x4802A:0x4802E]
for cursor in (0,8,32,40,64,80,120,136,160,200):execute(rec,cursor=cursor)
for rec in (bytes.fromhex('00 00 47 26'),rom[0x4802A:0x4802C]+b'\0\0',b'\0\0'+rom[0x4802A:0x4802C]):execute(rec)
print(f'PASS: {count} real name records + queue boundaries + kana/blank mixtures; complete caller returns, all queue entries and both glyphs checked')
