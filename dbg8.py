"""Trace registers/stack around the PHB..PLB sequence of the drawer's cn branch."""
import json
import mos65xx
import sim65816
import cnbuild5 as cb

rom = open(cb.OUT_ROM, 'rb').read()
cw = cb.build_drawer_copy()
RTS_SITES = [ins.address for ins in mos65xx.disassemble(cw, address=0x8000 + (cb.E3_DRAWER % 0x8000))
             if ins.mnemonic == 'rts']

addr = json.load(open(cb.BASE + '/cn_addr_map.json', encoding='utf-8'))
off = addr['019921']
msg = bytearray()
i = off
while rom[i] != 0xF2:
    msg.append(rom[i])
    i += 1

cpu = sim65816.CPU(rom)
cpu.pbr = cb.E3_DRAWER // 0x8000
cpu.pc = 0x8000 + (cb.E3_DRAWER % 0x8000)
cpu.m8 = True
cpu.x8 = True
cpu.db = 0x03
w = cpu.bus.wram
w[0x03EA:0x03EA + len(msg)] = msg
w[0x03E8] = len(msg) & 0xFF
w[0x03E9] = 1
w[0x036E] = 0
w[0x036F] = 1
w[0x09DF] = 8
w[0x12] = msg[1]
cpu.a = msg[1]

print('stack slots around $01E0..$01FF before:', bytes(w[0x01E0:0x0200]).hex(' '))
steps = 0
while steps < 4000 and cpu.pc not in RTS_SITES:
    pc, a, x, y, db, s, m8 = cpu.pc, cpu.a, cpu.x, cpu.y, cpu.db, cpu.s, cpu.m8
    cpu.step()
    newdb = cpu.db
    if 0x8270 <= pc <= 0x8355 or newdb != db:
        print('%04X a=%02X x=%02X y=%02X db=%02X s=%02X m8=%d%s' %
              (pc, a & 0xFF, x, y, db, s, m8, '   -> db=%02X' % newdb if newdb != db else ''))
    steps += 1
print('final pc %04X db=%02X' % (cpu.pc, cpu.db))
print('stack slots after :', bytes(w[0x01E0:0x0200]).hex(' '))
print('script at $0B08:', bytes(w[0x0B08:0x0B10]).hex(' '))