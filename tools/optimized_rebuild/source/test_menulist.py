"""Run ORIGINAL list loader and patched $03:F95D, including carry retries.

Independent oracle uses input table bytes and expected live VRAM glyph data.
Four nonempty entries, cross-page techniques, items, row wrap, queue pressure,
scroll/reopen and the original main-command call site are included.
"""
from pathlib import Path
import json,sys
import sim65816 as S
from dialogue_model import flush
ROOT=Path(__file__).resolve().parent
path=Path(sys.argv[1] if len(sys.argv)>1 else ROOT/'kuniokun_cn.smc').resolve()
rom=path.read_bytes();par=json.loads((path.parent/'cn_build_params.json').read_text(encoding='utf-8'))
N=par['slots']+par['label_sets']*2+par['label_name_glyphs']

def flush_engine(c):
    # Model the ACTUAL NMI protocol: upload data and advance only $09DD.
    # $09DF stays committed until $00:9AB6 observes the consumed cursor.
    w=c.bus.wram
    cursor=w[0x9DF]
    entries=flush(c)
    w[0x9DF]=cursor
    w[0x9DD]=cursor&255  # $09DE belongs to the other graphics queue
    return entries


def pair(slot,half=0):
    i=slot+half*N
    return rom[0x1F0180+i]|rom[0x1F0700+i]<<8

def codes(table,ident):
    off=0x10000+int.from_bytes(rom[table+ident*2:table+ident*2+2],'little')
    end=rom.index(0xF2,off)
    return rom[off:end]

def call(c,pc,ret=0xE000):
    before=(c.bus.wram[0x9DE],bytes(c.bus.wram[0x9E0:0x9E2]))
    c.pc=pc;c.pbr=c.db=3;c.s=0x1FF;c.m8=c.x8=True
    c.push8((ret-1)>>8);c.push8((ret-1)&255)
    for _ in range(60000):
        if (c.pbr,c.pc)==(3,ret):
            assert c.s==0x1FF and c.m8 and c.x8 and c.db==3,'caller ABI not preserved'
            assert (c.bus.wram[0x9DE],bytes(c.bus.wram[0x9E0:0x9E2]))==before, 'list reader/renderer changed graphics/train state'
            return
        c.step()
    raise AssertionError('list renderer timeout')

