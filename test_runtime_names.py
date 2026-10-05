"""Real dispatch and live ownership regression, not direct entry into a stub.

Old rc3 must fail before its hidden DE branch, even though test_itemmsg passed.
HUD glyphs must survive an item/body message and the other enemy plate.
"""
import json,sys
from pathlib import Path
from dialogue_model import make_cpu, flush
ROOT=Path(__file__).resolve().parent
path=Path(sys.argv[1] if len(sys.argv)>1 else ROOT/'kuniokun_cn.smc').resolve()
rom=path.read_bytes();p=json.loads((path.parent/'cn_build_params.json').read_text(encoding='utf-8'))

# The model must preserve hidden B in M=8, matching the hardware transfer
# semantics that exposed the wrong source index in the real emulator.
c=make_cpu(rom);c.a=0x6600;c.m8=True;c.x8=False;c.set_m(0x2A)
assert c.a==0x662A,'CPU model discarded hidden accumulator B'
c.set_y(c.a);assert c.y==0x662A,'16-bit TAY ignored hidden B'
c.set_m(0);assert c.a==0x6600 and c.z,'byte LDA zero flags depend on hidden B'

def call(c,bk,pc):
    c.pbr=c.db=bk;c.pc=pc;c.s=0x1FF;c.m8=c.x8=True
    c.push8(0xDF);c.push8(0xFF)
    for _ in range(50000):
        if (c.pbr,c.pc)==(bk,0xE000):
            assert c.s==0x1FF,'ABI stack mismatch'
            return
        c.step()
    raise AssertionError('real consumer did not return')

def draw(c,codes,row,col):
    w=c.bus.wram;w[0x3E8]=len(codes);w[0x3E9]=0
    w[0x3EA:0x3EA+len(codes)]=codes;w[0x36E]=row;w[0x36F]=col
    while w[0x3E9]<len(codes):
        old=w[0x3E9]
        call(c,3,0xFA30) # original drawer entry -> actual dispatch
        w[0x3E9]=(w[0x3E9]+1)&255 # original tick's continuation
        flush(c)
        assert w[0x3E9]>old,'no progress on an empty upload queue'

# A used upload queue contains nonzero stale bytes. M=8 word-stepping copies
# only plane 0 and leaves plane 1 unchanged, which empty/zero RAM tests missed.
c=make_cpu(rom,bytes.fromhex('de69'));w=c.bus.wram
w[0xB00:0xC00]=b'\xA5'*256
w[0x36E]=5;w[0x36F]=2;w[0x12]=0xDE
call(c,3,0xFA30)
q=bytes(w[0xB00:0xC00]);target=int.from_bytes(q[:2],'little')
assert q[4:36]==rom[p.get('menu_item_glyph_rom',0x1F8000)+0x69*64:p.get('menu_item_glyph_rom',0x1F8000)+0x69*64+32],'DE word copy left stale plane-1 bytes'
assert q[40:72]==rom[p['menu_item_glyph_rom']+0x69*64+32:p['menu_item_glyph_rom']+0x69*64+64], 'DE right half source mismatch'
flush(c)
assert bytes(b for v in c.vram[target:target+16] for b in (v&255,v>>8))==q[4:36],'DE upload mismatch'

# All table IDs through the actual dispatcher, with dirty queue bytes and
# nonzero hidden B. This applies equally to acquisition and use/equip messages.
for ident in range(256):
    c=make_cpu(rom,bytes((0xDE,ident)));w=c.bus.wram
    w[0xB00:0xC00]=b'\xA5'*256
    w[0x36E]=4;w[0x36F]=1+(ident&3);w[0x12]=0xDE;c.a=0x66DE
    call(c,3,0xFA30)
    assert bytes(w[0xB04:0xB24])==rom[p['menu_item_glyph_rom']+ident*64:p['menu_item_glyph_rom']+ident*64+32],('DE selected wrong source glyph',ident)
    assert bytes(w[0xB28:0xB48])==rom[p['menu_item_glyph_rom']+ident*64+32:p['menu_item_glyph_rom']+ident*64+64],('DE right half source',ident)

# Marker C9 DE alone never proved the branch reachable.
c=make_cpu(rom,bytes.fromhex('de3cde13de73de74'));w=c.bus.wram
w[0x36E]=5;w[0x36F]=2;w[0x12]=0xDE
call(c,3,0xFA30)
assert w[0x3E9]==1 and w[0x36F]==2+p.get('item_message_width',1),'DE is shadowed by ordinary-code dispatch'
entries=flush(c)
assert any(mode==0x80 and size==32 for _,mode,size in entries),'DE failed to upload its glyph'

# Busy byte cursor defers without touching neighboring train displacement.
# 256/511 were invalid synthetic word cursors: $09E0 is NOT a high byte.
for cursor in (212,255):
    c=make_cpu(rom,bytes.fromhex('de3c'));w=c.bus.wram
    w[0x36E]=5;w[0x36F]=2;w[0x12]=0xDE
    w[0x9DF]=cursor;w[0x9E0:0x9E2]=bytes.fromhex('f8ff')
    w[0xB00:0xD00]=bytes((i&255 for i in range(512)))
    before=bytes(w[0xB00:0xD00])
    call(c,3,0xFA30)
    assert w[0x9DF]==cursor,'busy cursor changed'
    assert w[0x9E0:0x9E2]==bytes.fromhex('f8ff'),'train displacement changed'
    assert bytes(w[0xB00:0xD00])==before,'busy DE dispatch overwrote the queue'
    assert w[0x36F]==2,'busy DE dispatch advanced the visible column'

