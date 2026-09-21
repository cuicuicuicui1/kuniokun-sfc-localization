"""bring verify16.py in line with the row-wipe build: the loader hook is gone,
the drawer blanks the row through the queue, and the queue guard really fires."""
import io

p = 'verify16.py'
s = io.open(p, encoding='utf-8', newline='').read()


def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (old[:70], s.count(old))
    s = s.replace(old, new)


# ---------------------------------------------------------------- A. hooks
rep("""mb, ma = cb.snes_of_rom(cb.E3_MSG)
""", "")
rep("""         (cb.HOOK_LOAD, bytes([0x5C, ma & 0xFF, ma >> 8, mb]), 'message blank JML'),
""",
    """         (cb.HOOK_LOAD, orig[cb.HOOK_LOAD:cb.HOOK_LOAD + 5],
          'line loader restored (the drawer blanks the rows)'),
""")

# ------------------------------------------------------------- helpers
rep("""def message_at(a):
    j = a
    while rom[j] != 0xF2:
        j += 1
    return bytes(rom[a:j])
""",
    """def message_at(a):
    j = a
    while rom[j] != 0xF2:
        j += 1
    return bytes(rom[a:j])


def wipe_row(row):
    \"\"\"the two queue entries that blank one text row (26 upper + 26 lower)\"\"\"
    out = b''
    for extra in (0, 0x20):
        addr = 0x7C03 + row * 0x40 + extra
        out += bytes([addr & 0xFF, addr >> 8, 0x80, 0x34]) + b'\\x00\\x2C' * 26
    return out


def room_limit(kind, col):
    \"\"\"the largest $09DF the drawer tolerates for one draw: it defers when
    $09DF + request would leave the 256 byte queue page $0B00-$0BFF\"\"\"
    if kind == 'occ':
        need = cb.ROW_WIPE + 8 if col == 0 else 8
    else:
        need = cb.ROW_WIPE_CHECK if (col == 0 or col >= cb.WRAP_COL) \\
            else cb.GLYPH_COST
    return 0x100 - need
""")

# ------------------------------------------------------------ C1. per byte
a1 = """        w = cpu.bus.wram
        staged = b''
        if cn or fx:
            if w[0x09DF] == stage:"""
a2 = """        stage += len(staged)"""
i1 = s.index(a1)
i2 = s.index(a2, i1) + len(a2)
new_c1 = """        w = cpu.bus.wram
        kind = 'cn' if (cn or fx) else 'occ'
        lim = room_limit(kind, col)
        # column 26 and beyond: the original drawer drops the character and
        # stages nothing, which is not a defer
        dropped = kind == 'occ' and col >= cb.MAX_COL
        staged = b''
        if w[0x09DF] == stage and not dropped:
            # no room left in the queue page: the next flush frees it and the
            # code is retried (the drawer cancels the consumer's $03e9 step)
            if stage <= lim:
                fail('entry %s byte %d: deferred with room ($09DF = $%02X '
                     'stage $%02X limit $%02X)'
                     % (key, i, w[0x09DF], stage, lim))
            if w[0x03E9] != ((i - 1) & 0xFF):
                fail('entry %s byte %d: deferred but $03E9 = $%02X want $%02X'
                     % (key, i, w[0x03E9], (i - 1) & 0xFF))
            if w[0x036F] != col:
                fail('entry %s byte %d: deferred but the column moved'
                     % (key, i))
            ok, _ = flush(cpu)
            flushes += 1
            if not ok:
                fail('entry %s: flusher did not return' % key)
            for word, want in sorted(vram_want.items()):
                got = b''.join(bytes([cpu.vram[word + k] & 0xFF,
                                      cpu.vram[word + k] >> 8])
                               for k in range(16))
                if got != want:
                    fail('entry %s: VRAM glyph $%04X differs' % (key, word))
            vram_want, tm_want = {}, {}
            stage = 0
            w[0x09DD] = 0
            continue                        # retry the same code
        if stage > lim:
            fail('entry %s byte %d: staged with no room ($09DF $%02X limit $%02X)'
                 % (key, i, w[0x09DF], lim))
        if col == 0:
            staged = wipe_row(row)          # a row starts: it is blanked first
        if kind == 'cn':
            ch = rev[(code - cb.PREFIX0, msg[i + 1])]
            slot = cell[ch][1]
            pa, pb = LEFT[slot], RIGHT[slot]
            vm_a, vm_b = 0x6000 + pa * 8, 0x6000 + pb * 8
            staged += (bytes([vm_a & 0xFF, vm_a >> 8, 0x80, 0x20]) +
                       pool_half(ch, 0) +
                       bytes([vm_b & 0xFF, vm_b >> 8, 0x80, 0x20]) +
                       pool_half(ch, 1))
            vram_want[vm_a] = pool_half(ch, 0)
            vram_want[vm_b] = pool_half(ch, 1)
            tiles = ((pa, pa + 1), (pb, pb + 1))
            want_e9 = (i + 1) & 0xFF
            if w[0x03E9] != want_e9:
                fail('entry %s byte %d: $03E9 = $%02X want $%02X'
                     % (key, i, w[0x03E9], want_e9))
        else:
            if dropped:
                tiles = None
            else:
                tiles = ((km.FB[code], km.FA[code]),)
        if tiles is not None:
            for k, (ta, tb) in enumerate(tiles):
                celladdr = 0x7C00 + row * 0x40 + 3 + col + k
                staged += bytes([celladdr & 0xFF, celladdr >> 8, 0x81, 0x04,
                                 ta | 0x00, 0x24, tb | 0x00, 0x24])
                tm_want[celladdr] = (ta | 0x2400, tb | 0x2400)
        got = bytes(w[0x0B00 + stage:0x0B00 + stage + len(staged)])
        if got != staged:
            fail('entry %s byte %d ($%02X): staged %s want %s'
                 % (key, i, code, got.hex(' '), staged.hex(' ')))
        stage += len(staged)"""
