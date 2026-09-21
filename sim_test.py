"""Test harness: run the patched renderer in the 65816 sim and render the result."""
import json
import sys

from PIL import Image

sys.path.insert(0, 'C:/Users/<user>/.zcode/workspace/default/sfc-recon')
from sim65816 import CPU

ROM = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/kuniokun_cn.smc'


def rom_off(bank, addr):
    return (bank & 0x7F) * 0x8000 + (addr - 0x8000)


def render_tilemap(cpu, vram_start, cols, rows, scale, path,
                   font_base=0x6000):
    im = Image.new('RGB', (cols * 8 * scale, rows * 16 * scale), (0, 0, 0))
    px = im.load()
    for r in range(rows):
        for c in range(cols):
            top = cpu.vram[(vram_start + r * 2 * 32 + c) & 0x7FFF]
            bot = cpu.vram[(vram_start + r * 2 * 32 + 32 + c) & 0x7FFF]
            for half, entry in ((0, top), (1, bot)):
                tile = entry & 0x3FF
                base = font_base + tile * 8
                for y in range(8):
                    w = cpu.vram[(base + y) & 0x7FFF]
                    p0, p1 = w & 0xFF, (w >> 8) & 0xFF
                    for x in range(8):
                        v = ((p0 >> (7 - x)) & 1) | (((p1 >> (7 - x)) & 1) << 1)
                        col = (255, 255, 255) if v in (1, 3) else \
                              (140, 140, 140) if v == 2 else (0, 0, 0)
                        for dy in range(scale):
                            for dx in range(scale):
                                px[c * 8 * scale + x * scale + dx,
                                   (r * 16 + half * 8 + y) * scale + dy] = col
    im.save(path)
    print('wrote', path)


def main():
    rom = open(ROM, 'rb').read()
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    cpu = CPU(rom)
    cpu.pbr = 0x01
    cpu.pc = 0xFC77
    cpu.m8 = False
    cpu.x8 = False
    cpu.a = idx            # string index -> ASL/TAX gives X = idx*2
    # VRAM text cursor
    cpu.bus.wr(0, 0x20, 0x00)
    cpu.bus.wr(0, 0x21, 0x78)
    # stack
    cpu.s = 0x01FF
    cpu.push8(0x00)
    cpu.push8(0x00)        # dummy return address (RTS will jump to 0x0000)
    print('start idx=%d  $20/$21=$%02X%02X  $2115=%02X'
          % (idx, cpu.bus.rd(0, 0x21), cpu.bus.rd(0, 0x20), cpu.vmain))
    n = 0
    while n < 20000:
        cpu.step()
        n += 1
        if cpu.pbr == 0x01 and cpu.pc < 0x0003:
            break
    print('executed %d steps, ended at %02X:%04X' % (n, cpu.pbr, cpu.pc))
    print('DMA transfers:')
    for d in cpu.dma_log:
        print('   ch%d mode%d bbad=$%02X  src=%02X:%04X size=%d'
              % (d[0], d[1], d[2], d[4], d[3], d[5]))
    # show the first few tilemap entries
    print('tilemap @ $7800:', ' '.join('%04X' % cpu.vram[0x7800 + i] for i in range(20)))
    render_tilemap(cpu, 0x7800, 20, 4, 5,
                   'C:/Users/<user>/.zcode/workspace/default/sfc-recon/sim_cn_%d.png' % idx)


if __name__ == '__main__':
    main()