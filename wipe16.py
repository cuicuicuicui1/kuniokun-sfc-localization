"""Dump what the box-wipe stager actually stages into the queue."""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import cnbuild5 as cb
import sim65816

rom = open(os.path.join(BASE, 'kuniokun_cn.smc'), 'rb').read()
wb, wa = cb.snes_of_rom(cb.E3_WIPE)

for pend, cur, top, bot in ((1, 2, 1, 2), (1, 1, 1, 1), (1, 0, 0, 0)):
    cpu = sim65816.CPU(rom)
    cpu.pbr, cpu.pc = wb, wa
    cpu.m8 = cpu.x8 = True
    cpu.db = 0x00
    w = cpu.bus.wram
    w[cb.WIPE_PEND], w[cb.WIPE_CUR] = pend, cur
    w[cb.WIPE_TOP], w[cb.WIPE_BOT] = top, bot
    w[0x09DF] = 0
    w[0x09DD] = 0
    steps = 0
    while steps < 40000 and not (cpu.pbr == 0x03 and cpu.pc == 0xEE74):
        cpu.step()
        steps += 1
    n = w[0x09DF]
    print('pend=%d cur=%d top=%d bot=%d -> reached %02X:%04X in %d steps, '
          'staged $%02X bytes, s=$%04X'
          % (pend, cur, top, bot, cpu.pbr, cpu.pc, steps, n, cpu.s))
    print('  queue:', ' '.join('%02X' % x for x in w[0x0B00:0x0B00 + n]))
    print('  WIPE_CUR=%02X PEND=%02X TOP=%02X BOT=%02X'
          % (w[cb.WIPE_CUR], w[cb.WIPE_PEND], w[cb.WIPE_TOP], w[cb.WIPE_BOT]))