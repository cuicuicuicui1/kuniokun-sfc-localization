"""Finite CPU-model contract at the ORIGINAL AC wait consumer.

This checks the targeted teardown guard/ABI, not game/story acceptance.
python test_garage_sync.py [ROM]
"""
from pathlib import Path
import sys
from sim65816 import CPU
from cnbuild5 import Asm
from garage_story_patch import HOOK, ORIGINAL, SYNC_ROM, SYNC_LIMIT, build, install

rom = Path(sys.argv[1] if len(sys.argv) > 1 else 'kuniokun_cn.smc').read_bytes()
assert rom[HOOK:HOOK+5] == bytes.fromhex('5C 00 DC 3E EA'), 'missing garage sync hook'
code = build(Asm)
assert rom[SYNC_ROM:SYNC_ROM+len(code)] == code, 'garage sync bytecode differs'
assert SYNC_LIMIT <= 0x1F6000
old = bytearray(rom); old[HOOK:HOOK+5] = ORIGINAL


def regs(c):
    return (c.a,c.x,c.y,c.s,c.d,c.db,c.m8,c.x8,c.n,c.z,c.c,c.v,c.i)


def run(blob, *, battle=0, teardown=0, spawn=0, enemies=0,
        event=0x95, vm=0xB94B, scene=0x4B, threshold=0, hidden=0xA5,
        entry=0x8E0A, stop_entry=False):
    c=CPU(blob);c.pbr,c.pc=7,entry;c.db=4;c.s=0x1FFD
    c.a=hidden<<8;c.x=0x36;c.y=0x21;c.c=True;c.v=True;c.i=True
    m=c.bus.wram
    m[0x900]=scene;m[0x1D23]=event;m[0x1D20]=vm&255;m[0x1D21]=vm>>8
    m[0x1D25]=3;m[0x1DA9]=threshold
    m[0x122B]=battle;m[0x122D]=teardown;m[0x8D7]=spawn
    # Actual companion slots remain active but NOT combat members.
    for i in [2,3]:m[0xE01+i]=0x81;m[0x1331+i]=i-1
    for i in range(4,4+enemies):m[0xE01+i]=0x81;m[0x122F+i]=1
    for _ in range(300):
        if c.pbr==7 and c.pc in ((0x8E1A,) if stop_entry else (0x8E1F,0x8E20)):
            return c
        c.step()
    raise AssertionError('wait consumer failed to reach a native exit')

cases=0
for hidden in [0x00,0xAB]:
    for busy in [(0,0,0),(1,0,0),(0,1,0),(0,9,0),(0,0xB,0),(0,0,1),(1,0xB,1)]:
        kw=dict(battle=busy[0],teardown=busy[1],spawn=busy[2],hidden=hidden)
        before=run(old,**kw,stop_entry=True)
        original=run(old,**kw);got=run(rom,**kw)
        assert original.pc==0x8E1F, 'original does not wait for teardown'
        if any(busy):
            assert got.pc==0x8E20 and got.bus.wram[0x1D25]==3
            assert regs(got)==regs(before), 'busy exit clobbered caller ABI'
            assert got.bus.wram[0x300:0x1D20]==before.bus.wram[0x300:0x1D20], 'guard edited actors/door/event data'
        else:
            assert got.pc==0x8E1F and got.bus.wram[0x1D25]==2
            assert regs(got)==regs(original), 'replayed original wait success differs'
        cases+=1
for kw in [dict(scene=0x4C),dict(event=0x92),dict(event=0x97),dict(vm=0xB98E),
           dict(vm=0xB84B),dict(threshold=1),dict(enemies=1),dict(enemies=3)]:
    for hidden in [0,0xAB]:
        a=run(old,battle=1,teardown=9,hidden=hidden,**kw)
        b=run(rom,battle=1,teardown=9,hidden=hidden,**kw)
        assert (b.pc,regs(b),b.bus.wram[0x1D25])==(a.pc,regs(a),a.bus.wram[0x1D25]), ('unrelated wait changed',kw)
        cases+=1
# The hook itself must not truncate the caller's 16-bit X/Y while observing
# M8. Start at the hook, not at LDY #02 in an X8-only original consumer.
for busy in [0,9]:
    c=CPU(rom);c.pbr,c.pc=7,0x8E1A;c.db=4;c.s=0x1FFD
    c.a=0xAB00;c.x=0xAB36;c.y=0xCD21;c.x8=False
    m=c.bus.wram;m[0x900]=0x4B;m[0x1D23]=0x95;m[0x1D20]=0x4B;m[0x1D21]=0xB9;m[0x122D]=busy;m[0x1D25]=3
    for _ in range(100):
        if c.pbr==7 and c.pc in [0x8E1F,0x8E20]:break
        c.step()
    else:raise AssertionError('direct hook did not exit')
    assert (c.x,c.y,c.x8,c.s)==(0xAB36,0xCD21,False,0x1FFD)
    cases+=1
# Negative installer controls: reject an occupied reserved page or an
# unexpected consumer. Do not silently overwrite earlier patches/data.
pristine=bytearray(rom);pristine[HOOK:HOOK+5]=ORIGINAL
pristine[SYNC_ROM:SYNC_LIMIT]=bytes(SYNC_LIMIT-SYNC_ROM)
expected=install(pristine,Asm)
assert expected['bytes']==len(code) and pristine[SYNC_ROM:SYNC_ROM+len(code)]==code
for changed in ['site','page_tail']:
    image=bytearray(rom);image[HOOK:HOOK+5]=ORIGINAL
    image[SYNC_ROM:SYNC_LIMIT]=bytes(SYNC_LIMIT-SYNC_ROM)
    if changed=='site':image[HOOK]=0xEA
    else:image[SYNC_LIMIT-1]=0xA5
    try:install(image,Asm)
    except AssertionError:pass
    else:raise AssertionError('unsafe install accepted '+changed)
print(f'PASS: {cases} original-consumer/ABI cases; teardown busy retains AC wait, unrelated scenes/counts unchanged, no NPC/door edits')
