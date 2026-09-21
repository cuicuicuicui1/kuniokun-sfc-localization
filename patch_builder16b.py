# -*- coding: utf-8 -*-
"""Finish the 16x16 conversion of cnbuild5.py: constants, the tile attribute
bug in the new drawer, and the main() wiring.  Run once."""

edits = []


def sub(old, new, count=1):
    edits.append((old, new, count))


# ---- constants ---------------------------------------------------------------
sub("""E3_DRAWER = CODE_ROM + 0x200           # $3E:8200  drawer copy + Chinese branch
E3_WIPE = CODE_ROM + 0x400             # $3E:8400  staged box wipe
E3_ARM = CODE_ROM + 0x500              # $3E:8500  message-entry hook (arms the wipe)""",
    """E3_DRAWER = CODE_ROM + 0x200           # $3E:8200  drawer: Chinese branch
E3_WIPE = CODE_ROM + 0x600             # $3E:8600  staged box wipe
E3_ARM = CODE_ROM + 0x700              # $3E:8700  message-entry hook (arms the wipe)""")

sub("""POOL_STRIDE = 64                       # one Chinese glyph = 16x16 px = four tiles
GLYPH_TILES = 4                        # tiles per glyph: TL, BL, TR, BR""",
    """POOL_STRIDE = 64                       # one Chinese glyph = 16x16 px = four tiles
GLYPH_TILES = 4                        # tiles per glyph: TL, BL, TR, BR
# The item table is drawn by the item window's own renderer (ROM 0x00FC77), which
# writes one 8x8 tile per byte and walks one cell per byte; a two cell Chinese
# glyph cannot be shown there, so those 110 entries stay in Japanese instead of
# coming out as boxes.
NO_TRANSLATE = {0x01DBC5}""")

sub("""# --- wipe bookkeeping (WRAM $0D40-$0D4F never changed during a 2600 frame run) -
WIPE_TOP = 0x0D40                      # lowest box row the last message drew into
WIPE_BOT = 0x0D41                      # highest such row
WIPE_ROW = 0x0D42                      # next row to wipe, 0 = nothing pending""",
    """# --- text state bookkeeping (WRAM $0D40-$0D4F: unchanged in a 2600 frame probe)
WIPE_TOP = 0x0D40                      # lowest box row the last message drew into
WIPE_BOT = 0x0D41                      # highest such row
WIPE_CUR = 0x0D42                      # next row to wipe
WIPE_PEND = 0x0D43                     # 1 while a wipe is pending; blocks glyphs
DRW_SLOT = 0x0D44                      # scratch: slot -> quad tile (16 bit)
DRW_VMADD = 0x0D46                     # scratch: VRAM address (16 bit)
DRW_TILE = 0x0D48                      # scratch: quad tile (16 bit)""")

# ---- the drawer referenced scratch names it does not use ---------------------
sub('WIPE_SLOT', 'DRW_SLOT', -1)
sub('WIPE_VMADD', 'DRW_VMADD', -1)
sub('WIPE_TILE', 'DRW_TILE', -1)
# (WIPE_CUR / WIPE_PEND / WIPE_TOP / WIPE_BOT keep their names)

# ---- tile attribute bytes: $24 is a separate byte, not OR-ed into the tile ----
sub("""    a.hexs('AD %02X 0D 09 24' % DRW_TILE)  # lda tile / ora #$24 (upper half)
    a.hexs('9D 00 0B E8')                  # sta / inx
    a.hexs('AD %02X 0D 1A 09 24' % DRW_TILE)  # lda tile+1 / ora #$24 (lower)
    a.hexs('9D 00 0B E8')                  # sta / inx""",
    """    a.hexs('AD %02X 0D 9D 00 0B E8' % DRW_TILE)      # tile (upper half)
    a.hexs('A9 24 9D 00 0B E8')                      # $24 (attribute byte)
    a.hexs('AD %02X 0D 1A 9D 00 0B E8' % DRW_TILE)   # tile+1 (lower half)
    a.hexs('A9 24 9D 00 0B E8')                      # $24""")

sub("""    a.hexs('AD %02X 0D 1A 1A 09 24' % DRW_TILE)  # lda tile+2 / ora #$24
    a.hexs('9D 00 0B E8')                  # sta / inx
    a.hexs('AD %02X 0D 1A 1A 1A 09 24' % DRW_TILE)  # lda tile+3 / ora #$24
    a.hexs('9D 00 0B E8')                  # sta / inx""",
    """    a.hexs('AD %02X 0D 1A 1A 9D 00 0B E8' % DRW_TILE)   # tile+2 (upper half)
    a.hexs('A9 24 9D 00 0B E8')                      # $24
    a.hexs('AD %02X 0D 1A 1A 1A 9D 00 0B E8' % DRW_TILE)  # tile+3 (lower half)
    a.hexs('A9 24 9D 00 0B E8')                      # $24""")

