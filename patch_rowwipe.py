"""Move box blanking from the loader hook (which cannot reach VRAM) into the
drawer, as one queue entry pair per text row, staged when that row's first
character is drawn.

Run:  python patch_rowwipe.py
"""
import io

p = 'cnbuild5.py'
s = io.open(p, encoding='utf-8', newline='').read()
steps = []


def rep(tag, old, new, count=1):
    global s
    assert s.count(old) == count, (tag, s.count(old))
    s = s.replace(old, new)
    steps.append(tag)


# ---- 1. constants -----------------------------------------------------------
rep('constants', """MSG_DEBUG = True        # per-message hook: counters + two CPU store probes
MSG_TABLE_ROM = 0x1F8000               # bank $3F: the box's blank tile map
MSG_TABLE_LEN = 2048                   # words $7C00-$7FFF as bytes
""", """ROW_WIPE = 2 * (4 + 52)                # one text row: 26 upper + 26 lower cells
ROW_WIPE_CHECK = ROW_WIPE + GLYPH_COST  # what one draw may stage in one flush
""")

# ---- 2. delete build_msgclear() --------------------------------------------
i = s.index('def build_msgclear():')
j = s.index('def build_sanitize():')
s = s[:i] + s[j:]
steps.append('drop build_msgclear')

# ---- 3. main(): the table, the hook install and the msg references ----------
i = s.index("    # the box's blank tile map: $2C00 everywhere")
j = s.index("    print('slots: %d free tile pairs")
s = s[:i] + s[j:]
steps.append('drop blank table')

rep('drop msg build', """    msg = build_msgclear()
    rom[E3_MSG:E3_MSG + len(msg)] = msg
""", "")

rep('layout asserts', """    assert E3_DRAWER + len(drawer) < E3_MSG, (len(drawer),)
    assert E3_MSG + len(msg) < CODE_ROM + 0x8000, (len(msg),)
    for name, code in (('drawer', drawer), ('message hook', msg)):
""", """    assert E3_DRAWER + len(drawer) < E3_MSG, (len(drawer),)
    assert E3_MSG < CODE_ROM + 0x8000
    for name, code in (('drawer', drawer),):
""")

rep('drawer print', """    print('drawer %d B @ROM 0x%06X ($%02X:%04X); message hook %d B ($%02X:%04X)'
          % (len(drawer), E3_DRAWER, db, da, len(msg), *snes_of_rom(E3_MSG)))
""", """    print('drawer %d B @ROM 0x%06X ($%02X:%04X)' % (len(drawer), E3_DRAWER, db, da))
""")

rep('loader hook off', """    ab, aa = snes_of_rom(E3_MSG)
    assert rom[HOOK_LOAD:HOOK_LOAD + 4] == bytes([0xA9, 0x40, 0x0C, 0x73]), \\
        rom[HOOK_LOAD:HOOK_LOAD + 4].hex(' ')
    rom[HOOK_LOAD:HOOK_LOAD + 4] = bytes([0x5C, aa & 0xFF, aa >> 8, ab])
    print('box blanking: $%02X:%04X on $03:EB9E blanks the box text area at '
          'every new entry (%d CPU writes per message)' % (ab, aa, 960))
""", """    # the row loader stays untouched: it runs from the main loop, where even a
    # DMA does not reach VRAM (measured: $3F:8000 -> $7c00 with a marker value in
    # the source table left the box reading $2c00), while the queue's own DMA,
    # fired from VBlank, does.  Blanking therefore rides the queue.
    assert rom[HOOK_LOAD:HOOK_LOAD + 5] == bytes([0xA9, 0x40, 0x0C, 0x73, 0x03]), \\
        rom[HOOK_LOAD:HOOK_LOAD + 5].hex(' ')
    print('box blanking: the drawer wipes a row through the upload queue when the '
          'row starts')
""")

# ---- 4. the drawer: a row wipe helper, an occ path wipe and a reserved guard -
rep('helper', '''    a = Asm(E3_DRAWER)

    def sload(off):''', '''    a = Asm(E3_DRAWER)

    def rowwipe(extra):
        """Stage one 52 byte queue entry blanking the 26 text cells of the row in
        $036e: columns 3..28 of the upper cell row (the lower half of each cell is
        another 26 words at +$20).  X is the queue cursor and is left past the
        entry, so a second call continues the same entry run; A and Y are
        scratch."""
        a.hexs('E2 20')                    # sep #$20
        a.hexs('AD 6E 03')                 # lda $036e (the text row)
        a.hexs('C2 20 29 FF 00')           # rep #$20 / and #$00ff
        for _ in range(6):
            a.hexs('0A')                   # asl x6: 64 words per tile map row
        a.hexs('18 69 %02X %02X' % ((0x7C00 + 3 + extra) & 0xFF,
                                    (0x7C00 + 3 + extra) >> 8))   # adc #$7c03
        a.hexs('9D 00 0B E8 E8')           # sta $0b00,x / inx inx (VRAM address)
        a.hexs('E2 20 A9 80 9D 00 0B E8')  # sep / lda #$80 / sta / inx ($2115)
        a.hexs('A9 34 9D 00 0B E8')        # lda #$34 / sta / inx (52 bytes)
        a.hexs('C2 20 A9 00 2C')           # rep / lda #$2c00 (the blank word)
        a.hexs('A0 1A')                    # ldy #26: words per cell row
        a.label('rw%02X' % extra)
        a.hexs('9D 00 0B E8 E8')           # sta $0b00,x / inx inx
        a.hexs('88')                       # dey
        a.rel(0xD0, 'rw%02X' % extra)      # bne rw (loop)

    def sload(off):''')

