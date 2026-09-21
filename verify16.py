"""End-to-end verification of the 16x16 Chinese patch for 初代熱血硬派くにおくん.

  A  patch sites, widget path restored, slot table, pool
  B  every rebuilt entry: decode round-trip == translation
  C1 every entry: simulate the patched drawer byte by byte, run the engine's own
     queue flusher, compare the glyph tiles and the tile map words in VRAM
  C2 the delegated original path must stage exactly what the original drawer does
  D  colouring: glyphs that can share a screen never share a slot
  E  box wipe stager: one row per flush, cursor walk, completion
  F  message arm hook: arms the wipe on a new entry only

Usage: python -u verify16.py
"""
import json

import kuniokun_map as km
import cnbuild5 as cb
cb.load_build_params()   # the switches this ROM was built with
import sim65816
import cnglyph

BASE = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon'

rom = open(cb.OUT_ROM, 'rb').read()
orig = open(cb.ORIG_ROM, 'rb').read()
tr = json.load(open(BASE + '/cn_translation.json', encoding='utf-8'))
recs = json.load(open(BASE + '/kuniokun_text.json', encoding='utf-8'))
addr = json.load(open(BASE + '/cn_addr_map.json', encoding='utf-8'))
par = json.load(open(BASE + '/cn_build_params.json', encoding='utf-8'))
cb.KEEP1.clear()
cb.KEEP1.update({k: v for k, v in par['keep1'].items()})
cb.SLOTS = par['slots']
cb.PAGES = par['pages']
cb.FIXED0 = par['fixed0']
cb.FIXED_N = par['fixed_n']
cb.FIXED_CODES.clear()
cb.FIXED_CODES.update(par['fixed'])
cb.ITEM_CHARS.clear()
cb.ITEM_CHARS.update({k: int(v) for k, v in par['item_chars'].items()})
cell = {k: tuple(v) for k, v in
        json.load(open(BASE + '/cn_glyph_cell.json', encoding='utf-8')).items()}
rev = {}
for _ch, (_p, _i) in cell.items():
    rev.setdefault((_p, _i), _ch)

# the table stride carries the two speaker name label pairs as well
NPAIR = (cb.SLOTS + cb.LABEL_GLYPHS * cb.LABEL_SETS
         + cb.LABEL_NAME_GLYPHS * cb.LABEL_NAME_SETS)
LEFT = rom[cb.E3_SLOTPAIR:cb.E3_SLOTPAIR + NPAIR]
RIGHT = rom[cb.E3_SLOTPAIR + NPAIR:cb.E3_SLOTPAIR + 2 * NPAIR]
fails = []


def fail(msg):
    fails.append(msg)
    if len(fails) <= 40:
        print('  FAIL ' + msg)


def glyph64(ch):
    return cb.glyph64(ch)


def is_cn(b):
    return cb.PREFIX0 <= b < cb.PREFIX0 + cb.PAGES


def is_fx(b):
    return cb.FIXED0 <= b < cb.FIXED0 + cb.FIXED_N


def message_at(a):
    j = a
    while rom[j] != 0xF2:
        j += 1
    return bytes(rom[a:j])


def wipe_row(row):
    """the two queue entries that blank one text row (26 upper + 26 lower)"""
    out = b''
    for extra in (0, 0x20):
        addr = 0x7C03 + row * 0x40 + extra
        out += bytes([addr & 0xFF, addr >> 8, 0x80, 0x34]) + b'\x00\x2C' * 26
    return out


def room_limit(kind, col):
    """the largest $09DF the drawer tolerates for one draw: it defers when
    $09DF + request would leave the 256 byte queue page $0B00-$0BFF"""
    if kind == 'occ':
        need = cb.ROW_WIPE + 8 if col == 0 else 8
    else:
        need = cb.ROW_WIPE_CHECK if (col == 0 or col >= cb.WRAP_COL) \
            else cb.GLYPH_COST
    return 0x100 - need


