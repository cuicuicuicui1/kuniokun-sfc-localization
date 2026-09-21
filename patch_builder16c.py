# -*- coding: utf-8 -*-
"""Switch the 16x16 build from one 4-tile quad per glyph to two independent tile
pairs (43 -> 53 slots), cap KEEP1 by frequency so the pairs exist, and rewrite
the drawer for the pair layout.  Run once: python patch_builder16c.py"""

NEW_DRAWER = r'''def build_drawer_copy():
    """Draw one 16x16 Chinese glyph as two tile pairs in two screen cells.

    Entered through a JML planted at ROM 0x01FA30, so PBR is $3E inside this code
    and an RTS would return into the wrong bank: every exit is an explicit JML
    into bank $03.  The character code is read from RAM $12 exactly like the
    original drawer does, because the row eraser ($FA0B, sub6) calls the drawer
    with a leftover A that has nothing to do with the character.

    A glyph occupies four tiles that need not be adjacent: the slot table gives
    two free tile pairs, the left screen cell shows tiles 2a/2a+1 and the right
    one 2b/2b+1.  The bitmap cannot be written to VRAM directly (the PPU drops a
    CPU write to $2118 outside VBlank), so it is appended to the engine's own
    upload queue in WRAM $0B00, whose flusher ($00:8385) turns entries

        [+0/+1] VRAM word address, [+2] $2115, [+3] byte count, [+4...] data

    into channel 0 DMAs.  One glyph costs two 36 byte tile entries plus two 8
    byte tile map cells.
    """
    a = Asm(E3_DRAWER)
    # ---- dispatch on the code in $12 -----------------------------------------
    a.hexs('A5 12')                        # lda $12
    a.hexs('C9 %02X' % PREFIX0)            # cmp #$c5
    a.rel(0x90, 'orig')                    # bcc orig
    a.hexs('C9 %02X' % (PREFIX0 + PAGES))  # cmp #$c5+pages
    a.rel(0x90, 'cn')                      # bcc cn
    a.label('orig')
    a.hexs('AD 6F 03')                     # lda $036f
    a.hexs('C9 1A')                        # cmp #$1a (eaten by the 4 byte hook)
    a.long_to(0x01FA35)                    # jml $03:fa35 (the original drawer)

    # ---- Chinese branch ------------------------------------------------------
    a.label('cn')
    a.hexs('AD %02X 0D' % WIPE_PEND)       # lda $0d43 (a box wipe is running)
    a.rel(0xD0, 'defer')                   # bne defer
    a.hexs('AD 6F 03')                     # lda $036f
    a.hexs('C9 %02X' % WRAP_COL)           # cmp #WRAP_COL
    a.rel(0x90, 'room')                    # bcc room (two cells still fit)
    # no room for two cells: wrap like the engine's own $F2 handler does
    a.hexs('EE 6E 03')                     # inc $036e
    a.hexs('AD 6E 03 C9 10')               # lda $036e / cmp #$10
    a.rel(0x90, 'w1')                      # bcc w1
    a.hexs('9C 6E 03')                     # stz $036e
    a.label('w1')
    a.hexs('9C 6F 03')                     # stz $036f
    a.hexs('EE 6D 03 AD 6D 03 C9 03')      # inc $036d / lda $036d / cmp #$03
    a.rel(0x90, 'room')                    # bcc room
    a.hexs('A9 03 8D 6D 03')               # lda #$03 / sta $036d
    a.hexs('AD 73 03 09 20 8D 73 03')      # lda $0373 / ora #$20 / sta $0373
    a.hexs('9C 71 03')                     # stz $0371 (box scroll request)
    a.label('room')
    a.hexs('A9 %02X' % GLYPH_COST)         # lda #GLYPH_COST
    a.hexs('22 B6 9A 00')                  # jsl $009ab6 (room in the queue page?)
    a.rel(0xB0, 'defer')                   # bcs defer

    # ---- slot, glyph id, tiles -----------------------------------------------
    a.hexs('8B')                           # phb (DBR is $03 here)
    a.hexs('A5 12 38 E9 %02X 18 69 %02X 48'
           % (PREFIX0, POOL_BANK0))        # glyph bank = code - $c5 + $21 -> stack
    a.hexs('AD E9 03 1A A8')               # lda $03e9 / inc a / tay
    a.hexs('B9 EA 03')                     # lda $03ea,y (the glyph id = slot)
    a.hexs('C9 %02X' % SLOTS)              # cmp #SLOTS
    a.rel(0xB0, 'cnbad')                   # bcs cnbad
    a.hexs('8D %02X 0D' % DRW_ID)          # sta scratch (id)
    a.hexs('9C %02X 0D' % (DRW_ID + 1))    # stz scratch+1 (zero extend)
    a.hexs('AA')                           # tax (X = slot)
    a.hexs('BD 00 E9')                     # lda $e900,x (left tile pair)
    a.hexs('8D %02X 0D' % DRW_PA)
    a.hexs('9C %02X 0D' % (DRW_PA + 1))
    a.hexs('BD 01 E9')                     # lda $e901,x (right tile pair)
    a.hexs('8D %02X 0D' % DRW_PB)
    a.hexs('9C %02X 0D' % (DRW_PB + 1))
    a.hexs('AD %02X 0D 0A 8D %02X 0D 1A 8D %02X 0D'
           % (DRW_PA, DRW_T1, DRW_T2))     # tiles 2a and 2a+1
    a.hexs('AD %02X 0D 0A 8D %02X 0D 1A 8D %02X 0D'
           % (DRW_PB, DRW_T3, DRW_T4))     # tiles 2b and 2b+1
    a.hexs('AE DF 09')                     # ldx $09df (queue append cursor)
    a.hexs('AB')                           # plb (DBR = the glyph bank)

    # ---- VRAM addresses: tile 2p lives at word $6000 + p*16 ------------------
    a.hexs('C2 30')                        # rep #$30
    a.hexs('AD %02X 0D 29 FF 00' % DRW_PA)
    a.hexs('0A 0A 0A 0A')                  # asl x4 (pair * 16 words)
    a.hexs('09 00 60 8D %02X 0D' % DRW_VMADD)   # ora #$6000 / sta scratch
    a.hexs('AD %02X 0D 29 FF 00' % DRW_PB)
    a.hexs('0A 0A 0A 0A')
    a.hexs('09 00 60 8D %02X 0D' % DRW_ADDR2)
    a.hexs('AD %02X 0D 29 FF 00' % DRW_ID)
    for _ in range(6):                     # Y = id * 64
        a.hexs('0A')
    a.hexs('A8')                           # tay

    # ---- queue: left half, right half ---------------------------------------
    for addr in (DRW_VMADD, DRW_ADDR2):
        a.hexs('AD %02X 0D 9D 00 0B E8 E8' % addr)   # VRAM address (2 bytes)
        a.hexs('E2 20 A9 80 9D 00 0B E8')            # sep #$20 / VMAIN $80
        a.hexs('A9 20 9D 00 0B E8')                  # count = 32 bytes
        a.hexs('C2 20')                              # rep #$20
        for _ in range(16):                          # 16 words = two tiles
            a.hexs('B9 00 80 9D 00 0B E8 E8 C8 C8')
    a.hexs('E2 30')                        # sep #$30
    a.hexs('A9 03 48 AB')                  # lda #$03 / pha / plb (DBR back)
    a.hexs('8E DF 09')                     # stx $09df (cursor += 72)

    # ---- two tile map cells (the original drawer's tail, twice) -------------
    a.hexs('AE DF 09')                     # ldx $09df
    a.hexs('AC 6E 03')                     # ldy $036e (row)
    a.hexs('B9 8E FA 18 6D 6F 03 9D 00 0B E8')   # cell address low
    a.hexs('B9 7E FA 69 00 9D 00 0B E8')         # cell address high (carry)
    a.hexs('A9 81 9D 00 0B E8')            # VMAIN $81: the two halves twice
    a.hexs('A9 04 9D 00 0B E8')            # count = 4 bytes
    for t in (DRW_T1, DRW_T2):
        a.hexs('AD %02X 0D 9D 00 0B E8' % t)         # tile
        a.hexs('A9 24 9D 00 0B E8')                  # attribute byte
    a.hexs('AC 6E 03')                     # ldy $036e
    a.hexs('B9 8E FA 18 6D 6F 03 1A 9D 00 0B E8')  # next column
    a.hexs('B9 7E FA 69 00 9D 00 0B E8')
    a.hexs('A9 81 9D 00 0B E8')
    a.hexs('A9 04 9D 00 0B E8')
    for t in (DRW_T3, DRW_T4):
        a.hexs('AD %02X 0D 9D 00 0B E8' % t)
        a.hexs('A9 24 9D 00 0B E8')
    a.hexs('8E DF 09')                     # stx $09df (cursor += 16)

    # ---- bookkeeping --------------------------------------------------------
    a.hexs('EE E9 03')                     # inc $03e9 (consume the id byte)
    a.hexs('EE 6F 03')                     # inc $036f ($FA7A adds the second)
    a.hexs('AD 6E 03')                     # lda $036e
    a.hexs('CD %02X 0D' % WIPE_TOP)        # cmp $0d40
    a.rel(0xB0, 'nt')                      # bcs nt
    a.hexs('8D %02X 0D' % WIPE_TOP)        # sta $0d40
    a.label('nt')
    a.hexs('AD 6E 03')
    a.hexs('CD %02X 0D' % WIPE_BOT)        # cmp $0d41
    a.rel(0x90, 'nb')                      # bcc nb
    a.hexs('8D %02X 0D' % WIPE_BOT)        # sta $0d41
    a.label('nb')
    a.hexs('68')                           # pla (the saved DBR)
    a.long_to(0x01FA7A)                    # jml $03:fa7a (inc $036f / rts)

    # ---- not yet drawable: give the frame back ------------------------------
    a.label('defer')
    a.hexs('AD E9 03')                     # lda $03e9
    a.rel(0xF0, 'defer2')                  # beq defer2 (index 0, nothing to undo)
    a.hexs('3A 8D E9 03')                  # dec a / sta $03e9 (cancel the consumer)
    a.label('defer2')
    a.long_to(0x01FA7D)                    # jml $03:fa7d (plain rts)

    # ---- id out of range: eat the byte, leave the cells blank ---------------
    a.label('cnbad')
    a.hexs('68 68')                        # pla pla (glyph bank + saved DBR)
    a.hexs('EE E9 03')                     # inc $03e9
    a.long_to(0x01FA7A)                    # jml $03:fa7a
    return a.done()


def build_wipe():
    """Stage one box row of blanks per queue flush while a wipe is pending.

    Entered through the 4 byte JML at $03:EE70, the per frame entry of the text
    state machine; the eaten prologue is replayed and control continues at
    $03:EE74 so that the machine's own epilogue still balances the stack.

    A row is two 26 word runs -- the upper halves of the 26 text cells and their
    lower halves 32 words further on -- each staged as one 56 byte queue entry.
    """
    a = Asm(E3_WIPE)
    a.hexs('08 8B E2 30')                  # php / phb / sep #$30 (prologue, 4 B)
    a.hexs('A9 03 48 AB')                  # lda #$03 / pha / plb (DBR = $03)
    a.hexs('AD %02X 0D' % WIPE_PEND)       # lda $0d43
    a.rel(0xF0, 'out')                     # beq out
    a.hexs('AD DD 09 CD DF 09')            # lda $09dd / cmp $09df
    a.rel(0xD0, 'out')                     # bne out (wait for the flusher)
    a.hexs('A9 %02X 22 B6 9A 00' % ROW_WIPE)  # lda #ROW_WIPE / jsl $009ab6
    a.rel(0xB0, 'out')                     # bcs out (queue page full)
    a.hexs('AD %02X 0D' % WIPE_CUR)        # lda $0d42
    a.hexs('C9 10')                        # cmp #$10 (not a box row?)
    a.rel(0xB0, 'finish')                  # bcs finish
    a.hexs('C2 30 29 FF 00')               # rep #$30 / and #$00ff
    for _ in range(6):                     # row * $40
        a.hexs('0A')
    a.hexs('18 69 03 7C')                  # clc / adc #$7c03
    a.hexs('8F %02X 0D 00' % WIPE_ADDR)    # sta long (this runs in bank $3E)
    a.hexs('AE DF 09')                     # ldx $09df
    for k in (0, 0x20):                    # upper halves, then lower halves
        if k:
            a.hexs('AF %02X 0D 00 18 69 20' % WIPE_ADDR)   # address + 32 words
        else:
            a.hexs('AF %02X 0D 00' % WIPE_ADDR)
        a.hexs('9D 00 0B E8 E8')           # store the address (2 bytes)
        a.hexs('E2 20 A9 80 9D 00 0B E8')  # sep #$20 / VMAIN $80
        a.hexs('A9 34 9D 00 0B E8')        # count = 52 bytes
        a.hexs('C2 20 A9 00 2C')           # rep #$20 / blank cell $2c00
        for _ in range(26):                # 26 cells per run
            a.hexs('9D 00 0B E8 E8')
    a.hexs('E2 30')                        # sep #$30
    a.hexs('8E DF 09')                     # stx $09df
    a.hexs('AD %02X 0D' % WIPE_CUR)        # advance the wipe
    a.hexs('CD %02X 0D' % WIPE_TOP)        # cmp $0d40 (reached the lowest row?)
    a.rel(0xF0, 'finish')                  # beq finish
    a.hexs('3A 8D %02X 0D' % WIPE_CUR)     # dec a / sta $0d42
    a.hexs('80 0A')                        # bra out
    a.label('finish')
    a.hexs('A9 10 8D %02X 0D' % WIPE_CUR)  # lda #$10 / sta $0d42
    a.hexs('9C %02X 0D' % WIPE_PEND)       # stz $0d43
    a.hexs('A9 10 8D %02X 0D' % WIPE_TOP)  # lda #$10 / sta $0d40
    a.hexs('9C %02X 0D' % WIPE_BOT)        # stz $0d41
    a.label('out')
    a.long_to(0x01EE74)                    # jml $03:ee74 (phk / plb / ...)
    return a.done()


'''

