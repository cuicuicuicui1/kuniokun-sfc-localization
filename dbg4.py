import json, sim65816, cnbuild5 as cb, kuniokun_map as km, mos65xx
BASE='C:/Users/<user>/.zcode/workspace/default/sfc-recon'
rom=open(cb.OUT_ROM,'rb').read()
addr=json.load(open(BASE+'/cn_addr_map.json',encoding='utf-8'))
CTRL_SITES=tuple(i.address for i in mos65xx.disassemble(rom[0x01FC9E:0x01FD90], address=0x8000+(0x01FC9E%0x8000)) if i.mnemonic=='rts')
RTS=(0x825B,0x8304)
a=addr['01AF34']; msg=bytearray(); j=a
while rom[j]!=0xF2: msg.append(rom[j]); j+=1
print('msg len',len(msg),' '.join('%02X'%b for b in msg))
row=col=0; i=0; cells={}
while i<len(msg):
    code=msg[i]
    cpu=sim65816.CPU(rom); cpu.pbr=cb.E3_DRAWER//0x8000; cpu.pc=0x8000+(cb.E3_DRAWER%0x8000)
    cpu.m8=cpu.x8=True; cpu.db=0x03
    w=cpu.bus.wram
    w[0x03EA:0x03EA+len(msg)]=msg; w[0x03E8],w[0x03E9]=len(msg),i
    w[0x036E],w[0x036F],w[0x09DF]=row,col,0; w[0x12]=code; cpu.a=code
    if code>=0xF0:
        cpu.pbr=0x03; cpu.pc=0xFC9E; cpu.a=code
        n=0
        while cpu.pc not in CTRL_SITES and n<300: cpu.step(); n+=1
        row,col=w[0x036E],w[0x036F]
        print('%2d ctl %02X -> row %d col %d (steps %d pc %04X)'%(i,code,row,col,n,cpu.pc))
        i+=1; continue
    n=0
    while cpu.pc not in RTS and n<5000: cpu.step(); n+=1
    w=cpu.bus.wram
    got=bytes(w[0x0B00:0x0B08])
    caddr=got[0]|(got[1]<<8)
    _hi,_lo=caddr>>8,caddr&0xFF
    cro,cco=(_hi-0x7C)*4+(_lo-3)//0x40,(_lo-3)%0x40
    print('%2d code %02X cn=%d script %s -> cell (%d,%d) pc %04X'%(i,code,cb.PREFIX0<=code<cb.PREFIX0+cb.PAGES,got.hex(' '),cro,cco,cpu.pc))
    cells[(cro,cco)]=1
    row,col=w[0x036E],w[0x036F]
    i+=2 if (cb.PREFIX0<=code<cb.PREFIX0+cb.PAGES) else 1
print('cells', len(cells))