# ---- main(): skip the item table ---------------------------------------------
sub("""    orig_text = {'%06X' % r['text_rom_off']: r['text'] for r in textrecs}
    fixed = {}
    stats = {'max_col': 0, 'max_row': 0, 'changed': 0, 'aligned': 0, 'wrapped': 0}
    for k, v in tr.items():
        w = reflow(v)""",
    """    orig_text = {'%06X' % r['text_rom_off']: r['text'] for r in textrecs}
    tbl_of = {'%06X' % r['text_rom_off']: r['table_rom_off'] for r in textrecs}
    fixed = {}
    stats = {'max_col': 0, 'max_row': 0, 'changed': 0, 'aligned': 0, 'wrapped': 0,
             'skipped': 0}
    for k, v in tr.items():
        if tbl_of.get(k) in NO_TRANSLATE:
            stats['skipped'] += 1
            continue
        w = reflow(v)""")

sub("""    print('reflow: %d strings changed; %d aligned to the original control codes; '
          '%d needed extra line breaks; widest line %d cells, tallest page %d lines, '
          '%d entries still too wide'
          % (stats['changed'], stats['aligned'], stats['wrapped'], stats['max_col'],
             stats['max_row'], len(over)))""",
    """    print('reflow: %d strings changed; %d aligned to the original control codes; '
          '%d needed extra line breaks; widest line %d cells, tallest page %d lines, '
          '%d entries still too wide; %d left in Japanese (item window)'
          % (stats['changed'], stats['aligned'], stats['wrapped'], stats['max_col'],
             stats['max_row'], len(over), stats['skipped']))""")

sub("""        assert len(recs) == count, (hex(table_off), len(recs), count)
        per_table[ti] = [glyphs_of(fixed['%06X' % r['text_rom_off']]) for r in recs]
    windows = []""",
    """        assert len(recs) == count, (hex(table_off), len(recs), count)
        if table_off in NO_TRANSLATE:
            per_table[ti] = []
            continue
        per_table[ti] = [glyphs_of(fixed['%06X' % r['text_rom_off']]) for r in recs]
    windows = []""")

# packing loop
sub("""        recs = sorted([r for r in textrecs if r['table_rom_off'] == table_off],
                      key=lambda r: r['index'])
        used = 0
        for r in recs:""",
    """        recs = sorted([r for r in textrecs if r['table_rom_off'] == table_off],
                      key=lambda r: r['index'])
        if table_off in NO_TRANSLATE:
            per_table[table_off] = (0, count)
            continue
        used = 0
        for r in recs:""")

# region write + pointer rebuild
sub("""    for (start, end), (table_off, count) in zip(REGIONS, TABLES):
        body = bytes(chunks[start])
        rom[start:end] = body + b'\\x00' * (end - start - len(body))
    for table_off, count in TABLES:
        recs = sorted([r for r in textrecs if r['table_rom_off'] == table_off],
                      key=lambda r: r['index'])""",
    """    for (start, end), (table_off, count) in zip(REGIONS, TABLES):
        if table_off in NO_TRANSLATE:
            continue                    # keep the original Japanese items
        body = bytes(chunks[start])
        rom[start:end] = body + b'\\x00' * (end - start - len(body))
    for table_off, count in TABLES:
        if table_off in NO_TRANSLATE:
            continue
        recs = sorted([r for r in textrecs if r['table_rom_off'] == table_off],
                      key=lambda r: r['index'])""")

# ---- pool: 64 bytes per glyph ------------------------------------------------
sub("""        off = p * 0x8000 + i * 32
        pool[off:off + 32] = glyph32(ch)""",
    """        off = p * 0x8000 + i * POOL_STRIDE
        pool[off:off + POOL_STRIDE] = glyph64(ch)""")

