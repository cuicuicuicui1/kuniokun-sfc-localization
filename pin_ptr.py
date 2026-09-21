"""Verify pointer table base and fix mos65xx invocation."""
import mos65xx

d = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()

print('=== bytes 0x01DBC0-0x01DC00 ===')
for i in range(0x01DBC0, 0x01DC00, 16):
    print('%06X: %s' % (i, ' '.join('%02X' % x for x in d[i:i + 16])))

BASE = 0x01DBC3


def rd16(base, i):
    return d[base + 2 * i] | (d[base + 2 * i + 1] << 8)


def lorom(addr, bank):
    if bank == 3:
        return 0x18000 + (addr - 0x8000)
    return None


print()
print('=== table @0x01DBC3 ==')
for i in range(12):
    v = rd16(BASE, i)
    tgt = lorom(v, 3)
    s = ''
    if tgt and 0 <= tgt < len(d):
        raw = d[tgt:tgt + 14]
        s = ' '.join('%02X' % x for x in raw)
    print('  i=%-3d ptr=$%04X -> ROM 0x%06X  %s' % (i, v, tgt or 0, s))

print()
print('=== table @0x01DBC5 (subagent base) ==')
for i in range(12):
    v = rd16(0x01DBC5, i)
    tgt = lorom(v, 3)
    s = ''
    if tgt and 0 <= tgt < len(d):
        raw = d[tgt:tgt + 14]
        s = ' '.join('%02X' % x for x in raw)
    print('  i=%-3d ptr=$%04X -> ROM 0x%06X  %s' % (i, v, tgt or 0, s))

print()
print('=== mos65xx invocation test (renderer region) ===')
buf = d[0x00FC6E:0x00FC98]
forms = [
    ('offset+address', dict(offset=0x00FC6E, address=0xFC6E)),
    ('count=20', dict(offset=0x00FC6E, address=0xFC6E, count=20)),
    ('no count, stop_at_return=False', dict(address=0xFC6E, stop_at_return=False)),
    ('plain', dict(address=0xFC6E)),
]
for name, kw in forms:
    try:
        r = mos65xx.disassemble(buf, **kw)
        print('  %-32s -> %d instructions' % (name, len(r) if r else 0))
        if r:
            for x in r[:8]:
                print('       %04X: %s' % (x.address, x.text))
    except Exception as e:
        print('  %-32s -> ERROR %s' % (name, e))