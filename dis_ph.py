"""Disassemble the string-processing routines that handle 0xE2/0xF0/0xC4 placeholders."""
import mos65xx

d = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()


def dis(start, end, label):
    print()
    print('======== %s  ROM 0x%06X..0x%06X ========' % (label, start, end))
    buf = d[start:end]
    r = mos65xx.disassemble(buf, address=start, stop_at_return=False)
    for x in r:
        raw = d[x.offset:x.offset + x.size]
        print('  %06X: %-11s %s' % (x.offset, ' '.join('%02X' % b for b in raw), x.text))


dis(0x01EB60, 0x01EC90, 'string processor? (C9 F0 site 0x01EBC3)')
dis(0x019740, 0x0197C0, 'C9 C4 site 0x019782')
dis(0x006190, 0x0061F0, 'C9 E2 site 0x0061BF')
dis(0x0040F0, 0x004140, 'C9 ED site 0x004113')