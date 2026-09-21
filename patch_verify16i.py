"""Verify-side follow-up for the drawer-called wipe.

* the stager is reached with JSL and must therefore end in RTL (a JSL/RTS pair
  leaks one byte of stack per glyph);
* A: the driver entry keeps its original bytes, the drawer holds the JSL;
* E: call the stager the way the drawer does and check both the staged row and
  the bookkeeping (WIPE_TOP/WIPE_BOT belong to the drawer and must survive);
* G: run the drawer once with a wipe pending and prove that the wiped row and
  the glyph reach VRAM in one flush, wiped first.
"""
import io

# ---------------------------------------------------------------- builder: RTL
P = 'cnbuild5.py'
s = io.open(P, encoding='utf-8', newline='').read().replace('\r\n', '\n')
old = """    a.label('out')
    a.hexs('AB 28 18 60')                  # plb / plp / clc / rts
    return a.done()"""
new = """    a.label('out')
    a.hexs('AB 28 18 6B')                  # plb / plp / clc / rtl
    return a.done()"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
s = s.replace("""    a = Asm(E3_WIPE)
    a.hexs('08 8B E2 30')                  # php / phb / sep #$30""",
              """    a = Asm(E3_WIPE)
    a.hexs('08 8B E2 30')                  # php / phb / sep #$30""")
io.open(P, 'w', encoding='utf-8', newline='\n').write(s)
print('cnbuild5: stager epilogue -> RTL')

# --------------------------------------------------------------- verify16: A
P = 'verify16.py'
s = io.open(P, encoding='utf-8', newline='').read().replace('\r\n', '\n')


def sub(old, new, tag):
    global s
    assert s.count(old) == 1, (tag, s.count(old))
    s = s.replace(old, new)
    print('patched', tag)


sub("""         (cb.HOOK_DRIVER, bytes([0x5C, wa & 0xFF, wa >> 8, wb]), 'wipe stager JML'),""",
    """         (cb.HOOK_DRIVER, orig[cb.HOOK_DRIVER:cb.HOOK_DRIVER + 4],
          'driver entry untouched (the drawer calls the stager)'),""", 'A driver')

