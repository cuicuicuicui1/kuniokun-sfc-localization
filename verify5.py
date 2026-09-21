"""End-to-end verification of the v5 Chinese patch for 初代熱血硬派くにおくん.

  A  patch sites, slot table, protected tiles, glyph pool
  B  every rebuilt entry: decode round-trip == translation
  C1 every entry's first message: simulate the patched drawer byte by byte and
     compare the glyph DMA, the staged $0B00 VRAM script and the VRAM content
  C2 drawer copy equivalence: on original Japanese messages the copy must
     produce exactly the same staged script and cursor state as the original
  D  colouring: glyphs that can share a screen never share a slot
  E  widget path: simulate the patched dispatcher over a whole string

Usage: python -u verify5.py
"""
import json
import sys

import kuniokun_map as km
import cnbuild5 as cb
import sim65816

BASE = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon'

rom = open(cb.OUT_ROM, 'rb').read()
orig = open(cb.ORIG_ROM, 'rb').read()
tr = json.load(open(BASE + '/cn_translation.json', encoding='utf-8'))
recs = json.load(open(BASE + '/kuniokun_text.json', encoding='utf-8'))
addr = json.load(open(BASE + '/cn_addr_map.json', encoding='utf-8'))
# reproduce the exact encoder state the build ended up with
par = json.load(open(BASE + '/cn_build_params.json', encoding='utf-8'))
cb.KEEP1.clear()
cb.KEEP1.update({k: v for k, v in par['keep1'].items()})
cb.SLOTS = par['slots']
cb.PAGES = par['pages']
cell = {k: tuple(v) for k, v in
        json.load(open(BASE + '/cn_glyph_cell.json', encoding='utf-8')).items()}
rev = {}
for _ch, (_p, _i) in cell.items():
    rev.setdefault((_p, _i), _ch)
# the build reflows every translation and then re-imposes the original control
# token sequence; the verifier must compare against that same text
_orig_text = {'%06X' % r['text_rom_off']: r['text'] for r in recs}
fixed = {k: cb.align_tokens(_orig_text[k], cb.reflow(v)) for k, v in tr.items()}

SLOTPAIR = rom[cb.B3_SLOTPAIR:cb.B3_SLOTPAIR + cb.SLOTS]
DRAWER_LEN = len(cb.build_drawer_copy())
fails = []


def fail(msg):
    fails.append(msg)
    if len(fails) <= 30:
        print('  FAIL ' + msg)


def glyph32(ch):
    return cb.glyph32(ch)


def is_cn(b):
    return cb.PREFIX0 <= b < cb.PREFIX0 + cb.PAGES


def message_at(a):
    """Bytes the loader would copy for the message starting at `a`."""
    j = a
    while rom[j] != 0xF2:
        j += 1
    return bytes(rom[a:j])


# ---------------------------------------------------------------- A. structure
print('A  patch sites / slot table / pool')
hooks = [(cb.HOOK_A, bytes([0x5C, 0x00, 0x80, 0x3E]), 'widget preload JML'),
         (cb.HOOK_KEEP_BANK, bytes([0xEA, 0xEA]), 'widget bank keep'),
         (cb.HOOK_B, bytes([0x5C, 0x80, 0x80, 0x3E]), 'widget dispatch JML'),
         (cb.HOOK_DRAWER, bytes([0x5C, 0x00, 0x82, 0x3E]), 'drawer JML'),
         (cb.HOOK_COPY1, bytes([0x20, 0x70, 0xE9]), 'sanitize JSR 1'),
         (cb.HOOK_COPY2, bytes([0x20, 0x70, 0xE9]), 'sanitize JSR 2')]
for off, want, name in hooks:
    got = rom[off:off + len(want)]
    if got != want:
        fail('%s @0x%06X = %s want %s' % (name, off, got.hex(' '), want.hex(' ')))
