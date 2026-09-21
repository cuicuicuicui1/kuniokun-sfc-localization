"""Disassemble the first bytes of each text-driver sub-step so the entry hook can
relocate whole instructions."""
import mos65xx
BASE = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/'
rom = open(BASE + 'work_kuniokun_2mb.smc', 'rb').read()

SUBS = [('sub1', 0xEF2D), ('sub2', 0xEF5E), ('sub3', 0xF018),
        ('sub4', 0xF0DC), ('sub5', 0xF0F1), ('sub6', 0xFA0B)]

for name, addr in SUBS:
    off = 3 * 0x8000 + (addr - 0x8000)          # bank $03 LoROM
    buf = rom[off:off + 24]
    print('=== %s  $%04X (ROM %06X) bytes: %s' % (
        name, addr, off, ' '.join('%02X' % b for b in buf[:14])))
    try:
        ins = list(mos65xx.disassemble(buf, address=addr))
        n = 0
        for i in ins:
            print('   %04X: %-22s (%d bytes)' % (i.address, i.text, i.length))
            n += i.length
            if n >= 6:
                break
    except Exception as e:
        print('   disasm failed:', e)