# --------------------------------------------------------------- verify16: E
sub("""def wipe_setup(pend, cur, top, bot, stage, cpu=None):
    if cpu is None:
        cpu = sim65816.CPU(rom)
    wb_, wa_ = cb.snes_of_rom(cb.E3_WIPE)
    cpu.pbr, cpu.pc = wb_, wa_
    cpu.m8 = cpu.x8 = True
    cpu.db = 0x00
    w = cpu.bus.wram
    w[cb.WIPE_PEND], w[cb.WIPE_CUR] = pend, cur
    w[cb.WIPE_TOP], w[cb.WIPE_BOT] = top, bot
    w[0x09DF] = stage
    w[0x09DD] = stage                       # the queue is flushed: cursors equal
    cpu.push8(0x03)                         # the engine's JML: PBR = $3E, no RTS
    cpu.push8(0xEE)
    cpu.push8(0x73)
    cpu.entry_s = cpu.s
    return cpu


rows_seen = []
cpu = None
for pend, cur, top, bot in ((1, 2, 1, 2), (1, 1, 1, 1)):
    cpu = wipe_setup(pend, cur, top, bot, 0)
    ok, steps = run_to(cpu, 0x03, 0xEE74)
    if not ok:
        fail('E: the stager did not hand control back to the driver '
             '(pc $%02X:%04X)' % (cpu.pbr, cpu.pc))
        continue
    # the stager deliberately leaves its PHP/PHB pushes for the driver epilogue
    if cpu.s != ((cpu.entry_s - 2) & 0xFFFF):
        fail('E: the stager stack is $%04X want $%04X' % (cpu.s,
                                                          (cpu.entry_s - 2) & 0xFFFF))
    w = cpu.bus.wram
    n = w[0x09DF]
    rows_seen.append((cur, top, bot, n, w[cb.WIPE_CUR], w[cb.WIPE_PEND]))
    if n not in (0, 2 * (4 + 52)):
        fail('E: staged $%02X bytes for one row (want $70)' % n)
    if n:
        # two runs per row: 26 upper halves at $7C03+row*$40 and the 26 lower
        # halves $20 words further on; each run is a 4 byte header plus 52 bytes
        for k, delta in enumerate((0, 0x20)):
            base = k * (4 + 52)
            lo, hi, vm, cnt = w[0x0B00 + base], w[0x0B00 + base + 1], \\
                w[0x0B00 + base + 2], w[0x0B00 + base + 3]
            want_addr = (0x7C03 + (cur & 0x0F) * 0x40 + delta) & 0xFFFF
            if lo | (hi << 8) != want_addr or vm != 0x80 or cnt != 52:
                fail('E: row %d run %d header $%02X%02X/$%02X/$%02X want '
                     '$%04X/$80/$34' % (cur, k, hi, lo, vm, cnt, want_addr))
            for c in range(26):
                if w[0x0B00 + base + 4 + c * 2] | (w[0x0B00 + base + 5 + c * 2] << 8) != 0x2C00:
                    fail('E: row %d run %d cell %d is not a blank' % (cur, k, c))
    if cur <= top:
        if w[cb.WIPE_PEND] != 0 or w[cb.WIPE_TOP] != 0x10 or w[cb.WIPE_BOT] != 0:
            fail('E: completion state pend $%02X top $%02X bot $%02X'
                 % (w[cb.WIPE_PEND], w[cb.WIPE_TOP], w[cb.WIPE_BOT]))
    else:
        if w[cb.WIPE_CUR] != cur - 1:
            fail('E: cursor $%02X want $%02X' % (w[cb.WIPE_CUR], cur - 1))
print('   %d stager runs: %s' % (len(rows_seen), rows_seen))""",
    """def wipe_setup(cur, lo, top, bot, stage, pend=1, cpu=None):
    \"\"\"Call the stager exactly like the drawer does: JSL from bank $3E with
    DBR = $03, returning through RTL.\"\"\"
    if cpu is None:
        cpu = sim65816.CPU(rom)
    wb_, wa_ = cb.snes_of_rom(cb.E3_WIPE)
    cpu.pbr, cpu.pc = wb_, wa_
    cpu.m8 = cpu.x8 = True
    cpu.db = 0x03                            # the text engine's data bank
    w = cpu.bus.wram
    w[cb.WIPE_PEND], w[cb.WIPE_CUR] = pend, cur
    w[cb.WIPE_LO], w[cb.WIPE_TOP], w[cb.WIPE_BOT] = lo, top, bot
    w[0x09DF] = stage
    w[0x09DD] = stage                       # the queue is flushed: cursors equal
    cpu.push8(cpu.pbr)                      # JSL frame: PBR, then the return PC
    cpu.push8(0x98)                         # RTL adds one, so this lands on $9900
    cpu.push8(0xFF)
    cpu.entry_s = cpu.s
    return cpu


rows_seen = []
cpu = None
for cur, lo, top, bot in ((2, 1, 0x10, 2), (1, 1, 0x10, 2), (0, 0, 0x10, 0)):
    cpu = wipe_setup(cur, lo, top, bot, 0)
    ok, steps = run_to(cpu, 0x3E, 0x9900)
    if not ok:
        fail('E: the stager did not return to its caller (pc $%02X:%04X '
             's $%04X want $%04X)' % (cpu.pbr, cpu.pc, cpu.s, cpu.entry_s))
        continue
    if cpu.s != cpu.entry_s:
        fail('E: the stager leaked stack (s $%04X want $%04X)'
             % (cpu.s, cpu.entry_s))
    w = cpu.bus.wram
    n = w[0x09DF]
    rows_seen.append((cur, n, w[cb.WIPE_CUR], w[cb.WIPE_PEND]))
    if n not in (0, 2 * (4 + 52)):
        fail('E: staged $%02X bytes for one row (want $70)' % n)
    if n:
        # two runs per row: 26 upper halves at $7C03+row*$40 and the 26 lower
        # halves $20 words further on; each run is a 4 byte header plus 52 bytes
        for k, delta in enumerate((0, 0x20)):
            base = k * (4 + 52)
            lo_, hi_, vm, cnt = w[0x0B00 + base], w[0x0B00 + base + 1], \\
                w[0x0B00 + base + 2], w[0x0B00 + base + 3]
            want_addr = (0x7C03 + (cur & 0x0F) * 0x40 + delta) & 0xFFFF
            if lo_ | (hi_ << 8) != want_addr or vm != 0x80 or cnt != 52:
                fail('E: row %d run %d header $%02X%02X/$%02X/$%02X want '
                     '$%04X/$80/$34' % (cur, k, hi_, lo_, vm, cnt, want_addr))
            for c in range(26):
                if w[0x0B00 + base + 4 + c * 2] | (w[0x0B00 + base + 5 + c * 2] << 8) != 0x2C00:
                    fail('E: row %d run %d cell %d is not a blank' % (cur, k, c))
    # WIPE_TOP/WIPE_BOT track the rows the current message drew into: the wipe
    # must leave them alone, and only clear its own flag when it is done
    if w[cb.WIPE_TOP] != top or w[cb.WIPE_BOT] != bot:
        fail('E: the stager clobbered the drawn-row window (top $%02X bot $%02X '
             'want $%02X/$%02X)' % (w[cb.WIPE_TOP], w[cb.WIPE_BOT], top, bot))
    if cur <= lo:
        if w[cb.WIPE_PEND] != 0 or w[cb.WIPE_CUR] != 0x10:
            fail('E: completion state pend $%02X cur $%02X' % (w[cb.WIPE_PEND],
                                                               w[cb.WIPE_CUR]))
    else:
        if w[cb.WIPE_PEND] != 1 or w[cb.WIPE_CUR] != cur - 1:
            fail('E: cursor $%02X want $%02X (pend $%02X)'
                 % (w[cb.WIPE_CUR], cur - 1, w[cb.WIPE_PEND]))
# nothing to wipe: the stager must do nothing at all
cpu = wipe_setup(2, 1, 0x10, 2, 0, pend=0)
ok, _ = run_to(cpu, 0x3E, 0x9900)
if not ok or cpu.bus.wram[0x09DF] != 0:
    fail('E: the stager staged bytes with no wipe pending')
print('   %d stager runs: %s' % (len(rows_seen), rows_seen))""", 'E rewrite')

