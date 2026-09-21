"""Debug C1's first few byte draws for one entry: print what the drawer staged."""
import io
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import cnbuild5 as cb
import sim65816

rom = io.open(os.path.join(BASE, 'kuniokun_cn.smc'), 'rb').read()
addr = json.load(io.open(os.path.join(BASE, 'cn_addr_map.json'), encoding='utf-8'))
key = sys.argv[1] if len(sys.argv) > 1 else '019921'
off = addr[key]
msg = []
i = off
while i < len(rom):
    msg.append(rom[i])
    if rom[i] == 0xF3:
        break
    i += 1
print('entry %s @%06X  %s' % (key, off, ' '.join('%02X' % b for b in msg)))

cpu = None
stage = 0
col = 0
row = 0
for j in range(min(len(msg), 8)):
    code = msg[j]
    if code >= 0xF0:
        continue
    if cpu is None:
        cpu = sim65816.CPU(rom)
    cpu.pbr, cpu.pc = cb.E3_DRAWER // 0x8000, 0x8000 + (cb.E3_DRAWER % 0x8000)
    cpu.m8 = cpu.x8 = True
    cpu.db = 0x03
    w = cpu.bus.wram
    w[0x03EA:0x03EA + len(msg)] = bytes(msg)
    w[0x03E8] = len(msg) & 0xFF
    w[0x03E9] = j
    w[0x036E] = row
    w[0x036F] = col
    w[0x09DF] = stage
    w[cb.WIPE_PEND] = 0
    w[0x12] = code
    cpu.a = code
    cpu.push8(0xFF)
    cpu.push8(0xFF)
    entry_s = cpu.s
    n = 0
    while n < 20000:
        cpu.step()
        n += 1
        if cpu.s > entry_s:
            break
    print('byte %d code %02X -> pbr %02X pc %04X s %04X(%04X) steps %d  '
          '$03E9 %02X $036F %02X $09DD %02X $09DF %02X stage %02X'
          % (j, code, cpu.pbr, cpu.pc, cpu.s, entry_s, n, w[0x03E9], w[0x036F],
             w[0x09DD], w[0x09DF], stage))
    print('   staged:', ' '.join('%02X' % b for b in
                                 w[0x0B00 + stage:0x0B00 + w[0x09DF]]))
    if w[0x09DF] != stage:
        stage = w[0x09DF]
    col = w[0x036F]
    row = w[0x036E]