if rom[cb.B3_SANITIZE:cb.B3_SANITIZE + 14] != cb.build_sanitize():
    fail('sanitizer bytes differ')
if rom[cb.B3_SLOTPAIR:cb.B3_SLOTPAIR + cb.SLOTS] != cb.build_slotpair()[0]:
    fail('slot pair table differs')
for t in sorted(cb.PROTECT_TILES):
    off = 0x0F8000 + t * 16
    if rom[off:off + 16] != orig[off:off + 16]:
        fail('protected font tile 0x%02X was overwritten' % t)
pairs = [p for p in SLOTPAIR if p != 0xFF]
if len(set(pairs)) != len(pairs):
    fail('slot pair table has duplicates')
for p in pairs:
    for t in (p, p + 1):          # the table holds the *tile number*
        if t in cb.PROTECT_TILES:
            fail('slot pair %d uses protected tile 0x%02X' % (p, t))
for ch, (p, i) in cell.items():
    off = cb.POOL_ROM + p * 0x8000 + i * 32
    if rom[off:off + 32] != glyph32(ch):
        fail('pool glyph %s (page %d id %d) wrong' % (ch, p, i))
print('   %d hooks ok, %d slot pairs, %d glyphs in the pool'
      % (len(hooks), len(pairs), len(cell)))

# ------------------------------------------------------- B. text round-trip
print('B  text round-trip (%d entries)' % len(recs))


def expected(ch):
    out = []
    i = 0
    while i < len(ch):
        c = ch[i]
        if c == '{':
            j = ch.index('}', i)
            for b in bytes.fromhex(ch[i + 1:j]):
                out.append(('ctl' if b == 0xF2 else 'orig', b))
            i = j + 1
        elif c == ' ':
            out.append(('orig', 0x00))
            i += 1
        elif c in cb.KEEP1:
            out.append(('orig', cb.KEEP1[c]))
            i += 1
        else:
            out.append(('cn', c))
            i += 1
    # the loader stops at $F2, so compare only the text before it
    for k, item in enumerate(out):
        if item[0] == 'ctl' and item[1] == 0xF2:
            return out[:k]
    return out


def actual(a):
    out = []
    i = a
    while rom[i] != 0xF2:
        b = rom[i]
        if is_cn(b):
            out.append(('cn', rev[(b - cb.PREFIX0, rom[i + 1])]))
            i += 2
        else:
            out.append(('orig', b))
            i += 1
    return out


for r in recs:
    key = '%06X' % r['text_rom_off']
    if key not in addr:
        fail('entry %s has no rebuilt address' % key)
        continue
    want, got = expected(fixed[key]), actual(addr[key])
    if got != want:
        nm = min(len(got), len(want))
        k = next((i for i in range(nm) if got[i] != want[i]), nm)
        fail('entry %s mismatch at %d: got %s want %s'
             % (key, k, got[k:k + 4], want[k:k + 4]))
print('   %d entries decoded' % len(recs))

# --------------------------------------------------------- C1. drawer sim
print('C1 drawer simulation')


def setup(msg, i, row, col, stage, src=rom, base=cb.E3_DRAWER, code=None, cpu=None):
    if cpu is None:
        cpu = sim65816.CPU(src)
    cpu.pbr = base // 0x8000
    cpu.pc = 0x8000 + (base % 0x8000)
    cpu.m8 = True
    cpu.x8 = True
    cpu.db = 0x03                       # the drawer runs with DBR = $03
    w = cpu.bus.wram
    w[0x03EA:0x03EA + len(msg)] = msg
    w[0x03E8] = len(msg) & 0xFF
    w[0x03E9] = i
    w[0x036E] = row
    w[0x036F] = col
    w[0x09DF] = stage
    w[0x12] = (msg[i] if code is None and i < len(msg) else (code or 0)) & 0xFF
    cpu.a = w[0x12]        # the consumer does LDA $03EA,Y / STA $12 / JSR $FA30
    # emulate the JSR that got us here so a stack imbalance is detectable: the
    # patched code must leave the stack exactly as it found it.
    cpu.push8(0xFF)
    cpu.push8(0xFF)
    cpu.entry_s = cpu.s
    return cpu