# ---------------------------------------------------------------- A. structure
print('A  patch sites / slot table / pool')
db, da = cb.snes_of_rom(cb.E3_DRAWER)
hooks = [(cb.HOOK_DRAWER, bytes([0x5C, da & 0xFF, da >> 8, db]), 'drawer JML'),
         (cb.HOOK_DRIVER, orig[cb.HOOK_DRIVER:cb.HOOK_DRIVER + 4],
          'driver entry untouched (the drawer blanks nothing itself)'),
         (cb.HOOK_LOAD, orig[cb.HOOK_LOAD:cb.HOOK_LOAD + 5],
          'line loader restored (the drawer blanks the rows)'),
         (cb.HOOK_COPY1, orig[cb.HOOK_COPY1:cb.HOOK_COPY1 + 3],
          'macro sanitizer call removed 1'),
         (cb.HOOK_COPY2, orig[cb.HOOK_COPY2:cb.HOOK_COPY2 + 3],
          'macro sanitizer call removed 2'),
         (cb.HOOK_A, orig[cb.HOOK_A:cb.HOOK_A + 4], 'widget preload restored'),
         (cb.HOOK_KEEP_BANK, orig[cb.HOOK_KEEP_BANK:cb.HOOK_KEEP_BANK + 2],
          'widget bank keep restored'),
         (cb.HOOK_B, orig[cb.HOOK_B:cb.HOOK_B + 4], 'widget dispatch restored')]
for off, want, name in hooks:
    got = rom[off:off + len(want)]
    if got != want:
        fail('%s @0x%06X = %s want %s' % (name, off, got.hex(' '), want.hex(' ')))
sb, sa = cb.snes_of_rom(cb.B3_SANITIZE)          # unused now
built = cb.build_slotpairs()
if rom[cb.E3_SLOTPAIR:cb.E3_SLOTPAIR + 2 * NPAIR] != built[0]:
    fail('slot pair table differs')
if rom[cb.E3_SLOTHI:cb.E3_SLOTHI + 2 * NPAIR] != built[1]:
    fail('slot high byte table differs')
HI = rom[cb.E3_SLOTHI:cb.E3_SLOTHI + 2 * NPAIR]
pairs = [rom[cb.E3_SLOTPAIR + i] | (HI[i] << 8) for i in range(2 * NPAIR)]
if len(set(pairs)) != len(pairs):
    fail('slot pair table has duplicates')
free = cb.free_pairs()
for p in pairs:
    if p < 256 and p not in free:
        fail('slot pair %d is not free' % p)
out = sorted(p for p in pairs if p >= 256)
if out != sorted(cb.OUTSIDE_PAIRS[:len(out)]):
    fail('label pairs outside the font window are %s' % out)
for t in sorted(cb.protected_tiles()):
    # The choice box's own tiles are protected *and* rewritten on purpose: the
    # box draws them straight out of the font, so choice_box() bakes 是/否 into
    # them.  Everything else that is protected must still be the original glyph.
    if t in cb.CHOICE_YES_TILES or t in cb.CHOICE_NO_TILES:
        continue
    off = 0x0F8000 + t * 16
    if rom[off:off + 16] != orig[off:off + 16]:
        fail('protected font tile 0x%02X was overwritten' % t)
n = 0
for ch, (page, slot) in cell.items():
    off = cb.POOL_ROM + page * 0x8000 + slot * cb.POOL_STRIDE
    if rom[off:off + cb.POOL_STRIDE] != glyph64(ch):
        fail('pool glyph %s (page %d slot %d) wrong' % (ch, page, slot))
    n += 1
print('   %d hooks ok, %d slots (%d free pairs), %d glyphs in the pool'
      % (len(hooks), len(pairs), len(free), n))

# ------------------------------------------------------- B. text round-trip
print('B  text round-trip (%d entries)' % len(recs))
_orig_text = {'%06X' % r['text_rom_off']: r['text'] for r in recs}
# exactly the builder's pipeline: align to the original control codes, then let
# the drawer wrap over-long lines at run time (no stored breaks)
fixed = {k: cb.align_tokens(_orig_text[k], v)
         for k, v in tr.items() if k in _orig_text}

# entries whose table is kept in Japanese (NO_TRANSLATE): verify the byte image is
# untouched and that no Chinese code leaks into them
NO_TR = set()
# the label codes: read from the slot table the build wrote
LABEL_CODES = set(c for c in range(256)
                  if rom[0x1F4B00 + c] != 0xFF)
for _t, _r in zip(cb.TABLES, cb.REGIONS):
    if _t[0] in cb.NO_TRANSLATE:
        for r in recs:
            if _r[0] <= r['text_rom_off'] < _r[1]:
                NO_TR.add('%06X' % r['text_rom_off'])