hud=p.get('hud_pairs');assert hud,'combat still borrows message name tiles'
N=p['slots']+2*p['label_sets']+p['label_name_glyphs']
message={rom[0x1F0180+i] | rom[0x1F0700+i]<<8 for i in range(2*N)}
assert not message.intersection(hud),'combat HUD / message live pair collision'
assert len(set(hud))==len(hud),'two enemy nameplates reuse a live glyph'

c=make_cpu(rom);w=c.bus.wram
records=[rom[0x4802A+i*16:0x4802E+i*16] for i in range(560)]
chosen=[records[0],next(rec for rec in records if rec[0]>=0xC0 and rec[2]>=0xC0 and rec!=records[0])]
expected={}
for plate,rec in zip((2,3),chosen):
    w[0x10]=plate;w[0x1C03+plate]=0x20;w[0x1B46+plate*4:0x1B4A+plate*4]=rec
    call(c,0,0x8C34);flush(c)
    base=int.from_bytes(rom[0xC2C+plate*2:0xC2E+plate*2],'little')-4
    for g in (0,1):
        for half in (0,1):
            idx=(plate&1)*2+g+half*(len(hud)//2);tile=hud[idx]
            assert c.vram[base-32+g*2+half]==(0x2400|tile),'HUD top half placed on lower row'
            assert c.vram[base+g*2+half]==(0x2400|(tile+1)),'HUD bottom half placed on upper row'
        off=(p.get('pool_bank0',0x21)+rec[g*2]-0xC0)*0x8000+rec[g*2+1]*64
        for half in (0,1):
            index=(plate&1)*2+g+half*(len(hud)//2)
            t=hud[index];data=rom[off+half*32:off+half*32+32]
            expected[t]=[int.from_bytes(data[j:j+2],'little') for j in range(0,32,2)]
    for t,words in expected.items():assert c.vram[0x6000+t*8:0x6000+t*8+16]==words,'second plate overwrote the first'
# Exercises item first in a row AND all four consecutive columns.
for row in (4,5):
    w[0x12]=0xDE
    # draw() loads the dispatch code before each real entry below.
    codes=bytes.fromhex('de3cde13de73de74');w[0x3E8]=len(codes);w[0x3E9]=0
    w[0x3EA:0x3EA+len(codes)]=codes;w[0x36E]=row;w[0x36F]=0
    while w[0x3E9]<len(codes):
        w[0x12]=w[0x3EA+w[0x3E9]]
        call(c,3,0xFA30);w[0x3E9]+=1;flush(c)
    assert w[0x36F]==4*p.get('item_message_width',1),'item name width/ID consumption mismatch'
    for t,words in expected.items():assert c.vram[0x6000+t*8:0x6000+t*8+16]==words,'item message overwrote battle HUD'
# Body glyphs use their entire reserved pool independently of the HUD.
for ch,(page,ident) in p['cell'].items():
    w[0x3E8]=2;w[0x3E9]=0;w[0x3EA:0x3EC]=bytes((0xC0+page,ident));w[0x12]=0xC0+page;w[0x36E]=4;w[0x36F]=6
    call(c,3,0xFA30);flush(c)
for t,words in expected.items():assert c.vram[0x6000+t*8:0x6000+t*8+16]==words,'body text overwrote battle HUD'
# Exercise the OUTER HUD consumer ($00:8A96), not only its cell callee.
# Two dirty enemy plates need more than one queue. The allocator must defer a
# whole plate, leave its bit $80 set, and complete it after the actual NMI
# read-cursor protocol. The old 82-byte reservation falsely marked it clean.
assert rom[0xAE6]==0xE2,'outer HUD reservation omits Chinese glyph payloads'
c=make_cpu(rom);w=c.bus.wram
for plate,rec in zip((2,3),chosen):
    w[0x1C03+plate]=0xA0
    w[0x1B46+plate*4:0x1B4A+plate*4]=rec
for attempt in range(3):
    c.pbr=c.db=0;c.pc=0x8A96;c.s=0x1FF;c.m8=c.x8=True
    c.push8(0);c.push8(0xDF);c.push8(0xFF)
    for _ in range(20000):
        if (c.pbr,c.pc)==(0,0xE000):break
        c.step()
    else:raise AssertionError('outer HUD consumer did not return')
    assert c.s==0x1FF,'outer HUD stack mismatch'
    cursor=int.from_bytes(w[0x9DF:0x9E1],'little')
    assert cursor<=255,'outer HUD queue overflow'
    if attempt==0:assert w[0x1C05]&0x80 and not (w[0x1C06]&0x80),'second plate not deferred intact'
    flush(c)
    w[0x9DF:0x9E1]=cursor.to_bytes(2,'little');w[0x9DD]=cursor
    if not (w[0x1C05]|w[0x1C06])&0x80:break
else:raise AssertionError('deferred HUD never became clean')
for plate,rec in zip((2,3),chosen):
    base=int.from_bytes(rom[0xC2C+plate*2:0xC2E+plate*2],'little')-4
    for g in (0,1):
        off=(p['pool_bank0']+rec[g*2]-0xC0)*0x8000+rec[g*2+1]*64
        for half in (0,1):
            tile=hud[(plate&1)*2+g+half*(len(hud)//2)]
            want=[int.from_bytes(rom[off+half*32+j:off+half*32+j+2],'little') for j in range(0,32,2)]
            assert c.vram[0x6000+tile*8:0x6000+tile*8+16]==want,'outer HUD marked an unuploaded glyph clean'
            assert c.vram[base-32+g*2+half]==0x2400|tile,'outer HUD upper cell mismatch'
            assert c.vram[base+g*2+half]==0x2400|(tile+1),'outer HUD lower cell mismatch'

print('PASS: real DE dispatch; two-enemy outer HUD retry/lifetime; item row-start/columns; all body glyphs preserve both combat nameplates')
