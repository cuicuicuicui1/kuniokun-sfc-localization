"""Debug: trace the patched renderer in the sim."""
import sys
sys.path.insert(0, 'C:/Users/<user>/.zcode/workspace/default/sfc-recon')
from sim65816 import CPU

B = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/'
pat = open(B + 'kuniokun_cn.smc', 'rb').read()

cpu = CPU(pat)
cpu.pbr = 0x01
cpu.pc = 0xFC77
cpu.m8 = False
cpu.x8 = False
cpu.a = 8
cpu.bus.wr(0, 0x20, 0x00)
cpu.bus.wr(0, 0x21, 0x78)
cpu.s = 0x01FF
cpu.push8(0x00)
cpu.push8(0x00)

for n in range(26):
    print('%02X:%04X A=%04X X=%04X Y=%02X S=%04X' % (cpu.pbr, cpu.pc, cpu.a, cpu.x, cpu.y, cpu.s))
    cpu.step()
print('after preload: $22=%02X $23=%02X $24=%02X  Y=%02X' %
      (cpu.bus.rd(0, 0x22), cpu.bus.rd(0, 0x23), cpu.bus.rd(0, 0x24), cpu.y))
print('$2115=%02X' % cpu.vmain)

# run to completion
n2 = 0
try:
    while cpu.pc < 0x0002 or cpu.pbr != 0x01:
        cpu.step()
        n2 += 1
        if n2 > 5000:
            break
except Exception as e:
    print('stopped:', e)
print('extra steps %d, pc=%02X:%04X' % (n2, cpu.pbr, cpu.pc))
print('DMA log:', cpu.dma_log)
print('$2115=%02X' % cpu.vmain)
print('top row   @7800:', ' '.join('%04X' % cpu.vram[0x7800 + i] for i in range(12)))
print('bottom row@7820:', ' '.join('%04X' % cpu.vram[0x7820 + i] for i in range(12)))
for slot in range(2):
    base = 0x6000 + slot * 16
    print('glyph slot %d @ VRAM %04X:' % (slot, base))
    for y in range(16):
        w = cpu.vram[base + y]
        p0, p1 = w & 0xFF, (w >> 8) & 0xFF
        print('   ' + ''.join('#' if (((p0 >> (7 - x)) & 1) |
                                     (((p1 >> (7 - x)) & 1) << 1)) else '.'
                              for x in range(8)))