DRAWER_BANK = 0x03            # every exit of the patched drawer returns here


def run_drawer(cpu, limit=5000):
    """Run until the drawer returns to its caller.  The hook is a JML, so the
    copy must jump (not RTS) back into bank $03 for every job; the emulated
    caller's return address is the marker that we are back, and the program bank
    must be the engine's again.  Returns (ok, steps)."""
    steps = 0
    while steps < limit:
        cpu.step()
        steps += 1
        if cpu.s > cpu.entry_s:              # the RTS popped the fake return addr
            return (cpu.pbr == DRAWER_BANK and cpu.pc in (0x0000, 0x10000)), steps
        if cpu.s < 0x0100:                   # stack ran away
            break
    return False, steps
def flush(cpu, limit=300000):
    """Run the engine's own queue flusher (ROM 0x000385) over the entries in
    $0B00, so the entries this patch appends are checked against their real
    consumer instead of against my reading of it: it turns each entry into a
    VRAM DMA and leaves the result in cpu.vram."""
    cpu.pbr = 0x00
    cpu.pc = 0x8385
    cpu.m8 = True
    cpu.x8 = True
    cpu.db = 0x00
    cpu.push8(0x00)                      # RTL pops the program bank and the PC
    cpu.push8(0xFF)
    cpu.push8(0xFE)
    entry_s = cpu.s
    steps = 0
    while steps < limit:
        cpu.step()
        steps += 1
        if cpu.s > entry_s:
            return cpu.pbr == 0x00 and cpu.pc == 0xFFFF, steps
    return False, steps