NEW_KEEP1 = r'''def derive_keep1(texts, need_pairs=None):
    """Let the characters that pay for themselves keep their original code.

    A kept character costs one byte instead of two and reuses the original font,
    but it also protects the two tiles its glyph lives in, and the Chinese glyph
    slots are built from those free tiles.  So characters are kept by descending
    frequency, and only while enough tile pairs stay free for the slot count.
    """
    if need_pairs is None:
        need_pairs = 2 * SLOTS
    by_char = {}
    for code, ch in km.CODE.items():
        if code >= 0xE0 or len(ch) != 1 or ch == ' ':
            continue
        by_char.setdefault(ch, code)
    freq = {}
    for t in texts:
        for ch in pieces_str(t):
            if ch in by_char:
                freq[ch] = freq.get(ch, 0) + 1

    def free_pair_count(chars):
        res = set(PROTECT_TILES)
        for c in chars:
            res.add(km.FA[c])
            res.add(km.FB[c])
        return sum(1 for p in range(128) if 2 * p not in res and 2 * p + 1 not in res)

    keep = dict(KEEP1_EXPLICIT)
    added = {}
    for ch in sorted(freq, key=lambda c: (-freq[c], c)):
        if ch in keep:
            continue
        if free_pair_count(list(keep) + list(added) + [ch]) < need_pairs:
            continue
        added[ch] = by_char[ch]
    keep.update(added)
    KEEP1.clear()
    KEEP1.update(keep)
    return added


'''