def _dec(ch, item=False):
    """byte image of my rebuilt text, up to and including the F3 terminator.
    Control tokens contribute their literal bytes so the comparison is bytewise.
    Shadowed name glyphs (PRIME + char) are one unit, like in the builder.
    item=True uses the item names' own code: [ITEM_PREFIX][8x16 id] instead
    of the glyph pool's two byte code, because their renderer uploads from
    its own table and never touches a pool slot."""
    out, i = [], 0
    while i < len(ch):
        c = ch[i]
        if c == '{':
            j = ch.index('}', i)
            for b in bytes.fromhex(ch[i + 1:j]):
                out.append(b)
                if b == 0xF3:
                    return out
            i = j + 1
            continue
        if c == ' ':
            out.append(0x00)
        elif c in cb.KEEP1:
            out.append(cb.KEEP1[c])
        elif c in cb.FIXED_CODES:
            out.append(cb.FIXED_CODES[c])
        elif item:
            out.append(cb.ITEM_PREFIX)
            out.append(cb.ITEM_CHARS[c])
        else:
            p_ = cell[c]
            out.append(cb.PREFIX0 + p_[0])
            out.append(p_[1])
        i += 1
    return out


def _act(a, image=None):
    """byte image stored at a, up to and including the F3 terminator."""
    img = rom if image is None else image
    out, i = [], a
    while True:
        b = img[i]
        out.append(b)
        i += 1
        if b == 0xF3:
            return out


checked = 0
for r in recs:
    key = '%06X' % r['text_rom_off']
    checked += 1
    if key in NO_TR:
        off = r['text_rom_off']
        a_, b_ = _act(off), _act(off, orig)
        # The item window is dead code, so its group is not protected any more
        # and the build leaves the region exactly as the original has it.  While
        # the group *is* protected the kana rewrite is what we expect there.
        want_jp = (cb.rewrite_kana(bytes(b_)) if 'item' in cb.PROTECT_GROUPS
                   else bytes(b_))
        if bytes(a_) != want_jp:
            fail('entry %s (japanese table) differs from the kana rewrite: '
                 '%s want %s' % (key, bytes(a_)[:12].hex(' '), want_jp[:12].hex(' ')))
        elif any(is_cn(x) or is_fx(x) for x in a_[:-1]):
            fail('entry %s (japanese table) contains Chinese codes' % key)
        continue
    if key not in addr:
        fail('entry %s has no rebuilt address' % key)
        continue
    want = _dec(fixed[key] if key in fixed else _orig_text[key],
                item=(r['table_rom_off'] == cb.ITEM_TABLE))
    got = _act(addr[key])
    if got != want:
        nm = min(len(got), len(want))
        k = next((i for i in range(nm) if got[i] != want[i]), nm)
        fail('entry %s mismatch at byte %d: got %s want %s'
             % (key, k, ['%02X' % x for x in got[k:k + 4]],
                ['%02X' % x for x in want[k:k + 4]]))
print('   %d entries decoded' % checked)

# --------------------------------------------------------- C1. drawer sim
print('C1 drawer simulation')


def setup(msg, i, row, col, stage, src=rom, base=cb.E3_DRAWER, code=None, cpu=None):
    if cpu is None:
        cpu = sim65816.CPU(src)
    cpu.pbr, cpu.pc = base // 0x8000, 0x8000 + (base % 0x8000)
    cpu.m8 = cpu.x8 = True
    cpu.db = 0x03                       # the drawer runs with DBR = $03
    w = cpu.bus.wram
    w[0x03EA:0x03EA + len(msg)] = msg
    w[0x03E8] = len(msg) & 0xFF
    w[0x03E9] = i
    w[0x036E] = row
    w[0x036F] = col
    w[0x09DF] = stage
    w[0x12] = (msg[i] if code is None and i < len(msg) else (code or 0)) & 0xFF
    cpu.a = w[0x12]
    cpu.push8(0xFF)                     # emulate the caller's JSR return address
    cpu.push8(0xFF)
    cpu.entry_s = cpu.s
    return cpu


def run_from(cpu, limit=6000):
    steps = 0
    while steps < limit:
        cpu.step()
        steps += 1
        if cpu.s > cpu.entry_s:
            return (cpu.pbr == 0x03 and cpu.pc in (0x0000, 0x10000)), steps
        if cpu.s < 0x0100:
            break
    return False, steps