rep('occ wipe', """    a.label('occ')
    a.hexs('AD 6F 03 C9 1A')               # lda $036f / cmp #$1a (hook food)""",
    """    a.label('occ')
    # A row starts here if the column is zero.  The engine's own font glyphs (the
    # speaker name, the colon) come through this path, so the wipe has to happen
    # here as well or the row would only be wiped once a Chinese glyph joined it.
    a.hexs('AD 6F 03')                     # lda $036f
    a.rel(0xD0, 'occ0')                    # bne occ0: not the row's first cell
    a.hexs('A9 %02X' % (ROW_WIPE + 8))     # lda #120: the wipe and this character's
                                           # own cell entry
    a.hexs('22 B6 9A 00')                  # jsl $009ab6: room in the queue page?
    a.far_rel(0xB0, 'defer0', 'occw')      # bcs defer0: retry next frame
    a.hexs('AE DF 09')                     # ldx $09df (queue cursor)
    a.hexs('5A')                           # phy (X and Y are the original drawer's)
    rowwipe(0)
    rowwipe(0x20)
    a.hexs('7A')                           # ply
    a.hexs('8E DF 09')                     # stx $09df
    a.label('occ0')
    a.hexs('AD 6F 03 C9 1A')               # lda $036f / cmp #$1a (hook food)""")

rep('guard', """    a.hexs('48')                           # pha: id -> stack
    a.hexs('A9 %02X' % GLYPH_COST)         # lda #GLYPH_COST
    a.hexs('22 B6 9A 00')                  # jsl $009ab6: room in the queue page?
    a.far_rel(0xB0, 'defer', 'guard')      # bcs defer""",
    """    a.hexs('48')                           # pha: id -> stack
    # If this glyph starts a row it carries the row wipe too, so the guard must
    # reserve both.  Column zero and a column at or past the wrap point both mean
    # a row starts (the wrap below turns the second case into column zero).
    a.hexs('AD 6F 03')                     # lda $036f
    a.rel(0xF0, 'g88')                     # beq g88
    a.hexs('C9 %02X' % WRAP_COL)           # cmp #WRAP_COL
    a.rel(0x90, 'g88')                     # bcc g88
    a.hexs('A9 %02X' % ROW_WIPE_CHECK)     # lda #200 (wipe + glyph)
    a.rel(0x80, 'gdone')                   # bra gdone
    a.label('g88')
    a.hexs('A9 %02X' % GLYPH_COST)         # lda #GLYPH_COST
    a.label('gdone')
    a.hexs('22 B6 9A 00')                  # jsl $009ab6: room in the queue page?
    a.far_rel(0xB0, 'defer', 'guard')      # bcs defer""")

rep('cn wipe', """    a.hexs('AD DF 09 C2 20 29 FF 00 AA')   # lda $09df / rep #$20 / and #$00ff / tax
""", """    a.hexs('AD DF 09 C2 20 29 FF 00 AA')   # lda $09df / rep #$20 / and #$00ff / tax
    # X is the queue cursor and Y is id * 64 for the pool reads below, so Y is
    # parked around the wipe.
    a.hexs('AD 6F 03')                     # lda $036f
    a.rel(0xD0, 'norow')                   # bne norow: not the row's first glyph
    a.hexs('5A')                           # phy
    rowwipe(0)
    rowwipe(0x20)
    a.hexs('7A')                           # ply
    a.label('norow')
""")

rep('defer0', """    a.label('defer2')
    a.hexs('E2 30 68 68')                  # sep #$30 / pla pla (id, glyph bank)
    a.long_to(0x01FA7D)                    # jml $03:fa7d (plain rts)
""", """    a.label('defer2')
    a.hexs('E2 30 68 68')                  # sep #$30 / pla pla (id, glyph bank)
    a.long_to(0x01FA7D)                    # jml $03:fa7d (plain rts)

    # the same retry, for the original drawer's path: nothing was pushed there, so
    # the return address must stay on the stack
    a.label('defer0')
    a.hexs('AD E9 03')                     # lda $03e9
    a.rel(0xF0, 'defer0b')                 # beq defer0b
    a.hexs('3A 8D E9 03')                  # dec a / sta $03e9
    a.label('defer0b')
    a.hexs('E2 30')                        # sep #$30
    a.long_to(0x01FA7D)                    # jml $03:fa7d (plain rts)
""")

io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('patched: ' + ', '.join(steps))