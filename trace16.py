"""Trace one drawer invocation in the simulator to find why a CN code takes the
original path.

  python trace16.py [entry-rom-offset-hex] [message-byte-index]
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import cnbuild5 as cb
import sim65816

rom = open(os.path.join(BASE, 'kuniokun_cn.smc'), 'rb').read()

off = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x019934
idx = int(sys.argv[2]) if len(sys.argv) > 2 else None

msg, i = [], off
while i < len(rom):
    b = rom[i]
    msg.append(b)
    i += 1
    if b == 0xF3:
        break
print('entry %06X  message: %s' % (off, ' '.join('%02X' % b for b in msg)))
if idx is None:
    idx = next(j for j, b in enumerate(msg) if cb.PREFIX0 <= b < 0xD7)
print('index %d  code %02X' % (idx, msg[idx]))

cpu = sim65816.CPU(rom)
cpu.pbr, cpu.pc = cb.E3_DRAWER // 0x8000, 0x8000 + (cb.E3_DRAWER % 0x8000)
cpu.m8 = cpu.x8 = True
cpu.db = 0x03
w = cpu.bus.wram
w[0x03EA:0x03EA + len(msg)] = bytes(msg)
w[0x03E8] = len(msg) & 0xFF
w[0x03E9] = idx
w[0x036E] = 0
w[0x036F] = 0
w[0x09DF] = 0
w[cb.WIPE_PEND] = 0
w[0x12] = msg[idx]
cpu.a = msg[idx]
cpu.push8(0xFF)
cpu.push8(0xFF)
entry_s = cpu.s

print('entry pc %02X:%04X  a=%02X  $12=%02X  $0D43=%02X'
      % (cpu.pbr, cpu.pc, cpu.a, w[0x12], w[cb.WIPE_PEND]))
for n in range(70):
    pc0, pbr0 = cpu.pc, cpu.pbr
    b0 = cpu.bus.rd(pbr0, pc0)
    cpu.step()
    print('  %02X:%04X op %02X  a=%02X x=%02X y=%02X db=%02X pbr=%02X s=%04X'
          % (pbr0, pc0, b0, cpu.a, cpu.x, cpu.y, cpu.db, cpu.pbr, cpu.s))
    if cpu.s > entry_s:
        print('  returned')
        break
print('$03E9=%02X $036F=%02X $09DF=%02X' % (w[0x03E9], w[0x036F], w[0x09DF]))
print('staged:', ' '.join('%02X' % x for x in w[0x0B00:0x0B00 + w[0x09DF]]))