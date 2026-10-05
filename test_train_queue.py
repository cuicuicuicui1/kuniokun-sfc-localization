"""Keep byte-sized text queue cursors separate from live train/graphics state.

$09DD is NMI's byte read cursor, $09DF is the byte append cursor. $09DE
belongs to the other graphics queue and $09E0/$09E1 hold train displacement.
The original train updater ($00:FC75) and original allocator define the oracle.
Run against rc4 (with its matching sidecars) to reproduce the old failure; do
not suppress that assertion or treat this model as a full story playthrough.
"""
from pathlib import Path
import json,sys
from dialogue_model import make_cpu, flush
from cnbuild5 import Asm
import sim65816 as S
root=Path(__file__).resolve().parent
path=Path(sys.argv[1] if len(sys.argv)>1 else root/'kuniokun_cn.smc')
rom=path.read_bytes();params=json.loads((path.parent/'cn_build_params.json').read_text(encoding='utf-8'))

assert rom[0x1AB6:0x1AD1] == bytes.fromhex('48 AD DD 09 CD DF 09 F0 08 B0 06 68 18 6D DF 09 6B 68 9C DD 09 9C DF 09 18 6B 8D'), 'original byte allocator changed'
assert rom[0x7C75:0x7C78] == bytes.fromhex('8D E0 09'), 'original train displacement producer changed'

def call(c,bk,pc):
 c.pbr=c.db=bk;c.pc=pc;c.s=0x1FF;c.m8=c.x8=True
 c.push8(0xDF);c.push8(0xFF)
 for _ in range(50000):
  if (c.pbr,c.pc)==(bk,0xE000):
   assert c.s==0x1FF,'caller stack mismatch'
   return
  c.step()
 raise AssertionError('consumer did not return')

def neighbors(w,velocity):
 w[0x9DE]=0xA5;w[0x9E0:0x9E2]=velocity.to_bytes(2,'little')
 return bytes(w[0x9DE:0x9E2:2]),w[0x9E1]

def preserve(w,before,where):
 assert (bytes(w[0x9DE:0x9E2:2]),w[0x9E1])==before,(where,'queue code clobbered train/graphics state')

for velocity in (0,8,0xFFF8):
 for col in (0,2):
  c=make_cpu(rom,bytes.fromhex('de3c'));w=c.bus.wram
  w[0x36E]=5;w[0x36F]=col;w[0x12]=0xDE
  before=neighbors(w,velocity)
  call(c,3,0xFA30)
  assert w[0x3E9]==1,('DE retries forever on live train displacement',hex(velocity),col,w[0x3E9])
  assert w[0x36F]==col+params.get('item_message_width',1),'DE column did not advance'
  assert 0<w[0x9DF]<256,'DE did not append an upload'
  preserve(w,before,'DE')
 print('PASS item during train velocity',hex(velocity))
# Real event08 reward ($04:A3BA, message0005) copies DE B8/B9/0D.
# Train displacement may remain nonzero while its control is disabled; it is
# not a queue-busy flag. Keep this in addition to synthetic item3C tests.
for velocity in (1, 6):
 for ident in (0xB8, 0xB9, 0x0D):
  c=make_cpu(rom,bytes((0xDE,ident)));w=c.bus.wram
  w[0x36E]=0x0F;w[0x36F]=0;w[0x12]=0xDE
  before=neighbors(w,velocity)
  call(c,3,0xFA30)
  assert w[0x3E9]==1 and w[0x36F]==params.get('item_message_width',1), ('original event08 reward stalled',ident,velocity)
  assert 0<w[0x9DF]<256, 'reward upload not appended'
  preserve(w,before,'original event08 reward')
