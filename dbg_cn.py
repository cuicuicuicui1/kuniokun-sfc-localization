import json, sim65816, cnbuild5 as cb, kuniokun_map as km
BASE='C:/Users/<user>/.zcode/workspace/default/sfc-recon'
rom=open(cb.OUT_ROM,'rb').read(); recs=json.load(open(BASE+'/kuniokun_text.json',encoding='utf-8'))
addr=json.load(open(BASE+'/cn_addr_map.json',encoding='utf-8'))
tr=json.load(open(BASE+'/cn_translation.json',encoding='utf-8'))
# pick the first entry whose FIRST byte is a Chinese prefix
for r in recs:
    k='%06X'%r['text_rom_off']; a=addr[k]
    if cb.PREFIX0 <= rom[a] < cb.PREFIX0+cb.PAGES:
        print('entry',k,'at',hex(a),'bytes',' '.join('%02X'%b for b in rom[a:a+12]),'|',tr[k][:20], '|', json.load(open(BASE+'/cn_build_params.json'))['slots'])
        break
msg=bytearray()
j=a
while rom[j]!=0xF2: msg.append(rom[j]); j+=1
msg=bytes(msg)
print('msg',' '.join('%02X'%b for b in msg))
w=msg
cpu=sim65816.CPU(rom); cpu.pbr=cb.E3_DRAWER//0x8000; cpu.pc=0x8000+(cb.E3_DRAWER%0x8000)
cpu.m8=cpu.x8=True; cpu.db=0x03
cpu.bus.wram[0x03EA:0x03EA+len(w)]=w; cpu.bus.wram[0x03E8]=len(w); cpu.bus.wram[0x03E9]=0
cpu.bus.wram[0x036E]=0; cpu.bus.wram[0x036F]=0; cpu.bus.wram[0x09DF]=0; cpu.bus.wram[0x12]=msg[0]; cpu.a=msg[0]
import mos65xx
for n in range(400):
    addr_now=(cpu.pbr<<16)|cpu.pc
    off=addr_now
    b=rom[cb.E3_DRAWER + (cpu.pc - 0x8200)] if 0x8200 <= cpu.pc < 0x8400 else None
    ins=mos65xx.disassemble(rom[cb.E3_DRAWER+(cpu.pc-0x8200):cb.E3_DRAWER+(cpu.pc-0x8200)+4], address=cpu.pc, count=1)
    txt=ins[0].text if ins else '??'
    print('%3d %04X A=%02X X=%02X Y=%02X S=%04X  %s' % (n,cpu.pc,cpu.a,cpu.x,cpu.y,cpu.s,txt))
    if cpu.pc in (0x825B,0x8304): break
    cpu.step()
print('dma', cpu.dma_log)
print('script', ' '.join('%02X'%b for b in cpu.bus.wram[0x0B00:0x0B10]))
print('col', cpu.bus.wram[0x036F], 'e9', cpu.bus.wram[0x03E9])