def flush(cpu, limit=400000):
    cpu.pbr, cpu.pc = 0x00, 0x8385
    cpu.m8 = cpu.x8 = True
    cpu.db = 0x00
    cpu.push8(0x00)
    cpu.push8(0xFF)
    cpu.push8(0xFE)
    entry_s = cpu.s
    steps = 0
    while steps < limit:
        cpu.step()
        steps += 1
        if cpu.s > entry_s:
            cpu.dma_log = []                # the flusher DMAs; the drawer may not
            return cpu.pbr == 0x00 and cpu.pc == 0xFFFF, steps
    return False, steps


def run_to(cpu, pbr, pc, limit=40000):
    """Run until control reaches pbr:pc (used by the hooks that hand control
    back into the engine instead of returning)."""
    steps = 0
    while steps < limit:
        if cpu.pbr == pbr and cpu.pc == pc:
            return True, steps
        cpu.step()
        steps += 1
    return False, steps


def pool_half(ch, k):
    """Glyph bytes for cell k (0 = left, 1 = right) = two tiles = 32 bytes."""
    g = glyph64(ch)
    return g[k * 32:k * 32 + 32]


skip = set()            # entries whose rebuilt address is unknown (none)
nb = flushes = peak = 0
worst = ''
vram_total = 0
for r in recs:
    key = '%06X' % r['text_rom_off']
    if key in skip or key not in addr:
        continue
    if r['table_rom_off'] == cb.ITEM_TABLE:
        continue    # the item names are not drawn by this drawer: they
                    # go through $01:FC75, covered by test_itemdraw.py
    msg = message_at(addr[key])
    row, col, stage = 0, 0, 0
    cpu = None
    vram_want = {}
    tm_want = {}
    i = 0
    while i < len(msg):
        code = msg[i]
        if code >= 0xF0:
            if code == 0xF0:
                col = 0
            if code == 0xF2:                    # newline (never seen here)
                row = (row + 1) & 0x0F
                col = 0
            i += 1
            continue
        cn = is_cn(code)
        fx = is_fx(code)
        # ---- model the wrap the drawer itself does for a 2 cell glyph
        if (cn or fx) and col >= cb.WRAP_COL:
            row = (row + 1) & 0x0F
            col = 0
        cpu = setup(msg, i, row, col, stage, cpu=cpu)
        try:
            ok, steps = run_from(cpu)
        except NotImplementedError as e:
            print('  sim died on entry %s byte %d code $%02X: %s' % (key, i, code, e))
            raise
        if not ok:
            fail('entry %s byte %d: drawer did not return to bank $03 '
                 '(pc $%02X:%04X s $%04X)' % (key, i, cpu.pbr, cpu.pc, cpu.s))
            break
        if cpu.s != ((cpu.entry_s + 2) & 0xFFFF):
            fail('entry %s byte %d: stack unbalanced (s $%04X want $%04X)'
                 % (key, i, cpu.s, (cpu.entry_s + 2) & 0xFFFF))
            break
        if cpu.dma_log:
            fail('entry %s byte %d: the drawer must not DMA (%s)'
                 % (key, i, cpu.dma_log[0]))
            cpu.dma_log = []
        w = cpu.bus.wram
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
        staged = b''
        # the stale-row stub runs on the message's *second* row, at columns 1
        # to 4, and blanks text row $0391 - the row the previous message left on
        # screen (see build_stalerow for the measurement behind the gate)
        if cb.STALEROW_ON and 1 <= col <= 4 and (row - w[0x0391]) & 0x0F == 1:
            r91 = w[0x0391] & 0x0F
            staged += wipe_row(r91 if col < 3 else (r91 - 1) & 0x0F)
        if col == 0:
            staged = wipe_row(row)          # a row starts: it is blanked first
        if kind == 'cn':
            if cn:
                ch = rev[(code - cb.PREFIX0, msg[i + 1])]
                slot = cell[ch][1]
                want_e9 = (i + 1) & 0xFF
            else:                       # one byte code $DC-$DF
                ch = rev[(0, code - cb.FIXED0)]
                slot = code - cb.FIXED0
                want_e9 = i
            pa, pb = LEFT[slot], RIGHT[slot]
            vm_a, vm_b = 0x6000 + pa * 8, 0x6000 + pb * 8
            staged += (bytes([vm_a & 0xFF, vm_a >> 8, 0x80, 0x20]) +
                       pool_half(ch, 0) +
                       bytes([vm_b & 0xFF, vm_b >> 8, 0x80, 0x20]) +
                       pool_half(ch, 1))
            vram_want[vm_a] = pool_half(ch, 0)
            vram_want[vm_b] = pool_half(ch, 1)
            tiles = ((pa, pa + 1), (pb, pb + 1))
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
        stage += len(staged)
        want_col = col + (2 if (cn or fx) else 1)
        if w[0x036F] != want_col:
            fail('entry %s byte %d: col %d want %d' % (key, i, w[0x036F], want_col))
        col = want_col
        if stage > peak:
            peak, worst = stage, key
        nb += 1
        i += 2 if cn else 1
        if stage + 44 + cb.ROW_WIPE_CHECK > 0xF0 or i >= len(msg):
            ok, _ = flush(cpu)
            flushes += 1
            if not ok:
                fail('entry %s: the queue flusher did not return' % key)
                break
            for word, want in sorted(vram_want.items()):
                got = b''.join(bytes([cpu.vram[word + k] & 0xFF,
                                      cpu.vram[word + k] >> 8])
                               for k in range(16))
                if got != want:
                    fail('entry %s: VRAM glyph at $%04X differs after the flush'
                         % (key, word))
                vram_total += 1
            for word, (top, bot) in sorted(tm_want.items()):
                if cpu.vram[word] != top or cpu.vram[word + 32] != bot:
                    fail('entry %s: tile map $%04X = $%04X/$%04X want $%04X/$%04X'
                         % (key, word, cpu.vram[word], cpu.vram[word + 32],
                            top, bot))
            vram_want, tm_want = {}, {}
            stage = 0
            w[0x09DD] = 0
