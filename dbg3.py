import json, sim65816, cnbuild5 as cb, mos65xx
BASE='C:/Users/<user>/.zcode/workspace/default/sfc-recon'
rom=open(cb.OUT_ROM,'rb').read(); recs=json.load(open(BASE+'/kuniokun_text.json',encoding='utf-8'))
addr=json.load(open(BASE+'/cn_addr_map.json',encoding='utf-8'))
props=sorted([r for r in recs if r['table_rom_off']==0x01DBC5], key=lambda r:r['index'])
for r in props:
    a=addr['%06X'%r['text_rom_off']]
    msg=bytearray(); j=a
    while rom[j]!=0xF2: msg.append(rom[j]); j+=1
    if any(cb.PREFIX0<=b<cb.PREFIX0+cb.PAGES for b in msg):
        print('entry','%06X'%r['text_rom_off'],'->',hex(a),'msg',' '.join('%02X'%b for b in msg)); break
cpu=sim65816.CPU(rom); cpu.pbr=cb.DISPATCH_ROM//0x8000; cpu.pc=0x8000+(cb.DISPATCH_ROM%0x8000)
cpu.m8=cpu.x8=True; cpu.db=0x03
_b,_a=cb.snes_of_rom(a); w=cpu.bus.wram
w[0x22],w[0x23],w[0x24]=_a&0xFF,(_a>>8)&0xFF,_b; w[0x20],w[0x21]=0xC6,0x79
for n in range(140):
    off=cb.DISPATCH_ROM+(cpu.pc-0x8080)
    ins=mos65xx.disassemble(rom[off:off+4], address=cpu.pc, count=1)
    print('%3d %04X A=%02X X=%02X Y=%02X S=%04X %s' % (n,cpu.pc,cpu.a,cpu.x,cpu.y,cpu.s, ins[0].text if ins else '?'))
    if cpu.pbr==0x01 and cpu.pc==0xFCC6: break
    cpu.step()
print('vram 79C6:', ' '.join('%04X'%cpu.vram[0x79C6+k] for k in range(3)))
print('dma', cpu.dma_log[:2])
