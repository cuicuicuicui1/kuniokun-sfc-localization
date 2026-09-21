"""Run the menu-close row wipe in the 65816 interpreter, without an emulator.

The stub at $3E:C000 is executed for real: its calls to the engine's room
helper ($009AB6) and to the flusher ($008385) run the ROM's own code, so the
queue entries it pushes are turned into VRAM writes by the same DMA path the
hardware uses.  What is checked afterwards:

  * four entries were pushed, covering map rows base..base+3, columns 3..28
  * the words that reached VRAM are $2C00 (the box's blank cell)
  * the pending byte at $0BFB is cleared
  * the stub returned to $03:F706 with the replayed instructions done

    python test_menuclose.py [rom]
"""
import sys

import sim65816

ROMF = sys.argv[1] if len(sys.argv) > 1 else 'kuniokun_cn.smc'
STUB = (0x3E, 0xC000)          # hooked on the menu's close step ($03:F85B)
STUB2 = (0x3E, 0xC100)         # hooked on a drawing sequence end ($03:F700)
ARM = (0x3E, 0xC200)           # hooked on the menu's setup step ($03:F72E)
BAND = (0x3E, 0xC300)          # hooked on the drawing-sequence start ($03:FCC8)
# The engine's step 31 tail ends in an RTS, so the harness puts a sentinel
# return address on the stack: reaching $03:DEAE means the whole path ran.
BACK = (0x03, 0xDEAE)
PEND = 0x0BFB


def arm_case(row):
    """The arming stub: $036E -> $0BFB, then the replayed instructions."""
    rom = open(ROMF, 'rb').read()
    c = sim65816.CPU(rom)
    c.pbr, c.pc = ARM
    c.s = 0x01FF
    c.m8 = c.x8 = True
    c.bus.wram[0x036E] = row
    c.bus.wram[0x0BFB] = 0
    c.bus.wram[0x039E] = 0x55
    c.bus.wram[0x0392] = 0x11
    c.push8(0xDE)
    c.push8(0xAD)
    steps = 0
    while steps < 20000 and (c.pbr, c.pc) != (0x03, 0xDEAE):
        c.step()
        steps += 1
    return (c.bus.wram[0x0BFB], c.bus.wram[0x039E], c.bus.wram[0x0392],
            (c.pbr, c.pc), steps)


