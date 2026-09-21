"""Run the stale-row wipe stub ($3E:C400) in the 65816 interpreter.

Cases: the message's second row ($036E == $0391 + 1) at columns 1..4 wipes text
row $0391 - the row the previous message left on screen - and everything else
wipes nothing.  A full queue makes the stub skip the wipe and leave the queue
untouched: it must never drive the engine's flusher, because the drawer does not
run in VBlank.

The gate's row and delta were measured, not guessed: in hw/seq1.log $0391 holds
the row to blank while $036E is one past it, and $0391 is not "the message's
first row" (it changed once in 901 frames).

    python test_stalerow.py [rom]
"""
import sys

import sim65816

ROMF = sys.argv[1] if len(sys.argv) > 1 else 'kuniokun_cn.smc'
STUB = (0x3E, 0xC400)
BACK = (0x03, 0xFCCD)


def entries(rom, r6e, r6f, r91, full=False):
    c = sim65816.CPU(rom)
    c.pbr, c.pc = STUB
    c.s = 0x01FF
    c.m8 = c.x8 = True
    c.db = 0x00
    for a in range(0x0B00, 0x0C00):
        c.bus.wram[a] = 0x00
    c.bus.wram[0x09DD] = 0x00
    c.bus.wram[0x09DE] = 0x0B
    cur = 0x00
    if full:
        # one valid entry already staged, so the page has no room for the wipe
        c.bus.wram[0x0B00] = 0x00; c.bus.wram[0x0B01] = 0x7C
        c.bus.wram[0x0B02] = 0x80; c.bus.wram[0x0B03] = 0x02
        c.bus.wram[0x0B04] = 0x00; c.bus.wram[0x0B05] = 0x00
        cur = 0xE8                             # $0BE8: no room for 224 bytes
    c.bus.wram[0x09DF] = cur
    c.bus.wram[0x09E0] = 0x0B
    c.bus.wram[0x036E] = r6e
    c.bus.wram[0x036F] = r6f
    c.bus.wram[0x0391] = r91
    c.push8(BACK[0]); c.push8(BACK[1] >> 8); c.push8(BACK[1] & 0xFF)
    steps = 0
    while steps < 200000 and not (c.pbr == BACK[0] and c.pc >= BACK[1]):
        c.step()
        steps += 1
    assert c.pbr == BACK[0] and c.pc >= BACK[1], ('did not return', hex(c.pc), steps)
    # walk the queue from $0B00 to the append cursor
    end = c.bus.wram[0x09DF] + c.bus.wram[0x09E0] * 256
    out, i = [], 0x0B00
    while i < end:
        addr = c.bus.wram[i] + c.bus.wram[i + 1] * 256
        vmain = c.bus.wram[i + 2]
        n = c.bus.wram[i + 3]
        data = [c.bus.wram[i + 4 + k] + c.bus.wram[i + 5 + k] * 256
                for k in range(0, n, 2)]
        out.append((addr, vmain, n, data))
        i += 4 + n
    return out, c


def main():
    rom = open(ROMF, 'rb').read()
    if sum(rom[0x1F4400:0x1F4404]) == 0:
        print('stale-row stub not installed (build with STALEROW=1): skipped')
        return 0
    ok = True
    cases = [(5, 1, 4, 4), (5, 2, 4, 4),      # columns 1, 2 -> $0391
             (5, 3, 4, 3), (5, 4, 4, 3),      # columns 3, 4 -> $0391 - 1
             (4, 1, 4, None),      # the message's first row: the stale row is
                                   # not visible yet
             (6, 1, 4, None),      # two rows past the start
             (5, 0, 4, None),      # column 0: the drawer's own row wipe is there
             (5, 5, 4, None),      # past the first few cells
             (1, 1, 0, 0),         # $0391 = 0: blank row 0
             (1, 3, 0, 15),        # $0391 - 1 wraps to row 15
             (0, 1, 15, 15)]       # delta 1 across the 16 row wrap
    for r6e, r6f, r91, want in cases:
        ent, _ = entries(rom, r6e, r6f, r91)
        got = [e[0] for e in ent]
        exp = [] if want is None else [0x7C00 + want * 64 + 3,
                                       0x7C00 + want * 64 + 3 + 0x20]
        good = got == exp and all(e[2] == 0x34 for e in ent) \
            and all(set(e[3]) == {0x2C00} for e in ent)
        print('6E=%02X 6F=%02X 91=%02X -> %s  want %s  %s'
              % (r6e, r6f, r91, [hex(a) for a in got], [hex(a) for a in exp],
                 'OK' if good else 'FAIL'))
        ok &= good
    # full page: the stub must skip the wipe and leave the queue alone.  It must
    # NOT drive the engine's flusher: the drawer does not run in VBlank, and
    # doing that is what garbled the whole screen in the v14 hardware run.
    ent, c = entries(rom, 4, 2, 4, full=True)
    # the cursor is a byte at $09DF with its page in $09E0, so "unchanged"
    # means $0BE8, the value the test staged before the call
    cur = c.bus.wram[0x09DF] + c.bus.wram[0x09E0] * 256
    good = (cur == 0xBE8
            and all(c.vram[0x7C00 + k] == 0 for k in (0x83, 0xA3, 0xC3, 0xE3)))
    print('full page -> cursor %04X (want 0BE8, unchanged), VRAM rows untouched: %s'
          % (cur, 'OK' if good else 'FAIL'))
    ok &= good
    print('ALL CHECKS PASSED' if ok else 'FAILURES')
    return 0 if ok else 1


sys.exit(main())
