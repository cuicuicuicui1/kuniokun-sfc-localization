"""Finite original opcode51 ABI / scope contracts, not natural playthrough."""
from pathlib import Path
import sys
from sim65816 import CPU
from cnbuild5 import Asm
from ending_scene_patch import HOOK, ORIGINAL, SCENE_ROM, SCENE_LIMIT, build, install, INDENT_HOOK, INDENT_ORIGINAL, INDENT_ROM, build_indent
rom = Path(sys.argv[1] if len(sys.argv)>1 else 'kuniokun_cn.smc').read_bytes()
assert rom[HOOK:HOOK+4] == bytes.fromhex('22 00 DD 3E')
assert rom[SCENE_ROM:SCENE_ROM+len(build(Asm))] == build(Asm)
old=bytearray(rom);old[HOOK:HOOK+4]=ORIGINAL

def regs(c):
    return (c.a,c.x,c.y,c.s,c.d,c.db,c.m8,c.x8,c.n,c.z,c.c,c.v,c.i)

def run(blob,scene=0x27,event=0xAC,vm=0xFEB8,phase=0xAB42,hidden=0xAB,x8=True,db=7):
    c=CPU(bytearray(blob));c.pbr,c.pc=7,0x95A9;c.db=db;c.d=0;c.s=0x1FFD
    c.a=(hidden<<8)|0x51;c.x8=x8;c.x=0x45 if x8 else 0xAB45;c.y=2 if x8 else 0xCD02
    c.c=True;c.v=True;c.i=True
    m=c.bus.wram;m[0x900]=scene;m[0x1D23]=event;m[0x1D20]=vm&255;m[0x1D21]=vm>>8
    for i in range(0xDE1,0xDEF):m[i]=(i*19)&255
    m[0xDE1]=phase&255;m[0xDE2]=phase>>8
    for _ in range(100):
        if c.pbr==0 and c.pc==0x9CB7:return c
        c.step()
    raise AssertionError('native scene callee not reached')

cases=0
for phase in [0,1,2,4,0x40,0x41,0x80,0xAB42,0xFFFF]:
 for hidden in [0,0xAB]:
  for x8 in [True,False]:
   for db in [0,4,7,0x7E]:
    a=run(old,phase=phase,hidden=hidden,x8=x8,db=db);b=run(rom,phase=phase,hidden=hidden,x8=x8,db=db)
    # The hook adds its own return frame below the native JSL; normalize that
    # stack-depth difference but check every other register exactly.
    assert regs(b)[:3]+regs(b)[4:] == regs(a)[:3]+regs(a)[4:]
    assert b.s==a.s-3
    assert b.bus.wram[0xDE1:0xDE3]==bytes.fromhex('00 00')
    assert b.bus.wram[0xDE3:0xDEF]==a.bus.wram[0xDE3:0xDEF]
    assert b.bus.wram[0x300:0xDE1]==a.bus.wram[0x300:0xDE1]
    assert b.bus.wram[0xDEF:0x1FE0]==a.bus.wram[0xDEF:0x1FE0]
    cases+=1
for kwargs in [dict(scene=0x26),dict(event=0xA9),dict(event=0),dict(vm=0xFEB9),dict(vm=0xEDB8)]:
 for x8 in [True,False]:
  a=run(old,x8=x8,**kwargs);b=run(rom,x8=x8,**kwargs)
  assert regs(b)[:3]+regs(b)[4:]==regs(a)[:3]+regs(a)[4:]
  assert b.bus.wram[0x300:0x1FE0]==a.bus.wram[0x300:0x1FE0]
  cases+=1
# Simulate the callee's return only: check wrapper RTL and original handler
# continuation without pretending to model forced-blank PPU execution.
for x8 in [True,False]:
 c=run(rom,x8=x8);c.pc=0x9000
 c.bus.rom[0x1000]=0x6B  # isolated CPU copy, harmless synthetic native RTL
 for _ in range(10):
  if c.pbr==7 and c.pc==0x95AD:break
  c.step()
 else:raise AssertionError('wrapper did not return to original opcode handler')
 assert c.s==0x1FFD
 cases+=1
# F6 is a five-cell eraser/indent, not a newline. At credits only,
# skip through native CLC/RTS; ordinary F6 still arms the original eraser.
for event in [0,0xA9,0xAC]:
 for hidden in [0,0xAB]:
  c=CPU(bytearray(rom));c.pbr,c.pc=3,0xFD56;c.db=3;c.s=0x1FFD
  c.a=(hidden<<8)|0x35;c.x=0xAB45;c.y=0xCD23;c.x8=False;c.c=True
  c.bus.wram[0x1D23]=event;c.bus.wram[0x374]=0x80;c.bus.wram[0x38A]=0xA5
  # Return boundary is the original CLC/RTS for credits, FD64 SEC/RTS otherwise.
  for _ in range(80):
   if c.pbr==3 and c.pc==(0xFCE8 if event==0xAC else 0xFD63):break
   c.step()
  else:raise AssertionError('F6 consumer not reached')
  assert (c.x,c.y,c.x8,c.s)==(0xAB45,0xCD23,False,0x1FFD)
  if event==0xAC:assert c.a==(hidden<<8)|0x35 and c.bus.wram[0x374]==0x80 and c.bus.wram[0x38A]==0xA5
  else:assert c.bus.wram[0x374]==0x88 and c.bus.wram[0x38A]==5
  cases+=1
pristine=bytearray(rom);pristine[HOOK:HOOK+4]=ORIGINAL;pristine[INDENT_HOOK:INDENT_HOOK+5]=INDENT_ORIGINAL;pristine[SCENE_ROM:SCENE_LIMIT]=bytes(0x100)
install(pristine,Asm)
for variant in ['hook','reserved_tail']:
 r=bytearray(pristine);r[HOOK:HOOK+4]=ORIGINAL;r[INDENT_HOOK:INDENT_HOOK+5]=INDENT_ORIGINAL;r[SCENE_ROM:SCENE_LIMIT]=bytes(0x100)
 r[HOOK if variant=='hook' else SCENE_LIMIT-1]=0xA5
 try:install(r,Asm)
 except AssertionError:pass
 else:raise AssertionError('unsafe installation accepted '+variant)
print('PASS: %d ending scope/ABI cases; original scene JSL replayed, no APU/actor/HDMA edits'%cases)

# Independent negative: the original train initializer suppresses gameplay
# trains under the credits' cutscene flag. Phase80 is NOT a neutral reset.
c=CPU(bytearray(rom));c.pbr,c.pc,c.db,c.s=0,0xFB28,0,0x1FFD
c.bus.wram[0x1DA8]=0x20;c.bus.wram[0xDE1]=0;c.bus.wram[0xDE2]=0
c.push8(0x9D);c.push8(0xEA)
for _ in range(30):
    if c.pbr==0 and c.pc==0x9DEB:break
    c.step()
else:raise AssertionError('native suppressed train initializer did not return')
assert c.bus.wram[0xDE1:0xDE3]==bytes(2)
print('PASS: native flag20 keeps gameplay train inactive; no forced80 counterexample')
