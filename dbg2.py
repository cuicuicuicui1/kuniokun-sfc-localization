import json, sim65816, cnbuild5 as cb, kuniokun_map as km, mos65xx
BASE='C:/Users/<user>/.zcode/workspace/default/sfc-recon'
rom=open(cb.OUT_ROM,'rb').read(); recs=json.load(open(BASE+'/kuniokun_text.json',encoding='utf-8'))
addr=json.load(open(BASE+'/cn_addr_map.json',encoding='utf-8'))
params=json.load(open(BASE+'/cn_build_params.json'))
cell={k:tuple(v) for k,v in params['cell'].items()}
SP=rom[cb.B3_SLOTPAIR:cb.B3_SLOTPAIR+cb.SLOTS]
print('SLOTPAIR[0:8]', SP[:8].hex(' '), 'len', len(SP))
a=addr['019967']; msg=bytearray(); j=a
while rom[j]!=0xF2: msg.append(rom[j]); j+=1
print('msg',' '.join('%02X'%b for b in msg))
for i in range(0,len(msg)):
    b=msg[i]
    if cb.PREFIX0<=b<cb.PREFIX0+cb.PAGES:
        print(' byte %d: page %d id %d' % (i, b-cb.PREFIX0, msg[i+1]), 'SP[id]=%02X'%SP[msg[i+1]])
# now simulate byte 7 (CB)
i=7; code=msg[i]
w=msg
cpu=sim65816.CPU(rom); cpu.pbr=cb.E3_DRAWER//0x8000; cpu.pc=0x8000+(cb.E3_DRAWER%0x8000)
cpu.m8=cpu.x8=True; cpu.db=0x03
cpu.bus.wram[0x03EA:0x03EA+len(w)]=w; cpu.bus.wram[0x03E8]=len(w); cpu.bus.wram[0x03E9]=i
cpu.bus.wram[0x036E]=0; cpu.bus.wram[0x036F]=6; cpu.bus.wram[0x09DF]=0
cpu.bus.wram[0x12]=code; cpu.a=code
ins_len={}
for n in range(200):
    blob=rom[cb.E3_DRAWER+(cpu.pc-0x8200):cb.E3_DRAWER+(cpu.pc-0x8200)+4]
    ins=mos65xx.disassemble(blob, address=cpu.pc, count=1)
    print('%3d %04X A=%02X X=%02X Y=%02X S=%04X %s' % (n,cpu.pc,cpu.a,cpu.x,cpu.y,cpu.s, ins[0].text if ins else '?'))
    if cpu.pc in (0x825B,0x8304): break
    cpu.step()