# --------------------------------------------------------------- verify16: G
sub("""print()
if fails:""",
    """# -------------------------------------------- G. wipe and glyph in one flush
print('G  wipe row + glyph in one flush')
found = None
for r in recs:
    key = '%06X' % r['text_rom_off']
    if key not in addr:
        continue
    msg = message_at(addr[key])
    for i, code in enumerate(msg):
        if is_cn(code) and code + 1 < len(msg):
            from_page = code - cb.PREFIX0
            if (from_page, msg[i + 1]) in rev:
                found = (key, msg, i)
                break
    if found:
        break
if not found:
    fail('G: no message with a two byte code to test with')
else:
    key, msg, i = found
    ch = rev[(msg[i] - cb.PREFIX0, msg[i + 1])]
    gpage, gslot = cell[ch]
    cpu = setup(msg, i, 2, 0, 0, code=msg[i], wipe=1)
    w = cpu.bus.wram
    w[cb.WIPE_CUR], w[cb.WIPE_LO] = 2, 1
    w[cb.WIPE_TOP], w[cb.WIPE_BOT] = 0x10, 2
    ok, steps = run_from(cpu)
    if not ok:
        fail('G: the drawer did not return to bank $03 (pc $%02X:%04X)'
             % (cpu.pbr, cpu.pc))
    else:
        row_addr = 0x7C03 + 2 * 0x40
        want = b''
        for delta in (0, 0x20):
            want += bytes([(row_addr + delta) & 0xFF, (row_addr + delta) >> 8,
                           0x80, 52]) + bytes([0x00, 0x2C]) * 26
        want += bytes([(row_addr) & 0xFF, (row_addr) >> 8, 0x81, 0x04,
                       LEFT[gslot], 0x24, LEFT[gslot] + 1, 0x24])
        want += bytes([(row_addr + 1) & 0xFF, (row_addr + 1) >> 8, 0x81, 0x04,
                       RIGHT[gslot], 0x24, RIGHT[gslot] + 1, 0x24])
        got = bytes(w[0x0B00:0x0B00 + len(want)])
        if got != want:
            fail('G: staged %s want %s' % (got.hex(' '), want.hex(' ')))
        ok, _ = flush(cpu)
        if not ok:
            fail('G: the queue flusher did not return')
        else:
            # the wipe ran first: cells the glyph did not claim are blank ...
            for c in range(3, 26):
                for delta in (0, 0x20):
                    if cpu.vram[row_addr + c + delta] != 0x2C00:
                        fail('G: cell $%04X = $%04X after the wipe (want blank)'
                             % (row_addr + c + delta,
                                cpu.vram[row_addr + c + delta]))
            # ... and the glyph still owns its own four cells
            pair = None
            for k, want_tiles in ((0, (LEFT[gslot], LEFT[gslot] + 1)),
                                  (1, (RIGHT[gslot], RIGHT[gslot] + 1))):
                for delta in (0, 0x20):
                    word = row_addr + k + delta
                    want_word = (want_tiles[0 if delta == 0 else 1] | 0x2400)
                    if cpu.vram[word] != want_word:
                        fail('G: glyph cell $%04X = $%04X want $%04X'
                             % (word, cpu.vram[word], want_word))
            for k, want_tiles in ((0, (LEFT[gslot], LEFT[gslot] + 1)),
                                  (1, (RIGHT[gslot], RIGHT[gslot] + 1))):
                word = 0x6000 + want_tiles[0] * 8
                got = b''.join(bytes([cpu.vram[word + m] & 0xFF,
                                      cpu.vram[word + m] >> 8])
                               for m in range(16))
                if got != pool_half(ch, k):
                    fail('G: glyph tiles at $%04X differ from the pool' % word)
        print('   %s glyph %s (page %d slot %d) with row 2 pending: '
              'row wiped, glyph drawn' % (key, ch, gpage, gslot))

print()
if fails:""", 'G section')

io.open(P, 'w', encoding='utf-8', newline='\n').write(s)
print('written', P)