# ---- slot table + code blobs -------------------------------------------------
sub("""    slotpair, npairs = build_slotpair()
    r5_end = REGIONS[4][0] + len(chunks[REGIONS[4][0]])
    assert r5_end <= B3_SLOTPAIR, (hex(r5_end), hex(B3_SLOTPAIR))
    rom[B3_SLOTPAIR:B3_SLOTPAIR + len(slotpair)] = slotpair
    print('slot pairs: %d free tile pairs available, %d slots used' % (npairs, SLOTS))

    drawer = build_drawer_copy()
    rom[E3_DRAWER:E3_DRAWER + len(drawer)] = drawer
    san = build_sanitize()
    rom[B3_SANITIZE:B3_SANITIZE + len(san)] = san
    assert B3_SLOTPAIR + len(slotpair) < B3_SLOTPAIR_LIMIT, (len(slotpair),)
    assert E3_DRAWER + len(drawer) < PRELOAD_ROM + 0x8000, (len(drawer),)
    assert B3_SANITIZE + len(san) < B3_SANITIZE_LIMIT, (len(san),)
    assert 0xF2 not in san, 'sanitizer must not contain an F2 byte'""",
    """    slottiles, nquads = build_slottiles()
    r5_end = REGIONS[4][0] + len(chunks[REGIONS[4][0]])
    assert r5_end <= B3_SLOTPAIR, (hex(r5_end), hex(B3_SLOTPAIR))
    rom[B3_SLOTPAIR:B3_SLOTPAIR + len(slottiles)] = slottiles
    print('slots: %d free tile quads available, %d slots used, one quad per glyph'
          % (nquads, SLOTS))

    drawer = build_drawer_copy()
    rom[E3_DRAWER:E3_DRAWER + len(drawer)] = drawer
    wipe = build_wipe()
    rom[E3_WIPE:E3_WIPE + len(wipe)] = wipe
    arm = build_arm()
    rom[E3_ARM:E3_ARM + len(arm)] = arm
    san = build_sanitize()
    rom[B3_SANITIZE:B3_SANITIZE + len(san)] = san
    assert B3_SLOTPAIR + len(slottiles) < B3_SLOTPAIR_LIMIT, (len(slottiles),)
    assert E3_DRAWER + len(drawer) < E3_WIPE, (len(drawer),)
    assert E3_WIPE + len(wipe) < E3_ARM, (len(wipe),)
    assert E3_ARM + len(arm) < CODE_ROM + 0x8000, (len(arm),)
    assert B3_SANITIZE + len(san) < B3_SANITIZE_LIMIT, (len(san),)
    assert 0xF2 not in san, 'sanitizer must not contain an F2 byte'""")

sub("""    print('drawer copy %d B @ROM 0x%06X ($%02X:%04X); sanitize %d B ($%02X:%04X)'
          % (len(drawer), E3_DRAWER, db, da, len(san), sb, sa_))""",
    """    print('drawer %d B @ROM 0x%06X ($%02X:%04X); wipe %d B ($%02X:%04X); '
          'arm %d B ($%02X:%04X); sanitize %d B ($%02X:%04X)'
          % (len(drawer), E3_DRAWER, db, da, len(wipe), *snes_of_rom(E3_WIPE),
             len(arm), *snes_of_rom(E3_ARM), len(san), sb, sa_))""")

sub("""    pre, dis = build_preload(), build_dispatch()
    rom[PRELOAD_ROM:PRELOAD_ROM + len(pre)] = pre
    rom[DISPATCH_ROM:DISPATCH_ROM + len(dis)] = dis
    pbb, pba = snes_of_rom(PRELOAD_ROM)
    rom[HOOK_A:HOOK_A + 4] = bytes([0x5C, pba & 0xFF, pba >> 8, pbb])
    rom[HOOK_KEEP_BANK:HOOK_KEEP_BANK + 2] = bytes([0xEA, 0xEA])
    abb, aba = snes_of_rom(DISPATCH_ROM)
    rom[HOOK_B:HOOK_B + 4] = bytes([0x5C, aba & 0xFF, aba >> 8, abb])
    print('widget path: preload %d B @$3E:%04X, dispatch %d B @$3E:%04X'
          % (len(pre), pba, len(dis), aba))""",
    """    wb, wa = snes_of_rom(E3_WIPE)
    assert rom[HOOK_DRIVER:HOOK_DRIVER + 4] == bytes([0x08, 0x8B, 0xE2, 0x30]), \\
        rom[HOOK_DRIVER:HOOK_DRIVER + 4].hex(' ')
    rom[HOOK_DRIVER:HOOK_DRIVER + 4] = bytes([0x5C, wa & 0xFF, wa >> 8, wb])
    ab, aa = snes_of_rom(E3_ARM)
    assert rom[HOOK_LOAD:HOOK_LOAD + 4] == bytes([0xA9, 0x40, 0x0C, 0x73]), \\
        rom[HOOK_LOAD:HOOK_LOAD + 4].hex(' ')
    rom[HOOK_LOAD:HOOK_LOAD + 4] = bytes([0x5C, aa & 0xFF, aa >> 8, ab])
    print('box wipe: stager $%02X:%04X hooked at $03:EE70, message hook at '
          '$%02X:%04X on $03:EB9E' % (wb, wa, ab, aa))""")

sub("""               'glyphs': len(enc.order),""",
    """               'glyphs': len(enc.order),
               'stride': POOL_STRIDE,
               'wrap_col': WRAP_COL,
               'no_translate': sorted(NO_TRANSLATE),""")

src = open('cnbuild5.py', encoding='utf-8').read()
for old, new, count in edits:
    n = src.count(old)
    if count >= 0:
        assert n == count, 'n=%d want %d: %r' % (n, count, old[:60])
    assert n > 0, old[:60]
    src = src.replace(old, new)
open('cnbuild5.py', 'w', encoding='utf-8').write(src)
print('applied %d edits' % len(edits))