def run_case(base, vblank=True, stub=STUB, back=BACK):
    rom = open(ROMF, 'rb').read()
    c = sim65816.CPU(rom)
    c.pbr, c.pc = stub
    c.s = 0x01FF
    c.m8 = c.x8 = True
    c.db = 0x00
    # a marker everywhere the wipe must not touch, then the real values
    for a in range(0x0B00, 0x0C00):
        c.bus.wram[a] = 0xAA
    c.bus.wram[PEND] = 0x80 | base
    c.bus.wram[0x4212] = 0x80 if vblank else 0x00
    c.bus.wram[0x09DD] = 0
    c.bus.wram[0x09DF] = 0
    c.push8(0xDE)
    c.push8(0xAD)
    steps = 0
    while steps < 200000:
        c.step()
        steps += 1
        if (c.pbr, c.pc) == back:
            break
    else:
        return None, 'never returned to $%02X:%04X' % back
    # apply the queue the way the engine's flusher does: [addr][vmain][count][data]
    q = 0x09DD
    a = c.bus.wram[0x09DD]
    end = c.bus.wram[0x09DF]
    applied = []
    while a < end:
        addr = c.bus.wram[0x0B00 + a] | (c.bus.wram[0x0B00 + a + 1] << 8)
        vmain = c.bus.wram[0x0B00 + a + 2]
        n = c.bus.wram[0x0B00 + a + 3]
        data = c.bus.wram[0x0B00 + a + 4:0x0B00 + a + 4 + n]
        applied.append((addr, vmain, n))
        for i in range(0, n, 2):
            c.vram[(addr + i // 2) & 0x7FFF] = data[i] | (data[i + 1] << 8)
        a += 4 + n
    rows = []
    for r in range(base, base + 4):
        rr = r & 0x1F
        word = 0x7C00 + rr * 0x20 + 3
        cells = [c.vram[word + i] for i in range(26)]
        rows.append((rr, cells))
    return (rows, c.bus.wram[PEND], c.bus.wram[0x09DD], c.bus.wram[0x09DF],
            applied, steps), None


def main():
    rom = open(ROMF, 'rb').read()
    if sum(rom[0x1F4000:0x1F4010]) == 0:
        print('command-window stubs not installed (build with CMDWIN=1): skipped')
        return 0
    ok = True
    for base in (0, 28, 4, 30):
        res, err = run_case(base)
        if err:
            print('base %2d: FAIL %s' % (base, err))
            ok = False
            continue
        rows, pend, dd, df, applied, steps = res
        bad = []
        for rr, cells in rows:
            for i, v in enumerate(cells):
                if v != 0x2C00:
                    bad.append((rr, i, v))
        print('base %2d: rows %s  pending=%02X cursor=%02X/%02X entries=%s steps=%d %s'
              % (base, [r for r, _ in rows], pend, dd, df,
                 ['$%04X/%d' % (a, n) for a, _v, n in applied], steps,
                 'OK' if not bad and pend == 0 else 'BAD %s' % bad[:4]))
        if bad or pend != 0 or len(applied) != 4:
            ok = False
    # the same with no pending byte: nothing may be written
    rom = open(ROMF, 'rb').read()
    c = sim65816.CPU(rom)
    c.pbr, c.pc = STUB
    c.s = 0x01FF
    c.m8 = c.x8 = True
    c.bus.wram[PEND] = 0
    c.bus.wram[0x4212] = 0x80
    c.bus.wram[0x09DD] = c.bus.wram[0x09DF] = 0
    c.push8(0xDE)
    c.push8(0xAD)
    steps = 0
    while steps < 20000 and (c.pbr, c.pc) != BACK:
        c.step()
        steps += 1
    nz = sum(1 for i in range(0x7C00, 0x8000) if c.vram[i] not in (0, 0x2C00))
    print('no pending: dma=%d steps=%d vram-nonblank=%d %s'
          % (len(c.dma_log), steps, nz, 'OK' if not c.dma_log and nz == 0 else 'BAD'))
    if c.dma_log or nz:
        ok = False
    # the second stub (the $03:F700 hook) must behave identically, and its
    # replay must land on $03:F706
    for base in (0, 28):
        res, err = run_case(base, stub=STUB2, back=(0x03, 0xF70B))
        if err:
            print('stub2 base %2d: FAIL %s' % (base, err))
            ok = False
            continue
        rows, pend, dd, df, applied, steps = res
        bad = [(r, i, v) for r, cells in rows for i, v in enumerate(cells)
               if v != 0x2C00]
        print('stub2 base %2d: rows %s pending=%02X entries=%d %s'
              % (base, [r for r, _ in rows], pend, len(applied),
                 'OK' if not bad and pend == 0 else 'BAD %s' % bad[:4]))
        if bad or pend != 0:
            ok = False
    # the band stub: always rows 28..31, then back to $03:FCCD
    rom = open(ROMF, 'rb').read()
    c = sim65816.CPU(rom)
    c.pbr, c.pc = BAND
    c.s = 0x01FF
    c.m8 = c.x8 = True
    c.db = 0
    for a in range(0x0B00, 0x0C00):
        c.bus.wram[a] = 0xAA
    c.bus.wram[0x0BFB] = 0x00
    c.bus.wram[0x4212] = 0x80
    c.bus.wram[0x0374] = 0x11
    c.bus.wram[0x09DD] = c.bus.wram[0x09DF] = 0
    c.push8(0xDE)
    c.push8(0xAD)
    steps = 0
    while steps < 20000 and (c.pbr, c.pc) != (0x03, 0xDEAE):
        c.step()
        steps += 1
    # apply the queue the way the engine's flusher does
    q, end = 0, c.bus.wram[0x09DF]
    while q < end:
        addr = c.bus.wram[0x0B00 + q] | (c.bus.wram[0x0B00 + q + 1] << 8)
        n = c.bus.wram[0x0B00 + q + 3]
        data = c.bus.wram[0x0B00 + q + 4:0x0B00 + q + 4 + n]
        for i in range(0, n, 2):
            c.vram[(addr + i // 2) & 0x7FFF] = data[i] | (data[i + 1] << 8)
        q += 4 + n
    bad = []
    for r in (28, 29, 30, 31):
        for i in range(26):
            v = c.vram[0x7C00 + r * 0x20 + 3 + i]
            if v != 0x2C00:
                bad.append((r, i, v))
    print('band stub: rows 28..31 blank=%s pending=%02X cursor=%02X/%02X %s'
          % (not bad, c.bus.wram[0x0BFB], c.bus.wram[0x09DD], c.bus.wram[0x09DF],
             'OK' if not bad else 'BAD %s' % bad[:4]))
    if bad:
        ok = False

    # the arming stub: base must be 2 * $036E with bit 7 set
    for row in (0, 2, 14, 15):
        pend, r9e, r92, pcs, steps = arm_case(row)
        want = 0x80 | ((2 * row) & 0x1F)
        good = (pend == want and r9e == 0 and r92 == 0x12 and pcs == (0x03, 0xDEAE))
        print('arm $036E=%2d -> $0BFB=%02X (want %02X) $039E=%02X $0392=%02X %s'
              % (row, pend, want, r9e, r92, 'OK' if good else 'BAD'))
        if not good:
            ok = False
    print('ALL CHECKS PASSED' if ok else 'FAILURES')


if __name__ == '__main__':
    main()