subs = []


def sub(old, new, count=1):
    subs.append((old, new, count))


sub("""GLYPH_ENTRY = 4 + POOL_STRIDE          # queue bytes per glyph: header + bitmap
CELL_ENTRY = 8                         # queue bytes per tile map cell
GLYPH_COST = GLYPH_ENTRY + 2 * CELL_ENTRY""",
    """GLYPH_ENTRY = 2 * (4 + 32)             # queue bytes per glyph: two tile pairs
CELL_ENTRY = 8                         # queue bytes per tile map cell
GLYPH_COST = GLYPH_ENTRY + 2 * CELL_ENTRY""")

sub("""DRW_SLOT = 0x0D44                      # scratch: slot -> quad tile (16 bit)
DRW_VMADD = 0x0D46                     # scratch: VRAM address (16 bit)
DRW_TILE = 0x0D48                      # scratch: quad tile (16 bit)""",
    """DRW_PA = 0x0D44                        # scratch: left tile pair (16 bit)
DRW_PB = 0x0D46                        # scratch: right tile pair (16 bit)
DRW_VMADD = 0x0D4A                     # scratch: VRAM address of the left pair
DRW_ADDR2 = 0x0D4C                     # scratch: VRAM address of the right pair
DRW_ID = 0x0D4E                        # scratch: glyph id (16 bit)
DRW_T1 = 0x0D50                        # scratch: left cell tiles (2 bytes)
DRW_T3 = 0x0D52                        # scratch: right cell tiles (2 bytes)
WIPE_ADDR = 0x0D54                     # scratch: wipe stager VRAM address""")