def load(c,table,ids):
    w=c.bus.wram;w[0x40A:0x44A]=bytes(64)
    w[0x36:0x39]=(0x1CA8).to_bytes(3,'little')
    w[0x1CA8]=len(ids);w[0x1CA9:0x1CA9+len(ids)]=bytes(ids);w[0x39B]=len(ids)
    w[0x37A:0x37C]=(table-0x10000).to_bytes(2,'little')
    for n in range(4):
        w[0x39A]=n;w[0x39E]=n//2;call(c,0xF913)
    for idx,ident in enumerate(ids):
        start=(idx//2)*26+1+(idx%2)*13
        assert w[0x40A+start:0x40A+start+len(codes(table,ident))]==codes(table,ident),'real row loader lost bytes'
    for off in (0,13,26,39):assert w[0x40A+off]==0,'blank separators overwritten'

def oracle(c,table,ids,startrow):
    # IDs refer to source tables, NOT the renderer's progress markers.
    for n,ident in enumerate(ids):
        col=1+(n%2)*13;row=(startrow+n//2)&15;offset=0
        data=codes(table,ident)
        base=(rom[0x1FA7E+row]<<8)|rom[0x1FA8E+row]
        while offset<len(data):
            code=data[offset]
            slot=(row&1)*13+col//2
            if code==0xDE:
                off=par['menu_item_glyph_rom']+data[offset+1]*64
                t,u=pair(slot),pair(slot,1)
                want=[(t,rom[off:off+32]),(u,rom[off+32:off+64])]
                cells=[(col,t,t+1),(col+1,u,u+1)];offset+=2;col+=2
            elif 0xC0<=code<0xC0+par['pages']:
                off=(par.get('pool_bank0',0x21)+code-0xC0)*0x8000+data[offset+1]*64
                t,u=pair(slot),pair(slot,1)
                want=[(t,rom[off:off+32]),(u,rom[off+32:off+64])]
                cells=[(col,t,t+1),(col+1,u,u+1)];offset+=2;col+=2
            else:
                want=[];cells=[(col,rom[0x1FB9E+code],rom[0x1FA9E+code])];offset+=1;col+=1
            for x,upper,lower in cells:
                assert c.vram[base+x]==0x2400|upper,(ident,x,hex(c.vram[base+x]),hex(upper))
                assert c.vram[base+x+32]==0x2400|lower,'lower half mismatch'
            for t,g in want:
                words=[int.from_bytes(g[i:i+2],'little') for i in range(0,32,2)]
                assert c.vram[0x6000+t*8:0x6000+t*8+16]==words,('glyph upload/lifetime',ident,t)

for table,ids in [(0x1E096,[21,22,23,35]),(0x1DBC3,[1,10,48,100]),(0x1DBC3,[2,64,109,110])]:
    for startrow in (4,15):
        c=S.CPU(rom);load(c,table,ids);w=c.bus.wram;w[0x36E]=startrow
        protected=bytes(w[0x14:0x30]);frames=0
        for row in (0,1):
            w[0x39E]=row
            # Existing queue traffic must make the new renderer defer, not overwrite.
            w[0x9DF]=240;w[0x9DE]=0xA5;w[0x9E0:0x9E2]=bytes.fromhex('f8ff');w[0xB00:0xB00+240]=b'\xA5'*240
            before=bytes(w[0xB00:0xC00]);call(c,0xF95D)
            assert w[0x9DE]==0xA5 and w[0x9E0:0x9E2]==bytes.fromhex('f8ff'), 'list clobbered graphics/train neighbors'
            assert c.c and bytes(w[0xB00:0xC00])==before,'busy queue was overwritten'
            w[0x9DD:0x9E1]=bytes(4)
            for _ in range(60):
                call(c,0xF95D);assert w[0x14:0x30]==protected,'DP scratch leaked'
                frames+=1;flush_engine(c)
                if not c.c:break
            else:raise AssertionError('list row never completed')
        assert w[0x36E]==(startrow+2)&15,'row counter advanced incorrectly'
        assert all(w[0x40A+i]==0 for i in (0,13,26,39)),'progress left in blank cells'
        oracle(c,table,ids,startrow)
        # Reopening the exact same list reconstructs live glyphs from source.
        load(c,table,ids);w[0x36E]=startrow
        for row in (0,1):
            w[0x39E]=row
            for _ in range(60):
                call(c,0xF95D);flush_engine(c)
                if not c.c:break
        oracle(c,table,ids,startrow)
# Real scrolling draws ONE replacement row with $039E==0 each time.
# The other visible row must retain both its tilemap and its glyph pixels.
for table,ids in ((0x1DBC3,list(range(28,56))), (0x1E096,list(range(21,36)))):
    c=S.CPU(rom);w=c.bus.wram;startrow=14
    load(c,table,ids[:4]);w[0x36E]=startrow
    for rel in (0,1):
        w[0x39E]=rel
        for _ in range(60):
            call(c,0xF95D);flush_engine(c)
            if not c.c:break
    previous=ids[2:4];previous_row=15
    for offset in range(4,len(ids)-1,2):
        target=(previous_row+1)&15;replacement=ids[offset:offset+2]
        load(c,table,replacement);w[0x36E]=target;w[0x39E]=0
        for _ in range(60):
            call(c,0xF95D);flush_engine(c)
            if not c.c:break
        else:raise AssertionError('single-row scroll never completed')
        oracle(c,table,previous,previous_row)
        oracle(c,table,replacement,target)
        previous,previous_row=replacement,target

# All items and 15 visible techniques individually traverse loader/renderer.
for table,maximum in ((0x1DBC3,110),(0x1E096,35)):
    for ident in range(1,maximum+1):
        c=S.CPU(rom);load(c,table,[ident]);w=c.bus.wram;w[0x36E]=4;w[0x39E]=0
        for _ in range(60):
            call(c,0xF95D);flush_engine(c)
            if not c.c:break
        oracle(c,table,[ident],4)
# Static command labels are not interpreted as DE/DD list prefixes.
c=S.CPU(rom);w=c.bus.wram;w[0x40A:0x43E]=rom[0x1F743:0x1F777];w[0x36E]=4
call(c,0xF95D,0xF781);assert not c.c and w[0x36E]==5,'main command bypass failed'
assert w[0x9DF]==112,'main command queue contract changed'
print('PASS: real list loader, 4 nonempty entries, all 110 items/35 names, both rows/wrap, queue retry, DP/ABI, reopen, original command bypass')