s = s[:i1] + new_c1 + s[i2:]

# the flush trigger must leave room for a row wipe as well
rep("""        if stage + 44 + cb.GLYPH_COST > 0xF0 or i >= len(msg):""",
    """        if stage + 44 + cb.ROW_WIPE_CHECK > 0xF0 or i >= len(msg):""")

# -------------------------------------------------- C2. original path parity
rep("""        for k in range(cb.QUEUE, cb.QUEUE + 0x40):
            if c1.bus.wram[k] != c2.bus.wram[k]:
                fail('C2 code $%02X row %d col %d: queue byte $%04X mine $%02X '
                     'original $%02X' % (code, row, col, k, c1.bus.wram[k],
                                         c2.bus.wram[k]))
                break
        for k in (0x036E, 0x036F, 0x09DF):
            if c1.bus.wram[k] != c2.bus.wram[k]:
                fail('C2 code $%02X: $%04X mine $%02X original $%02X'
                     % (code, k, c1.bus.wram[k], c2.bus.wram[k]))""",
    """        # at a row start my copy stages the row wipe before delegating
        off = cb.ROW_WIPE if col == 0 else 0
        if off:
            want_wipe = wipe_row(row)
            got_wipe = bytes(c1.bus.wram[cb.QUEUE:cb.QUEUE + off])
            if got_wipe != want_wipe:
                fail('C2 code $%02X row %d: row wipe %s want %s'
                     % (code, row, got_wipe.hex(' '), want_wipe.hex(' ')))
        for k in range(cb.QUEUE, cb.QUEUE + 0x40):
            if c1.bus.wram[k + off] != c2.bus.wram[k]:
                fail('C2 code $%02X row %d col %d: queue byte $%04X mine $%02X '
                     'original $%02X' % (code, row, col, k,
                                         c1.bus.wram[k + off],
                                         c2.bus.wram[k]))
                break
        for k in (0x036E, 0x036F):
            if c1.bus.wram[k] != c2.bus.wram[k]:
                fail('C2 code $%02X: $%04X mine $%02X original $%02X'
                     % (code, k, c1.bus.wram[k], c2.bus.wram[k]))
        if c1.bus.wram[0x09DF] != c2.bus.wram[0x09DF] + off:
            fail('C2 code $%02X: $09DF mine $%02X original $%02X (+%d)'
                 % (code, c1.bus.wram[0x09DF], c2.bus.wram[0x09DF], off))""")