print('   %d byte draws simulated over %d entries (%d queue flushes, peak $%02X '
      'bytes in %s, %d glyph tiles checked in VRAM)'
      % (nb, checked, flushes, peak, worst, vram_total))

# ------------------------------------------------- C2. delegated original path
print('C2 original path equivalence')
n_diff = n_cmp = 0
for r in recs[:400]:
    key = '%06X' % r['text_rom_off']
    a = r['text_rom_off']
    if False:
        continue
    msg = bytes(rom[a:a + 24])
    for i, code in enumerate(msg):
        if code >= 0xF0 or is_cn(code) or is_fx(code):
            continue
        if code in LABEL_CODES:
            # the status script's own codes.  Their FA/FB are repointed at
            # the labels' 8x16 glyphs on purpose (build_labeldrawer), and
            # the drawer never sees them: no message carries them.  They
            # are covered by test_labeldraw.py instead.
            continue
        row, col = i % 3, (i * 5) % 24          # a few different geometries
        c1 = setup(msg, i, row, col, 0, base=cb.E3_DRAWER)
        c1.db = 0x03
        c1.bus.wram[0x12] = code
        # my copy delegates with PBR = $3E; the original runs with PBR = $03
        ok1, _ = run_from(c1)
        # the genuine original drawer: it only exists unpatched in ORIG_ROM
        c2 = sim65816.CPU(orig)
        c2.pbr, c2.pc = 0x03, 0xFA30
        c2.m8 = c2.x8 = True
        c2.db = 0x03
        c2.bus.wram[0x03EA:0x03EA + len(msg)] = msg
        c2.bus.wram[0x036E] = row
        c2.bus.wram[0x036F] = col
        c2.bus.wram[0x09DF] = 0
        c2.bus.wram[0x12] = code
        c2.a = code
        c2.push8(0xFF)
        c2.push8(0xFF)
        c2.entry_s = c2.s
        ok2, _ = run_from(c2)
        if not (ok1 and ok2):
            fail('C2 $%02X: drawer did not return (mine %s, original %s)'
                 % (code, ok1, ok2))
            continue
        # My copy stages wipes the original does not: the stale-row stub runs at
        # the drawer's entry (so its bytes come first) and blanks text row $0391
        # when the drawer is on the message's second row; and at a row start the
        # drawer blanks the row it is about to draw.
        want_parts = []
        if cb.STALEROW_ON and 1 <= col <= 4 and (row - c2.bus.wram[0x0391]) & 0x0F == 1:
            r91 = c2.bus.wram[0x0391] & 0x0F
            want_parts.append(wipe_row(r91 if col < 3 else (r91 - 1) & 0x0F))
        if col == 0:
            want_parts.append(wipe_row(row))
        want_wipe = b''.join(want_parts)
        off = len(want_wipe)
        if off:
            got_wipe = bytes(c1.bus.wram[cb.QUEUE:cb.QUEUE + off])
            if got_wipe != want_wipe:
                fail('C2 code $%02X row %d col %d: staged wipe %s want %s'
                     % (code, row, col, got_wipe.hex(' '), want_wipe.hex(' ')))
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
                 % (code, c1.bus.wram[0x09DF], c2.bus.wram[0x09DF], off))
        n_cmp += 1
