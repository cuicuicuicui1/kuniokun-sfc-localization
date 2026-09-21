"""Dump + disassemble the VRAM/DMA setup region so VRAM destinations are certain."""
import mos65xx

d = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()


def snes(off):
    """LoROM: bank = off//0x8000, addr = 0x8000 + off%0x8000"""
    return '$%02X:%04X' % (off // 0x8000, 0x8000 + (off % 0x8000))


def dump(a, b, dis=True):
    print('=== ROM 0x%06X-0x%06X  (SNES %s) ===' % (a, b, snes(a)))
    i = a
    while i < b:
        ln = min(16, b - i)
        print('%06X %-6s: %s' % (i, snes(i), ' '.join('%02X' % x for x in d[i:i + ln])))
        i += ln
    if dis:
        print('--- disassembly ---')
        try:
            ins = mos65xx.disassemble(d[a:b], offset=a, address=0x8000 + a % 0x8000)
        except Exception as e:
            print('disasm error:', e)
            ins = []
        for x in ins:
            print('  %04X: %-24s (%s)' % (x.address, x.text, x.mode))


dump(0x000630, 0x0007D0)
print()
dump(0x000320, 0x0003C0)
print()
dump(0x000E80, 0x000F20)