print('PASS event08 reward DE B8/B9/0D with preserved train displacement1/6')
# Exercise body row-start wipes and glyphs through the same true drawer entry.
page, ident = next(v for v in params['cell'].values() if v[1] < params['slots'])
for velocity in (8, 0xFFF8):
 for code, data in ((0x41, bytes.fromhex('4100')), (0xC0+page, bytes([0xC0+page, ident]))):
  for col in (0, 2):
   c=make_cpu(rom,data);w=c.bus.wram
   w[0x36E]=5;w[0x36F]=col;w[0x12]=code
   before=neighbors(w,velocity)
   call(c,3,0xFA30)
   assert w[0x36F]>col, 'body drawer did not advance'
   assert 0 < w[0x9DF] < 256, 'body queue cursor wrapped'
   preserve(w,before,'body')
   assert flush(c), 'empty glyph/row upload'
   preserve(w,before,'model flush')
print('PASS body glyphs / row wipes / model flush preserve neighboring state')

# A byte cursor at 248 must NOT accept an eight-byte cell and wrap to zero.
for code,data,cursor in ((0x41,b'AA',248),(0xDE,bytes.fromhex('de3c'),212)):
 c=make_cpu(rom,data);w=c.bus.wram
 w[0x36E]=5;w[0x36F]=2;w[0x12]=code;w[0x9DF]=cursor
 before=neighbors(w,0xFFF8);w[0xB00:0xD00]=b'\xa5'*512
 queue=bytes(w[0xB00:0xD00]);call(c,3,0xFA30)
 assert w[0x9DF]==cursor and w[0x36F]==2, 'full byte queue advanced/wrapped'
 assert bytes(w[0xB00:0xD00])==queue, 'full queue overwritten'
 preserve(w,before,'busy drawer')
print('PASS byte capacity: defers before 256, no queue overwrite')

# Original allocator oracle, not the patched renderer's arithmetic.
# A consumed queue is reclaimed using DD/DF alone, despite nonzero neighbors.
for velocity in (8,0xFFF8):
 for consumed in (0,240,255):
  c=S.CPU(rom);w=c.bus.wram;c.a=88;c.pc=0x9AB6;c.s=0x1FF
  w[0x9DD]=w[0x9DF]=consumed;before=neighbors(w,velocity)
  c.push8(0);c.push8(0xDF);c.push8(0xFF)
  for _ in range(100):
   if (c.pbr,c.pc)==(0,0xE000):break
   c.step()
  else:raise AssertionError('original allocator did not return')
  assert c.a&255==88 and not c.c and w[0x9DD]==w[0x9DF]==0
  assert c.s==0x1FF
  preserve(w,before,'original allocator')
print('PASS original $00:9AB6 reclaims only the two byte cursors')

# Shared helper ABI: preserve hidden accumulator B, P and 16-bit Y.
# Synthetic one-function ROM only; this does not install code into free space.
for method in ('queue_load_x','queue_store_x'):
 a=Asm(0x100);getattr(a,method)();code=a.done()
 synthetic=bytearray(b'\xff'*0x8000);synthetic[0x100:0x100+len(code)]=code
 for m8 in (False,True):
  for x8 in (False,True):
   for cursor in range(256):
    c=S.CPU(bytes(synthetic));w=c.bus.wram;c.pc=0x8100
    c.m8=m8;c.x8=x8;c.a=0xBECA;c.x=0x34 if x8 else 0x8734
    c.y=0x81 if x8 else 0x9381;c.n=c.c=c.v=c.i=True;c.z=False
    before=neighbors(w,0xFFF8);w[0x9DF]=cursor
    state=(c.a,c.y,c.s,c.m8,c.x8,c.n,c.z,c.c,c.v,c.i)
    for _ in range(30):
     if c.pc==0x8100+len(code):break
     c.step()
    else:raise AssertionError('cursor helper did not return')
    assert (c.a,c.y,c.s,c.m8,c.x8,c.n,c.z,c.c,c.v,c.i)==state, method+' ABI'
    assert c.x==(cursor if method=='queue_load_x' else (0x34 if x8 else 0x8734))
    assert w[0x9DF]==(cursor if method=='queue_load_x' else 0x34)
    preserve(w,before,method)
print('PASS cursor helper ABI: all 256 byte values, four M/X combinations')
print('PASS: train displacement independent from message queue (model evidence)')