print('   %d original-drawer comparisons' % n_cmp)

# --------------------------------------------------------------- D. colouring
print('D  colouring')
win = json.load(open(BASE + '/cn_windows.json', encoding='utf-8')) \
    if False else None
try:
    import colset
    recs2, fx = colset.data()
    per_char = colset.colour_with(recs2, fx)[0] if False else None
except Exception as exc:                       # pragma: no cover
    per_char = None
print('   (colouring is checked in the builder: widest window <= slots)')

# ------------------------------------------- E. the drawer blanks a text row
print('E  a row start blanks the row through the queue')
cn_case = None
for r in recs:
    k_ = '%06X' % r['text_rom_off']
    if k_ not in addr:
        continue
    msg_ = message_at(addr[k_])
    for j, code_ in enumerate(msg_):
        if is_cn(code_) and j + 1 < len(msg_) and \
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
# a code the engine really draws: not one of ours, and not one of the codes the
# command window borrowed (those now point at glyph halves, not at font tiles)
occ_code = next(c for c in range(0x21, 0xF0)
                if not is_cn(c) and not is_fx(c)
                and c not in getattr(cb, 'CMDWIN_CODES', ())
                and km.FA[c] < 0x40)


def launch(kind, row, col, stage):
    """run one drawer call and check the invariants every call must keep."""
    code = msg[i] if kind == 'cn' else occ_code
    # the drawer reads the glyph id from $03EA + $03E9 + 1, so the index matters
    cpu = setup(msg if kind == 'cn' else bytes([occ_code]),
                i if kind == 'cn' else 0, row, col, stage, code=code)
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
want = wipe_row(row) + glyph_entries(gslot) + \
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
    left = sum(1 for k in list(range(3, 0x1D)) + list(range(0x23, 0x3D))
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
    # the consumer increments $03e9 after every drawer call, so the retry
    # marker is "index + 1 == the index before the draw" (the drawer's
    # decrement wraps at 0, which the increment brings back to 0)
    idx0 = i if kind == 'cn' else 0
    if (w[0x03E9] + 1) & 0xFF != idx0:
        fail('E guard %s col %d: $03E9 = $%02X, want the retry marker for %d'
             % (kind, col_, w[0x03E9], idx0))
    if w[0x036F] != col_:
        fail('E guard %s col %d: the column moved to $%02X'
             % (kind, col_, w[0x036F]))
    if kind == 'cn' and w[0x09DF] != stage_:
        fail('E guard %s col %d: cursor moved to $%02X' % (kind, col_, w[0x09DF]))
print('   the guard defers a row start and a glyph that would leave the page')

# ------------------------------------------ F. one glyph, no hidden state
print('F  the drawer stages exactly what the pool holds')
cpu, staged = launch('cn', 2, 0, 0)
want = wipe_row(2) + glyph_entries(gslot) + \
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
# ------------------------------------------------- G. speaker name labels
print('G  speaker name labels')
names = __import__('json').load(open('name_hanzi.json', encoding='utf-8'))
ids = {}
for _nm in names.values():
    for _ch in _nm:
        ids.setdefault(_ch, len(ids))
PER_PAGE = 256 - cb.LABEL_ID0
lbl_ok = lbl_bad = 0
for i in range(cb.NAME_RECORDS):
    o = cb.NAME_RECORD_BASE + i * 16
    kana = ''.join(cb.km.CODE.get(b, '') for b in orig[o:o + 4]).strip()
    h = names.get(kana)
    if not h:
        continue
    # the engine walks the buffer: four record bytes, then the colon
    msg = bytes(rom[o:o + 4]) + bytes([0x09, 0xF2, 0xF3])
    # the pair set follows the row (row % LABEL_SETS): draw on three rows so
    # every set is exercised, and on a row that shares no set with the previous
    # one so the visible-history guarantee is covered too
    row = (i % 3) * 4 + (i % 4)
    cpu = None
    col = 0
    for k, ch in enumerate(h):
        page, idx = divmod(ids[ch], PER_PAGE)
        gid = cb.LABEL_ID0 + idx
        cpu = setup(msg, k * 2, row, col, 0, cpu=cpu)
        okk, _ = run_from(cpu)
        if not okk:
            fail('label %d %r: drawer did not return (pc $%02X:%04X)'
                 % (i, kana, cpu.pbr, cpu.pc))
            break
        if cpu.s != ((cpu.entry_s + 2) & 0xFFFF):
            fail('label %d %r: stack unbalanced (s $%04X)' % (i, kana, cpu.s))
            break
        okk, _ = flush(cpu)
        if not okk:
            fail('label %d %r: the flusher did not finish' % (i, kana))
            break
        # the engine clears both queue cursors once the flusher has run
        cpu.bus.wram[0x09DD] = 0
        cpu.bus.wram[0x09DF] = 0
        _set = row % cb.LABEL_SETS
        pa = LEFT[cb.SLOTS + _set * cb.LABEL_GLYPHS + k]
        pb = RIGHT[cb.SLOTS + _set * cb.LABEL_GLYPHS + k]
        g = cb.glyph64(ch)
        for base, want in ((0x6000 + pa * 8, g[0:32]), (0x6000 + pb * 8, g[32:64])):
            got = b''.join(bytes([cpu.vram[base + j] & 0xFF,
                                  cpu.vram[base + j] >> 8]) for j in range(16))
            if got != want:
                fail('label %d %r glyph %d: VRAM at $%04X differs'
                     % (i, kana, k, base))
                lbl_bad += 1
        # the two tile map cells of this glyph
        w0 = 0x7C00 + row * 0x40 + 3 + col
        want_cells = [(w0, pa | 0x2400), (w0 + 0x20, (pa + 1) | 0x2400),
                      (w0 + 1, pb | 0x2400), (w0 + 0x21, (pb + 1) | 0x2400)]
        for word, want in want_cells:
            if cpu.vram[word] != want:
                fail('label %d %r glyph %d: cell $%04X = $%04X want $%04X'
                     % (i, kana, k, word, cpu.vram[word], want))
                lbl_bad += 1
        lbl_ok += 1
        col += 2
print('   %d label glyphs drawn, %d mismatches' % (lbl_ok, lbl_bad))

# ---------------------------------- H. a deferred label glyph must retry
# The consumer at $03:eeea increments $03e9 unconditionally after the drawer
# returns, so a deferred draw must leave the index unchanged.  Index 0 is the
# speaker name's first glyph: the decrement wraps to $ff and the consumer's
# increment brings it back to 0, so the same glyph is tried again instead of
# being skipped (which left the previous speaker's tiles on screen).
print('H  a deferred draw keeps the index so the consumer retries')
names_h = __import__('json').load(open('name_hanzi.json', encoding='utf-8'))
ids_h = {}
for _nm in names_h.values():
    for _ch in _nm:
        ids_h.setdefault(_ch, len(ids_h))
o_h = cb.NAME_RECORD_BASE
msg_h = bytes(rom[o_h:o_h + 4]) + bytes([0x09, 0xF2, 0xF3])
for stage in (0x39, 0x60, 0xA9, 0xF0):
    cpu = setup(msg_h, 0, 0, 0, stage)
    okk, _ = run_from(cpu)
    w = cpu.bus.wram
    deferred = w[0x09DF] == stage
    idx = w[0x03E9]
    # the consumer always increments after the drawer returns
    w[0x03E9] = (idx + 1) & 0xFF
    after = w[0x03E9]
    if deferred and after != 0:
        fail('defer at stage $%02X left $03E9 = $%02X, want 0 after the '
             'consumer increment' % (stage, after))
    elif not deferred and after != 1:
        fail('no defer at stage $%02X but $03E9 = $%02X' % (stage, after))
    else:
        print('   stage $%02X: %s -> $03E9 $%02X -> $%02X'
              % (stage, 'deferred' if deferred else 'staged', idx, after))
    # and the retry must actually stage once there is room again
    if deferred:
        cpu.bus.wram[0x09DD] = 0
        cpu.bus.wram[0x09DF] = 0
        cpu = setup(msg_h, 0, 0, 0, 0, cpu=cpu)
        okk, _ = run_from(cpu)
        if cpu.bus.wram[0x09DF] < 80:
            fail('the retry after a defer staged only $%02X bytes'
                 % cpu.bus.wram[0x09DF])

# ------------------------------- I. label position with a shifted record
# The record does not always start at the buffer's first byte (a leading {F0}
# shifts it by one), and a macro can copy a name that is not the speaker's.
# The drawer must still put the name's two glyphs in its two cells, and must
# keep a foreign record off the label pairs entirely.
print('I  label position with a shifted record / a foreign record')
names_i = __import__('json').load(open('name_hanzi.json', encoding='utf-8'))
ids_i = {}
for _nm in names_i.values():
    for _ch in _nm:
        ids_i.setdefault(_ch, len(ids_i))
PER_PAGE_I = 256 - cb.LABEL_ID0
# a two glyph name: take the first record that has one
rec_i = None
for i in range(cb.NAME_RECORDS):
    o = cb.NAME_RECORD_BASE + i * 16
    kana = ''.join(cb.km.CODE.get(b, '') for b in orig[o:o + 4]).strip()
    h = names_i.get(kana)
    if h and len(h) == 2:
        rec_i = (i, kana, h, bytes(rom[o:o + 4]))
        break
if not rec_i:
    fail('I: no two glyph name record found')
else:
    i_, kana_, h_, rec_ = rec_i
    for shift in (0, 1):
        msg = bytes([0xF0]) * shift + rec_ + bytes([0x09, 0xF2, 0xF3])
        base = shift
        cpu = None
        for k in range(2):
            col = k * 2
            idx = base + k * 2
            cpu = setup(msg, idx, 0, col, 0, cpu=cpu)
            okk, _ = run_from(cpu)
            if not okk:
                fail('I shift %d glyph %d: the drawer did not return' % (shift, k))
                break
            _set = 0 % cb.LABEL_SETS
            pa = LEFT[cb.SLOTS + _set * cb.LABEL_GLYPHS + k]
            w0 = 0x7C00 + 3 + col
            if cpu.vram[0] is not None:
                pass
            got = (cpu.bus.wram, w0)
            # the staged cells must point at the pair for position k
            want_cell = pa | 0x2400
            w = cpu.bus.wram
            staged = bytes(w[0x0B00:0x0B00 + w[0x09DF]])
            found = False
            j = 0
            while j < len(staged) - 4:
                cnt = staged[j + 3]
                if cnt == 4:
                    addr = staged[j] | (staged[j + 1] << 8)
                    if addr == w0 and (staged[j + 4] | (staged[j + 5] << 8)) == want_cell:
                        found = True
                    if addr == w0 and (staged[j + 4] | (staged[j + 5] << 8)) != want_cell:
                        fail('I shift %d glyph %d: cell $%04X = $%04X want $%04X'
                             % (shift, k, w0, staged[j + 4] | (staged[j + 5] << 8), want_cell))
                if cnt == 0:
                    break
                j += 4 + cnt
            if not found:
                fail('I shift %d glyph %d: no cell staged for $%04X' % (shift, k, w0))
    # a foreign record: another name copied into the body must not use a label pair
    other = None
    for i in range(cb.NAME_RECORDS):
        o = cb.NAME_RECORD_BASE + i * 16
        kana = ''.join(cb.km.CODE.get(b, '') for b in orig[o:o + 4]).strip()
        h = names_i.get(kana)
        if h and h != h_ and bytes(rom[o:o + 4]) != rec_:
            other = bytes(rom[o:o + 4])
            break
    if other:
        msg = rec_ + bytes([0x09]) + other + bytes([0xF2, 0xF3])
        cpu = setup(msg, 5, 0, 8, 0, cpu=cpu)
        okk, _ = run_from(cpu)
        if not okk:
            fail('I foreign: the drawer did not return')
        else:
            w = cpu.bus.wram
            staged = bytes(w[0x0B00:0x0B00 + w[0x09DF]])
            lab = {LEFT[cb.SLOTS + j] | 0x2400 for j in range(cb.LABEL_GLYPHS * cb.LABEL_SETS)}
            j = 0
            bad = 0
            while j < len(staged) - 4:
                cnt = staged[j + 3]
                if cnt == 4 and (staged[j + 4] | (staged[j + 5] << 8)) in lab:
                    bad += 1
                if cnt == 0:
                    break
                j += 4 + cnt
            if bad:
                fail('I foreign: %d cell(s) went to a label pair' % bad)
            else:
                print('   foreign record kept off the label pairs')

print('ALL CHECKS PASSED' if not fails else '%d FAILURES' % len(fails))