nb = 0
flushes = 0
peak = 0
worst = ''
for r in recs:
    key = '%06X' % r['text_rom_off']
    msg = message_at(addr[key])
    row, col, stage = 0, 0, 0
    cpu = None
    vram_want = {}          # VRAM word -> the 32 glyph bytes that must land there
    tm_want = {}            # VRAM word -> (top, bottom) tile map words
    i = 0
    while i < len(msg):
        code = msg[i]
        if code >= 0xF0:
            # the consumer routes $F0-$FF to the control handler at $01FC9E and
            # never hands them to the drawer, so nothing gets staged for them
            if code == 0xF0:
                col = 0
            i += 1
            continue
        cpu = setup(msg, i, row, col, stage, cpu=cpu)
        ok, steps = run_drawer(cpu)
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
        staged = b''
        tiles = None
        if is_cn(code):
            if col < cb.MAX_COL:
                ch = rev[(code - cb.PREFIX0, msg[i + 1])]
                pair = SLOTPAIR[cell[ch][1]]
                vmadd = 0x6000 + pair * 8
                staged = bytes([vmadd & 0xFF, vmadd >> 8, 0x80, 0x20]) + glyph32(ch)
                vram_want[vmadd] = glyph32(ch)
                tiles = (pair, pair + 1)
            if w[0x03E9] != ((i + 1) & 0xFF):
                fail('entry %s byte %d: the id byte was not consumed '
                     '($03E9 = $%02X)' % (key, i, w[0x03E9]))
        elif code < 0xF0:
            tiles = (km.FB[code], km.FA[code])
        if tiles is not None and col < cb.MAX_COL:
            celladdr = 0x7C00 + row * 0x40 + 3 + col
            staged += bytes([celladdr & 0xFF, celladdr >> 8, 0x81, 0x04,
                             tiles[0], 0x24, tiles[1], 0x24])
            tm_want[celladdr] = (tiles[0] | 0x2400, tiles[1] | 0x2400)
        got = bytes(w[0x0B00 + stage:0x0B00 + stage + len(staged)])
        if got != staged:
            fail('entry %s byte %d ($%02X): staged %s want %s'
                 % (key, i, code, got.hex(' '), staged.hex(' ')))
        stage += len(staged)
        if w[0x09DF] != stage:
            fail('entry %s byte %d: queue cursor $09DF = $%02X want $%02X'
                 % (key, i, w[0x09DF], stage))
        if w[0x036F] != (col + 1) & 0xFF:
            fail('entry %s byte %d: col %d want %d'
                 % (key, i, w[0x036F], (col + 1) & 0xFF))
        col += 1
        if stage > peak:
            peak, worst = stage, key
        nb += 1
        if code == 0xF0:
            col = 0
        i += 2 if is_cn(code) else 1
        # the engine flushes the queue every frame and clears both cursors right
        # after ($00:B908 in the NMI handler, $00:F1F2 / $02:88E6 in the main
        # loop), so flush whenever the next entry would not fit the 256 byte
        # buffer - exactly the budget the real thing has to live with
        if stage + 44 > 0xF0 or i >= len(msg):
            ok, steps = flush(cpu)
            flushes += 1
            if not ok:
                fail('entry %s: the queue flusher did not return (pc $%02X:%04X)'
                     % (key, cpu.pbr, cpu.pc))
                break
            for word, want in sorted(vram_want.items()):
                got = b''.join(bytes([cpu.vram[word + k] & 0xFF,
                                      cpu.vram[word + k] >> 8])
                               for k in range(16))
                if got != want:
                    fail('entry %s: VRAM glyph at $%04X differs after the flush'
                         % (key, word))
            for word, (top, bot) in sorted(tm_want.items()):
                if cpu.vram[word] != top or cpu.vram[word + 32] != bot:
                    fail('entry %s: tile map $%04X = $%04X/$%04X want $%04X/$%04X'
                         % (key, word, cpu.vram[word], cpu.vram[word + 32],
                            top, bot))
            vram_want, tm_want = {}, {}
            stage = 0
            w[0x09DD] = 0
            w[0x09DF] = 0
            cpu.dma_log = []             # the flusher DMA'd; the drawer must not
        if fails:
            break
    if fails:
        break
print('   %d byte draws simulated over %d entries (%d queue flushes, peak '
      '$%02X bytes, entry %s)' % (nb, len(recs), flushes, peak, worst))

# ------------------------------------------------- C2. drawer copy check
print('C2 drawer copy vs original drawer')
ORIG_DRAWER = 0x01FA30
n = 0
bad = 0
for r in recs:
    key = '%06X' % r['text_rom_off']
    for off in (r['text_rom_off'],):
        msg = orig[off:off + r['nbytes']]
        # original Japanese message, up to the first $F2
        k = 0
        while k < len(msg) and msg[k] != 0xF2:
            k += 1
        msg = msg[:k]
        if not msg:
            continue
        outs = []
        for base, src in ((ORIG_DRAWER, orig), (cb.E3_DRAWER, rom)):
            cpu = setup(msg, 0, 0, 0, 0, src=src, base=base)
            # the original drawer writes into $0B00 through absolute,X so run
            # it one byte per invocation, like the consumer does
            script = bytearray()
            col, stage = 0, 0
            i = 0
            while i < len(msg):
                c = msg[i]
                cpu = setup(msg, i, 0, col, stage, src=src, base=base)
                ok, steps = run_drawer(cpu)
                if not ok:
                    fail('%06X on %s byte %d: no return to bank $03 (pc $%02X:%04X)'
                         % (base, key, i, cpu.pbr, cpu.pc))
                    break
                if cpu.s != ((cpu.entry_s + 2) & 0xFFFF):
                    fail('stack unbalanced in %06X on %s (s $%04X)'
                         % (base, key, cpu.s, (cpu.entry_s + 2) & 0xFFFF))
                w = cpu.bus.wram
                if c < 0xF0:
                    # this copy's staged bytes are at $0B00+stage
                    nxt = w[0x09DF]
                    script += bytes(w[0x0B00 + stage:0x0B00 + (nxt if nxt > stage else stage + 8)])
                    stage = nxt
                    col = w[0x036F]
                i += 1
            outs.append(bytes(script))
        if outs[0] != outs[1]:
            bad += 1
            if bad <= 3:
                fail('drawer copy differs on %s:\n     orig %s\n     copy %s'
                     % (key, outs[0][:48].hex(' '), outs[1][:48].hex(' ')))
        n += 1
