from sim65816 import CPU
cases=0
for op in (0x06,0x26):
 for width in (8,16):
  mask=(1<<width)-1;top=1<<(width-1)
  for value in (0,1,top-1,top,mask):
   for carry in (False,True):
    c=CPU(bytes((op,2))+bytes(0x7ffe));c.pc=0x8000
    c.d=0x120;c.db=0x7f;c.m8=width==8;c.a=0x66aa;c.c=carry
    c.bus.wram[0x122:0x125]=bytes((value&255,value>>8,0xa5));c.bus.wram[0x10122:0x10125]=bytes.fromhex('a5 a5 a5')
    c.step();want=((value<<1)+(1 if op==0x26 and carry else 0))&mask
    assert int.from_bytes(c.bus.wram[0x122:0x122+width//8],'little')==want
    assert c.c==bool(value&top) and c.z==(want==0) and c.n==bool(want&top)
    assert c.a==0x66aa and c.bus.wram[0x124]==0xa5 and c.bus.wram[0x10122:0x10125]==bytes.fromhex('a5 a5 a5')
    if width==8:assert c.bus.wram[0x123]==value>>8
    cases+=1
print('PASS',cases,'DP shifts: widths, bank0, carry/N/Z and neighbors')
