"""Rewrite verify16.py for the stateless build.

E becomes "the message hook blanks the box text area", F becomes "the hook
leaves a continuation line alone", G becomes "the drawer emits exactly one
glyph entry and touches no WRAM outside the queue, the engine's own counters
and the stack".
"""
import io
import re

P = 'verify16.py'
s = io.open(P, encoding='utf-8', newline='').read()

# ---- A: the message hook replaces wipe + arm
old = """db, da = cb.snes_of_rom(cb.E3_DRAWER)
wb, wa = cb.snes_of_rom(cb.E3_WIPE)
ab, aa = cb.snes_of_rom(cb.E3_ARM)
sb, sa = cb.snes_of_rom(cb.B3_SANITIZE)
"""
new = """db, da = cb.snes_of_rom(cb.E3_DRAWER)
mb, ma = cb.snes_of_rom(cb.E3_MSG)
"""
assert s.count(old) == 1
s = s.replace(old, new)

old = "         (cb.HOOK_LOAD, bytes([0x5C, aa & 0xFF, aa >> 8, ab]), 'message arm JML'),"
new = "         (cb.HOOK_LOAD, bytes([0x5C, ma & 0xFF, ma >> 8, mb]), 'message blank JML'),"
assert s.count(old) == 1
s = s.replace(old, new)

old = """         (cb.HOOK_DRIVER, orig[cb.HOOK_DRIVER:cb.HOOK_DRIVER + 4],
          'driver entry untouched (the drawer calls the stager)'),"""
new = """         (cb.HOOK_DRIVER, orig[cb.HOOK_DRIVER:cb.HOOK_DRIVER + 4],
          'driver entry untouched (the drawer blanks nothing itself)'),"""
assert s.count(old) == 1
s = s.replace(old, new)

# ---- C1 helper: no wipe scratch any more
old = """def setup(msg, i, row, col, stage, src=rom, base=cb.E3_DRAWER, code=None, cpu=None,
          wipe=0):"""
new = """def setup(msg, i, row, col, stage, src=rom, base=cb.E3_DRAWER, code=None, cpu=None):"""
assert s.count(old) == 1
s = s.replace(old, new)

old = """    w[0x09DF] = stage
    w[cb.WIPE_PEND] = wipe
    w[0x12] ="""
new = """    w[0x09DF] = stage
    w[0x12] ="""
assert s.count(old) == 1
s = s.replace(old, new)