sub("""SLOTS = 114""", """SLOTS = 53                             # two independent tile pairs per glyph""")
sub("""WIN_LIST_MAX = 12                      # list tables: entry i .. i+win-1""",
    """WIN_LIST_MAX = 10                      # list tables: entry i .. i+win-1""")

# ---- slot table: two tile pairs per slot -------------------------------------
sub("""def build_slottiles():
    \"\"\"Slot table: one byte per slot = the base tile of its free quad.

    A quad is four consecutive 4-aligned tiles, which is what lets the drawer
    upload a whole 16x16 glyph with a single queue entry (64 data bytes).
    \"\"\"
    quads = free_quads()
    if len(quads) < SLOTS:
        raise SystemExit('only %d free tile quads, need %d' % (len(quads), SLOTS))
    return bytes(quads[s] for s in range(SLOTS)), len(quads)""",
    """def build_slotpairs():
    \"\"\"Slot table: two bytes per slot = two free tile pairs.

    A glyph is 16x16 = four 8x8 tiles, but they do not have to be adjacent: the
    two tiles of the left screen cell come from one free tile pair and the two of
    the right cell from another.  That needs 86 -> 53 slots instead of the 39 a
    single four-aligned quad would allow, and 53 is what the slot colouring needs
    to keep consecutive list entries apart (43 would just barely do for single
    messages, 39 does not).
    \"\"\"
    pairs = free_pairs()
    if len(pairs) < 2 * SLOTS:
        raise SystemExit('only %d free tile pairs, need %d for %d slots'
                         % (len(pairs), 2 * SLOTS, SLOTS))
    out = bytearray()
    for s in range(SLOTS):
        out += bytes([pairs[2 * s], pairs[2 * s + 1]])
    return bytes(out), len(pairs)""")

