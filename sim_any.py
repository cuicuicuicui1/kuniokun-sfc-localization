"""Render any translated string through the patched dispatcher in the 65816 sim.

usage: python -u sim_any.py <text_rom_off_hex> [cols] [scale]

Sets $22/$23/$24 to the given bank-$03 text offset, starts at the dispatch
entry ($3E:8080) with Y=0 and cursor $20/$21 = $7800, runs to RTS, then
renders VRAM $7800 to sim_any_<off>.png and prints the tilemap entries.
"""
import sys

sys.path.insert(0, 'C:/Users/<user>/.zcode/workspace/default/sfc-recon')
from sim65816 import CPU
from sim_test import render_tilemap

ROM = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/kuniokun_cn.smc'
DISPATCH = 0x1F0080


def snes_of_rom(off):
    return (off // 0x8000, 0x8000 + (off % 0x8000))


def main():
    off = int(sys.argv[1], 16)
    cols = int(sys.argv[2]) if len(sys.argv) > 2 else 32
    scale = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    rom = open(ROM, 'rb').read()
    cpu = CPU(rom)
    bank, addr = snes_of_rom(off)
    cpu.pbr = 0x3E
    cpu.pc = 0x8000 + (DISPATCH % 0x8000)      # dispatch entry: $3E:8080
    cpu.m8 = True                              # hook B sits after SEP #$30
    cpu.x8 = True
    cpu.x8 = False
    cpu.y = 0
    cpu.bus.wr(0, 0x22, addr & 0xFF)
    cpu.bus.wr(0, 0x23, addr >> 8)
    cpu.bus.wr(0, 0x24, bank)
    cpu.bus.wr(0, 0x20, 0x00)
    cpu.bus.wr(0, 0x21, 0x78)
    cpu.s = 0x01FF
    cpu.push8(0x00)
    cpu.push8(0x00)
    n = 0
    while n < 60000:
        cpu.step()
        n += 1
        if cpu.pbr == 0x01 and cpu.pc < 0x0003:
            break
    print('text $%02X:%04X  %d steps, ended %02X:%04X, $20/$21=$%02X%02X'
          % (bank, addr, n, cpu.pbr, cpu.pc,
             cpu.bus.rd(0, 0x21), cpu.bus.rd(0, 0x20)))
    print('DMA count = %d' % len(cpu.dma_log))
    print('tilemap:', ' '.join('%04X' % cpu.vram[0x7800 + i] for i in range(cols)))
    render_tilemap(cpu, 0x7800, cols, 1, scale,
                   'C:/Users/<user>/.zcode/workspace/default/sfc-recon/sim_any_%06X.png' % off)


if __name__ == '__main__':
    main()