# ---- cut everything from the old E section on and rebuild it
cut = s.index('# ----------------------------------------------------------------- E. wipe')
head = s[:cut]
tail = """# ------------------------------------------------- E. message box blanking
print('E  message hook blanks the box text area')


def msg_setup(flag73, cpu=None):
    \"\"\"Enter the hook the way the loader does: JML from $03:EB9E with M = X = 8
    and DBR = $03, holding the five bytes the hook took over in its head.\"\"\"
    if cpu is None:
        cpu = sim65816.CPU(rom)
    bb, ba = cb.snes_of_rom(cb.E3_MSG)
    cpu.pbr, cpu.pc = bb, ba
    cpu.m8 = cpu.x8 = True
    cpu.db = 0x03
    cpu.bus.wram[0x0373] = flag73
    cpu.bus.wram[0x0011] = 0x5A          # loader state the hook must not touch
    cpu.bus.wram[0x03E8] = 0x5B
    cpu.bus.wram[0x03E9] = 0x5C
    cpu.bus.wram[0x036A] = 0x5D
    cpu.bus.wram[0x036B] = 0x5E
    cpu.push8(0x03)                      # the loader reached us through a JML
    cpu.push8(0xBB)
    cpu.push8(0xEB)
    cpu.entry_s = cpu.s
    return cpu


boxes = [(0x00, True), (0x40, False), (0x80, True), (0x41, False)]
for flag73, want_blank in boxes:
    cpu = msg_setup(flag73)
    before = list(cpu.bus.wram)
    ok, steps = run_to(cpu, 0x03, 0xEBA3)
    if not ok:
        fail('E: the message hook did not hand control back to the loader '
             '(pc $%02X:%04X)' % (cpu.pbr, cpu.pc))
        continue
    if cpu.s != cpu.entry_s:
        fail('E: the message hook left the stack unbalanced ($%04X want $%04X)'
             % (cpu.s, cpu.entry_s))
    w = cpu.bus.wram
    if not (w[0x0373] & 0x40):
        fail('E: the replayed TSB did not set bit 6 ($0373 = $%02X)' % w[0x0373])
    if (w[0x0373] & 0xBF) != (flag73 & 0xBF):
        fail('E: $0373 = $%02X lost bits of $%02X' % (w[0x0373], flag73))
    touched = sorted(i for i in range(len(before)) if before[i] != w[i])
    if touched != [0x0373]:
        fail('E: flag $%02X changed WRAM at %s (want only $0373)'
             % (flag73, ' '.join('$%04X' % i for i in touched[:8])))
    if cpu.vmain != 0:
        fail('E: the hook changed VMAIN ($2115 = $%02X)' % cpu.vmain)
    bad = []
    for row in range(16):
        for col in range(64):
            word = 0x7C00 + row * 0x40 + col
            text = 1 <= col <= 30 or 33 <= col <= 62
            want = 0x2C00 if (want_blank and text) else 0
            if cpu.vram[word] != want:
                bad.append('$%04X = $%04X want $%04X' % (word, cpu.vram[word], want))
    for word in range(0x7C00):
        if cpu.vram[word]:
            bad.append('$%04X outside the text area was written' % word)
    if bad:
        fail('E: flag $%02X box %s: %s%s'
             % (flag73, 'blanked' if want_blank else 'kept',
                '; '.join(bad[:4]), '' if len(bad) <= 4 else ' (+%d)' % (len(bad) - 4)))
print('   %d message entries (%d blanked the text area, %d left it alone)'
      % (len(boxes), sum(1 for _, b in boxes if b), sum(1 for _, b in boxes if not b)))

# ------------------------------------------------ F. one glyph, no side state
print('F  drawer emits one glyph and keeps no hidden state')
found = None
for r in recs:
    key = '%06X' % r['text_rom_off']
    if key not in addr:
        continue
    msg = message_at(addr[key])
    for i, code in enumerate(msg):
        if is_cn(code) and i + 1 < len(msg):
            if (code - cb.PREFIX0, msg[i + 1]) in rev:
                found = (key, msg, i)
                break
    if found:
        break
if not found:
    fail('F: no message with a two byte code to test with')
else:
    key, msg, i = found
    ch = rev[(msg[i] - cb.PREFIX0, msg[i + 1])]
    gpage, gslot = cell[ch]
    cpu = setup(msg, i, 2, 0, 0, code=msg[i])
    w = cpu.bus.wram
    before_wram = list(w)
    before_vram = list(cpu.vram)
    ok, steps = run_from(cpu)
    if not ok:
        fail('F: the drawer did not return to bank $03 (pc $%02X:%04X)'
             % (cpu.pbr, cpu.pc))
    if cpu.s != ((cpu.entry_s + 2) & 0xFFFF):
        fail('F: the drawer left the stack unbalanced ($%04X want $%04X)'
             % (cpu.s, (cpu.entry_s + 2) & 0xFFFF))
    if cpu.dma_log:
        fail('F: the drawer must not DMA (%s)' % (cpu.dma_log[0],))
    if cpu.vram != before_vram:
        fail('F: the drawer wrote VRAM itself instead of staging entries')
    # only the queue, the engine's own cursors/counters and the glyph code may
    # change: any other byte would mean the drawer keeps hidden state in WRAM
    allowed = set(range(0x0B00, 0x0C00)) | {0x09DD, 0x09DF, 0x036F, 0x03E9}
    touched = sorted(set(x for x in range(len(before_wram))
                         if before_wram[x] != w[x]) - allowed)
    if touched:
        fail('F: the drawer wrote WRAM at %s'
             % ' '.join('$%04X' % x for x in touched[:8]))
    if any(w[x] != before_wram[x] for x in range(0x0D40, 0x0D60)):
        fail('F: the drawer wrote the scratch area $0D40-$0D5F')
    # exactly one glyph: two bitmap entries and two tile map entries
    row_addr = 0x7C03 + 2 * 0x40
    want = b''
    for k, tile in ((0, LEFT[gslot]), (1, RIGHT[gslot])):
        vma = 0x6000 + tile * 8
        want += bytes([vma & 0xFF, vma >> 8, 0x80, 32]) + pool_half(ch, k)
    want += bytes([row_addr & 0xFF, row_addr >> 8, 0x81, 0x04,
                   LEFT[gslot], 0x24, LEFT[gslot] + 1, 0x24])
    want += bytes([(row_addr + 1) & 0xFF, (row_addr + 1) >> 8, 0x81, 0x04,
                   RIGHT[gslot], 0x24, RIGHT[gslot] + 1, 0x24])
    if len(want) != cb.GLYPH_COST:
        fail('F: the expectation is %d bytes, GLYPH_COST is %d'
             % (len(want), cb.GLYPH_COST))
    got = bytes(w[0x0B00:0x0B00 + len(want)])
    if got != want:
        fail('F: staged %s want %s' % (got.hex(' '), want.hex(' ')))
    ok, _ = flush(cpu)
    if not ok:
        fail('F: the queue flusher did not return')
    else:
        for k, want_tiles in ((0, (LEFT[gslot], LEFT[gslot] + 1)),
                              (1, (RIGHT[gslot], RIGHT[gslot] + 1))):
            word = 0x6000 + want_tiles[0] * 8
            got = b''.join(bytes([cpu.vram[word + m] & 0xFF,
                                  cpu.vram[word + m] >> 8]) for m in range(16))
            if got != pool_half(ch, k):
                fail('F: glyph tiles at $%04X differ from the pool' % word)
            for delta in (0, 0x20):
                cell_word = row_addr + k + delta
                want_word = want_tiles[0 if delta == 0 else 1] | 0x2400
                if cpu.vram[cell_word] != want_word:
                    fail('F: cell $%04X = $%04X want $%04X'
                         % (cell_word, cpu.vram[cell_word], want_word))
    print('   %s glyph %s (page %d slot %d): %d staged bytes, no VRAM or WRAM '
          'side effects' % (key, ch, gpage, gslot, len(want)))

print()
if fails:
    print('%d FAILURES' % len(fails))
    raise SystemExit(1)
print('ALL CHECKS PASSED')
"""
io.open(P, 'w', encoding='utf-8', newline='').write(head + tail)
print('rewrote %s (%d -> %d bytes)' % (P, len(s), len(head + tail)))