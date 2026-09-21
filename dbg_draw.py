"""trace the drawer's first simulated draw to find where the sim loses sync"""
import io
import sim65816
import cnbuild5 as cb

rom = open('kuniokun_cn.smc', 'rb').read()
orig = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()

E3 = cb.E3_DRAWER
pbr, pc0 = E3 // 0x8000, 0x8000 + (E3 % 0x8000)
cpu = sim65816.CPU(rom)
cpu.pbr, cpu.pc = pbr, pc0
cpu.m8 = cpu.x8 = True
cpu.db = 0x03
w = cpu.bus.wram
msg = bytes([cb.PREFIX0, 0x00])
w[0x03EA:0x03EA + len(msg)] = msg
w[0x03E8] = len(msg)
w[0x03E9] = 0
w[0x036E] = 3
w[0x036F] = 0
w[0x09DF] = 0
w[0x12] = msg[0]
cpu.a = msg[0]
cpu.push8(0xFF)
cpu.push8(0xFF)
entry_s = cpu.s
hist = []
for n in range(4000):
    hist.append((cpu.pbr, cpu.pc, cpu.a, cpu.x, cpu.y, cpu.m8, cpu.x8))
    try:
        cpu.step()
    except NotImplementedError as e:
        print('CRASH', e)
        break
    if cpu.s > entry_s:
        print('returned after %d steps, pbr:%04X pc:%04X s:%04X' %
              (n, cpu.pbr, cpu.pc, cpu.s))
        break
    if len(hist) > 24:
        hist.pop(0)
else:
    print('no return')
for pbr_, pc_, a_, x_, y_, m_, x8_ in hist:
    print('  %02X:%04X A=%02X X=%04X Y=%04X m=%d x=%d' %
          (pbr_, pc_, a_, x_, y_, m_, x8_))