# ------------------------------------------------------------ E and F
cut = s.index('# ------------------------------------------------- E. message box blanking')
s = s[:cut] + '''# ------------------------------------------- E. the drawer blanks a text row
print('E  a row start blanks the row through the queue')
cn_case = None
for r in recs:
    k_ = '%06X' % r['text_rom_off']
    if k_ not in addr:
        continue
    msg_ = message_at(addr[k_])
    for j, code_ in enumerate(msg_):
        if is_cn(code_) and j + 1 < len(msg_) and \\
                (code_ - cb.PREFIX0, msg_[j + 1]) in rev:
            cn_case = (k_, msg_, j)
            break
    if cn_case:
        break
if not cn_case:
    fail('E: no two byte Chinese code found')
key, msg, i = cn_case
ch = rev[(msg[i] - cb.PREFIX0, msg[i + 1])]
gslot = cell[ch][1]
gpa, gpb = LEFT[gslot], RIGHT[gslot]
occ_code = next(c for c in range(0x21, 0xF0)
                if not is_cn(c) and not is_fx(c) and km.FA[c] < 0x40)


def launch(kind, row, col, stage):
    """run one drawer call and check the invariants every call must keep."""
    code = msg[i] if kind == 'cn' else occ_code
    cpu = setup(msg if kind == 'cn' else bytes([occ_code]), 0, row, col,
                stage, code=code)
    before_wram = list(cpu.bus.wram)
    before_vram = list(cpu.vram)
    ok, steps = run_from(cpu)
    if not ok:
        fail('E %s row %d col %d: the drawer did not return (pc $%02X:%04X)'
             % (kind, row, col, cpu.pbr, cpu.pc))
        return None, b''
    if cpu.s != ((cpu.entry_s + 2) & 0xFFFF):
        fail('E %s: stack unbalanced ($%04X want $%04X)'
             % (kind, cpu.s, (cpu.entry_s + 2) & 0xFFFF))
    if cpu.dma_log:
        fail('E %s: the drawer must not DMA (%s)' % (kind, cpu.dma_log[0]))
    if cpu.vram != before_vram:
        fail('E %s: the drawer wrote VRAM instead of staging entries' % kind)
    allowed = (set(range(0x0100, 0x0200)) | set(range(0x0B00, 0x0C00))
               | {0x09DD, 0x09DF, 0x036F, 0x03E9})
    touched = sorted(set(x for x in range(len(before_wram))
                         if before_wram[x] != cpu.bus.wram[x]) - allowed)
    if touched:
        fail('E %s: the drawer wrote WRAM at %s'
             % (kind, ' '.join('$%04X' % x for x in touched[:8])))
    if any(cpu.bus.wram[x] != before_wram[x] for x in range(0x0D40, 0x0D60)):
        fail('E %s: the drawer wrote the scratch area $0D40-$0D5F' % kind)
    w = cpu.bus.wram
    return cpu, bytes(w[0x0B00 + stage:0x0B00 + w[0x09DF]])


def glyph_entries(slot):
    pa, pb = LEFT[slot], RIGHT[slot]
    out = b''
    for tile, half in ((pa, 0), (pb, 1)):
        vma = 0x6000 + tile * 8
        out += bytes([vma & 0xFF, vma >> 8, 0x80, 0x20]) + pool_half(ch, half)
    return out


def cell_entries(row, col, tiles):
    out = b''
    for k, (ta, tb) in enumerate(tiles):
        addr = 0x7C00 + row * 0x40 + 3 + col + k
        out += bytes([addr & 0xFF, addr >> 8, 0x81, 0x04, ta, 0x24, tb, 0x24])
    return out


row, col = 3, 0
cpu, staged = launch('cn', row, col, 0)
want = wipe_row(row) + glyph_entries(gslot) + \\
    cell_entries(row, col, ((gpa, gpa + 1), (gpb, gpb + 1)))
if len(want) != cb.ROW_WIPE_CHECK:
    fail('E: the row start expectation is %d bytes, ROW_WIPE_CHECK is %d'
         % (len(want), cb.ROW_WIPE_CHECK))
if staged != want:
    fail('E row start: staged %s want %s' % (staged.hex(' '), want.hex(' ')))
else:
    # make the wipe visible: fill the row, then flush and look at the cells
    for word in range(0x7C00 + row * 0x40, 0x7C00 + row * 0x40 + 0x40):
        cpu.vram[word] = 0x2CFE
    ok, _ = flush(cpu)
    if not ok:
        fail('E: the queue flusher did not return')
    else:
        blank = bad = 0
        for k in range(26):
            for base in (0x7C03 + row * 0x40 + k, 0x7C23 + row * 0x40 + k):
                want_word = 0x2C00
                if base == 0x7C00 + row * 0x40 + 3 + col:
                    want_word = gpa | 0x2400
                elif base == 0x7C00 + row * 0x40 + 4 + col:
                    want_word = gpb | 0x2400
                elif base == 0x7C00 + row * 0x40 + 3 + col + 0x20:
                    want_word = gpa + 1 | 0x2400
                elif base == 0x7C00 + row * 0x40 + 4 + col + 0x20:
                    want_word = gpb + 1 | 0x2400
                got = cpu.vram[base]
                if got != want_word:
                    if bad < 3:
                        fail('E row %d col $%02X = $%04X want $%04X'
                             % (row, base & 0x3F, got, want_word))
                    bad += 1
                elif got == 0x2C00:
                    blank += 1
        print('   row start: %d entries, %d of 52 cells blanked around the glyph'
              % (len(want), blank))

cpu, staged = launch('cn', row, 5, 0)
want = glyph_entries(gslot) + cell_entries(row, 5, ((gpa, gpa + 1), (gpb, gpb + 1)))
if staged != want:
    fail('E middle of row: staged %s want %s' % (staged.hex(' '), want.hex(' ')))
elif len(staged) != cb.GLYPH_COST:
    fail('E middle of row: %d staged bytes, GLYPH_COST is %d'
         % (len(staged), cb.GLYPH_COST))

cpu, staged = launch('occ', row, 0, 0)
want = wipe_row(row) + cell_entries(row, 0, ((km.FB[occ_code], km.FA[occ_code]),))
if staged != want:
    fail('E engine glyph row start: staged %s want %s'
         % (staged.hex(' '), want.hex(' ')))
else:
    for word in range(0x7C00 + row * 0x40, 0x7C00 + row * 0x40 + 0x40):
        cpu.vram[word] = 0x2CFE
    ok, _ = flush(cpu)
    if not ok:
        fail('E: the queue flusher did not return')
    if cpu.vram[0x7C00 + row * 0x40 + 3] != km.FB[occ_code] | 0x2400:
        fail('E engine glyph: cell $%04X = $%04X want $%04X'
             % (0x7C00 + row * 0x40 + 3, cpu.vram[0x7C00 + row * 0x40 + 3],
                km.FB[occ_code] | 0x2400))
    left = sum(1 for k in range(0x40)
               if cpu.vram[0x7C00 + row * 0x40 + k] == 0x2CFE)
    if left:
        fail('E engine glyph: %d cells of the row still hold the filler' % left)
    print('   engine glyph row start: wiped row then the original glyph entry')

cpu, staged = launch('occ', row, 5, 0)
want = cell_entries(row, 5, ((km.FB[occ_code], km.FA[occ_code]),))
if staged != want:
    fail('E engine glyph mid row: staged %s want %s'
         % (staged.hex(' '), want.hex(' ')))

# the guard: a draw that would leave the 256 byte page must be retried
for kind, col_, stage_ in (('cn', 0, 0x39), ('cn', 5, 0xA9), ('occ', 0, 0x89),
                           ('occ', 5, 0xF9)):
    cpu, staged = launch(kind, row, col_, stage_)
    if staged:
        fail('E guard %s col %d stage $%02X: staged %d bytes, want a defer'
             % (kind, col_, stage_, len(staged)))
        continue
    w = cpu.bus.wram
    if w[0x03E9] != 0xFF:
        fail('E guard %s col %d: $03E9 = $%02X, want the retry marker $FF'
             % (kind, col_, w[0x03E9]))
    if w[0x036F] != col_:
        fail('E guard %s col %d: the column moved to $%02X'
             % (kind, col_, w[0x036F]))
    if kind == 'cn' and w[0x09DF] != stage_:
        fail('E guard %s col %d: cursor moved to $%02X' % (kind, col_, w[0x09DF]))
print('   the guard defers a row start and a glyph that would leave the page')

# ------------------------------------------ F. one glyph, no hidden state
print('F  the drawer stages exactly what the pool holds')
cpu, staged = launch('cn', 2, 0, 0)
want = wipe_row(2) + glyph_entries(gslot) + \\
    cell_entries(2, 0, ((gpa, gpa + 1), (gpb, gpb + 1)))
if staged != want:
    fail('F: staged %s want %s' % (staged.hex(' '), want.hex(' ')))
ok, _ = flush(cpu)
if not ok:
    fail('F: the queue flusher did not return')
else:
    for tile, half in ((gpa, 0), (gpb, 1)):
        word = 0x6000 + tile * 8
        got = b''.join(bytes([cpu.vram[word + m] & 0xFF,
                              cpu.vram[word + m] >> 8]) for m in range(16))
        if got != pool_half(ch, half):
            fail('F: glyph tiles at $%04X differ from the pool' % word)
    for k, (ta, tb) in enumerate(((gpa, gpa + 1), (gpb, gpb + 1))):
        for delta, want_tile in ((0, ta), (0x20, tb)):
            word = 0x7C00 + 2 * 0x40 + 3 + k + delta
            if cpu.vram[word] != want_tile | 0x2400:
                fail('F: cell $%04X = $%04X want $%04X'
                     % (word, cpu.vram[word], want_tile | 0x2400))
    print('   %s glyph %s: %d staged bytes, tiles in VRAM equal the pool'
          % (key, ch, len(want)))

print()
if fails:
    print('%d FAILURES' % len(fails))
    raise SystemExit(1)
print('ALL CHECKS PASSED')
'''

io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('verify16 patched for the row wipe build')