print('   %d messages compared (copies of the original drawer logic)' % n)

# ------------------------------------------------------------- D. colouring
print('D  colouring windows')


def ids_of(a):
    out = set()
    k = a
    while rom[k] != 0xF2:
        b = rom[k]
        if is_cn(b):
            out.add(cell[rev[(b - cb.PREFIX0, rom[k + 1])]][1])
            k += 2
        else:
            k += 1
    return out


conf = 0
for ti, (table_off, count) in enumerate(cb.TABLES):
    rs = sorted([r for r in recs if r['table_rom_off'] == table_off],
                key=lambda r: r['index'])
    win = cb.WIN_MAIN_MAX if ti == 0 else cb.WIN_LIST_MAX
    for i in range(len(rs)):
        u = set()
        for j in range(i, min(i + win, len(rs))):
            u |= ids_of(addr['%06X' % rs[j]['text_rom_off']])
        if len(u) > cb.SLOTS:
            conf += 1
if conf:
    fail('%d windows need more than %d slots' % (conf, cb.SLOTS))
else:
    print('   widest window fits %d slots for every window' % cb.SLOTS)

# ---------------------------------------------------------------- E. widgets
print('E  widget path')
props = sorted([r for r in recs if r['table_rom_off'] == 0x01DBC5],
               key=lambda r: r['index'])
tested = 0
for r in props:
    if tested >= 8:
        break
    a = addr['%06X' % r['text_rom_off']]
    msg = message_at(a)
    if not any(is_cn(b) for b in msg):
        continue
    cpu = sim65816.CPU(rom)
    cpu.pbr = cb.DISPATCH_ROM // 0x8000
    cpu.pc = 0x8000 + (cb.DISPATCH_ROM % 0x8000)
    cpu.m8 = True
    cpu.x8 = True
    cpu.db = 0x03
    w = cpu.bus.wram
    _b, _a = cb.snes_of_rom(a)
    w[0x22], w[0x23], w[0x24] = _a & 0xFF, (_a >> 8) & 0xFF, _b
    w[0x20], w[0x21] = 0xC6, 0x79
    steps = 0
    while steps < 20000:
        cpu.step()
        steps += 1
        if cpu.pbr == 0x01 and cpu.pc == 0xFCC6:      # shared RTS
            break
    if not (cpu.pbr == 0x01 and cpu.pc == 0xFCC6):
        fail('widget: dispatcher did not reach RTS (pc $%02X:%04X)' % (cpu.pbr, cpu.pc))
        continue
    col = 0
    i = 0
    ok = True
    while i < len(msg):
        c = msg[i]
        word = cpu.vram[0x79C6 + col]
        if is_cn(c):
            ch = rev[(c - cb.PREFIX0, msg[i + 1])]
            want = SLOTPAIR[cell[ch][1]] | 0x2400
            i += 2
        else:
            want = (km.FB[c] | 0x2400) & 0xFFFF   # FB is written to A first
            i += 1
        if word != want:
            fail('widget: cell %d word %04X want %04X'
                 % (col, word, want))
            ok = False
            break
        col += 1
    tested += 1
print('   %d widget strings simulated' % tested)

print()
if fails:
    print('%d FAILURES' % len(fails))
    sys.exit(1)
print('ALL CHECKS PASSED')