# ---- main(): slot count from pairs, slot table name --------------------------
sub("    SLOTS = min(SLOTS, len(free_quads()))",
    "    SLOTS = min(SLOTS, len(free_pairs()) // 2)")

sub("""    slottiles, nquads = build_slottiles()
    r5_end = REGIONS[4][0] + len(chunks[REGIONS[4][0]])
    assert r5_end <= B3_SLOTPAIR, (hex(r5_end), hex(B3_SLOTPAIR))
    rom[B3_SLOTPAIR:B3_SLOTPAIR + len(slottiles)] = slottiles
    print('slots: %d free tile quads available, %d slots used, one quad per glyph'
          % (nquads, SLOTS))""",
    """    slotpairs, npairs = build_slotpairs()
    r5_end = REGIONS[4][0] + len(chunks[REGIONS[4][0]])
    assert r5_end <= B3_SLOTPAIR, (hex(r5_end), hex(B3_SLOTPAIR))
    rom[B3_SLOTPAIR:B3_SLOTPAIR + len(slotpairs)] = slotpairs
    print('slots: %d free tile pairs, %d pair-pair slots used (%d bytes of table)'
          % (npairs, SLOTS, len(slotpairs)))""")

sub("    assert B3_SLOTPAIR + len(slottiles) < B3_SLOTPAIR_LIMIT, (len(slottiles),)",
    "    assert B3_SLOTPAIR + len(slotpairs) < B3_SLOTPAIR_LIMIT, (len(slotpairs),)")

# ---- keep1 cap ---------------------------------------------------------------
src = open('cnbuild5.py', encoding='utf-8').read()
i = src.index('def derive_keep1(texts):')
j = src.index('DECOR_TILES = (0x20, 0x72, 0x85, 0x86, 0x93)')
src = src[:i] + NEW_KEEP1 + src[j:]

# ---- drawer + wipe ----------------------------------------------------------
i = src.index('def build_drawer_copy():')
j = src.index('def build_arm():')
src = src[:i] + NEW_DRAWER + src[j:]

for old, new, count in subs:
    n = src.count(old)
    assert n == count, 'n=%d want %d: %r' % (n, count, old[:60])
    src = src.replace(old, new)

open('cnbuild5.py', 'w', encoding='utf-8').write(src)
print('rewrote derive_keep1 + drawer + wipe, applied %d subs' % len(subs))