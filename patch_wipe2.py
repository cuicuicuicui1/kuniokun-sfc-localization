"""Move the box wipe staging from the driver entry hook into the drawer.

The driver-hook stager only enqueued its entries when the queue happened to be
empty, and the entries then sat in the queue while the flusher walk skipped over
them (the glyph entries staged by the drawer always reached VRAM, the wipe rows
never did).  The drawer's own entries are the proven path, so the stager becomes
a JSL subroutine called by the drawer right before it stages a glyph.  The
drawer reserves ROW_WIPE + GLYPH_COST bytes with the engine's own room check
($009AB6) first, so the wipe row and the glyph always travel in the same flush,
wipe first.

Bookkeeping: WIPE_TOP/WIPE_BOT keep tracking the rows the current message drew
into (the drawer updates them, the arm resets them) while the new WIPE_LO holds
the lowest row the pending wipe has to clear, so arming a fresh window can no
longer disturb the wipe that is still running.
"""
import io

P = 'cnbuild5.py'
src = io.open(P, encoding='utf-8', newline='').read().replace('\r\n', '\n')


def sub(old, new, tag):
    global src
    assert src.count(old) == 1, (tag, src.count(old))
    src = src.replace(old, new)
    print('patched', tag)


# ------------------------------------------------------------------ constants
sub("""WIPE_ADDR = 0x0D54                     # scratch: wipe stager VRAM address
""",
    """WIPE_ADDR = 0x0D54                     # scratch: wipe stager VRAM address
WIPE_LO = 0x0D58                       # lowest box row the pending wipe must clear
""", 'const WIPE_LO')

# ------------------------------------------------------------- drawer: guard
sub("""    a.label('checks')
    a.hexs('AD %02X 0D' % ((WIPE_PEND) & 0xFF))       # lda $0d43 (a box wipe is running)
    a.far_rel(0xD0, 'defer', 'wipe')       # bne defer (too far for rel)
    a.hexs('AD 6F 03')                     # lda $036f
""",
    """    a.label('checks')
    a.hexs('A9 %02X' % GLYPH_COST)         # lda #GLYPH_COST
    a.hexs('AE %02X 0D' % ((WIPE_PEND) & 0xFF))       # ldx $0d43 (a box row is due too)
    a.rel(0xF0, 'groom')                   # beq groom
    a.hexs('A9 %02X' % (ROW_WIPE + GLYPH_COST))       # lda #ROW_WIPE+GLYPH_COST
    a.label('groom')
    a.hexs('22 B6 9A 00')                  # jsl $009ab6 (room in the queue page?)
    a.far_rel(0xB0, 'defer', 'guard')      # bcs defer (too far for rel)
    _wb, _wa = snes_of_rom(E3_WIPE)
    a.hexs('22 %02X %02X %02X' % (_wa & 0xFF, _wa >> 8, _wb))   # jsl $3e:wipe
    a.hexs('AD 6F 03')                     # lda $036f
""", 'drawer guard')

sub("""    a.label('room')
    a.hexs('A9 %02X' % GLYPH_COST)         # lda #GLYPH_COST
    a.hexs('22 B6 9A 00')                  # jsl $009ab6 (room in the queue page?)
    a.far_rel(0xB0, 'defer', 'guard')      # bcs defer (too far for rel)

    # ---- slot, glyph id, tiles""",
    """    a.label('room')

    # ---- slot, glyph id, tiles""", 'drawer room')

# ------------------------------------------------------------------ wipe blob
old_wipe_start = """def build_wipe():
    \"\"\"Stage one box row of blanks per queue flush while a wipe is pending.

    Entered through the 4 byte JML at $03:EE70, the per frame entry of the text
    state machine; the eaten prologue is replayed and control continues at
    $03:EE74 so that the machine's own epilogue still balances the stack.

    A row is two 26 word runs -- the upper halves of the 26 text cells and their
    lower halves 32 words further on -- each staged as one 56 byte queue entry.
    \"\"\"
    a = Asm(E3_WIPE)
    a.hexs('08 8B E2 30')                  # php / phb / sep #$30 (prologue, 4 B)
    a.hexs('A9 03 48 AB')                  # lda #$03 / pha / plb (DBR = $03)
    a.hexs('AD %02X 0D' % ((WIPE_PEND) & 0xFF))       # lda $0d43
    a.far_rel(0xF0, 'out', 'wpend')        # beq out (too far for rel)
    a.hexs('AD DD 09 CD DF 09')            # lda $09dd / cmp $09df
    a.far_rel(0xD0, 'out', 'wflush')       # bne out (too far for rel)
    a.hexs('A9 %02X 22 B6 9A 00' % ROW_WIPE)  # lda #ROW_WIPE / jsl $009ab6
    a.far_rel(0xB0, 'out', 'wroom')        # bcs out (too far for rel)
    a.hexs('AD %02X 0D' % ((WIPE_CUR) & 0xFF))        # lda $0d42
"""
new_wipe_start = """def build_wipe():
    \"\"\"Stage the blanks of one box row into the engine's upload queue.

    Called with JSL from the drawer, which has already reserved
    ROW_WIPE + GLYPH_COST bytes with the engine's own room check and stages its
    glyph right after this returns: a wiped row therefore always reaches VRAM in
    the same flush as - and before - the glyph that replaces the old text.  Only
    one row is staged per call so a message never blocks for long; a message that
    used three rows is clear again after the next three glyphs.

    A row is two 26 word runs -- the upper halves of the 26 text cells and their
    lower halves 32 words further on -- each staged as one 56 byte queue entry.
    Rows run from WIPE_CUR down to WIPE_LO inclusive.

    Entered and left with the DBR and the M/X widths the drawer had, so the
    caller's address prefixes keep working.
    \"\"\"
    a = Asm(E3_WIPE)
    a.hexs('08 8B E2 30')                  # php / phb / sep #$30
    a.hexs('A9 03 48 AB')                  # lda #$03 / pha / plb (DBR = $03)
    a.hexs('AD %02X 0D' % ((WIPE_PEND) & 0xFF))       # lda $0d43
    a.far_rel(0xF0, 'out', 'wpend')        # beq out (too far for rel)
    a.hexs('AD %02X 0D' % ((WIPE_CUR) & 0xFF))        # lda $0d42
"""
sub(old_wipe_start, new_wipe_start, 'wipe prologue')

sub("""    a.hexs('AD %02X 0D' % ((WIPE_CUR) & 0xFF))        # advance the wipe
    a.hexs('CD %02X 0D' % ((WIPE_TOP) & 0xFF))        # cmp $0d40 (reached the lowest row?)
    a.rel(0xF0, 'finish')                  # beq finish
    a.hexs('3A 8D %02X 0D' % ((WIPE_CUR) & 0xFF))     # dec a / sta $0d42
    a.rel(0x80, 'out')                     # bra out
    a.label('finish')
    a.hexs('A9 10 8D %02X 0D' % ((WIPE_CUR) & 0xFF))  # lda #$10 / sta $0d42
    a.hexs('9C %02X 0D' % ((WIPE_PEND) & 0xFF))       # stz $0d43
    a.hexs('A9 10 8D %02X 0D' % ((WIPE_TOP) & 0xFF))  # lda #$10 / sta $0d40
    a.hexs('9C %02X 0D' % ((WIPE_BOT) & 0xFF))        # stz $0d41
    a.label('out')
    a.long_to(0x01EE74)                    # jml $03:ee74 (phk / plb / ...)
    return a.done()
""",
    """    a.hexs('AD %02X 0D' % ((WIPE_CUR) & 0xFF))        # advance the wipe
    a.hexs('CD %02X 0D' % ((WIPE_LO) & 0xFF))         # cmp $0d58 (reached the lowest row?)
    a.rel(0xF0, 'finish')                  # beq finish
    a.hexs('3A 8D %02X 0D' % ((WIPE_CUR) & 0xFF))     # dec a / sta $0d42
    a.rel(0x80, 'out')                     # bra out
    a.label('finish')
    a.hexs('A9 10 8D %02X 0D' % ((WIPE_CUR) & 0xFF))  # lda #$10 / sta $0d42
    a.hexs('9C %02X 0D' % ((WIPE_PEND) & 0xFF))       # stz $0d43
    a.label('out')
    a.hexs('AB 28 18 60')                  # plb / plp / clc / rts
    return a.done()
""", 'wipe epilogue')

# -------------------------------------------------------------------- arm blob
sub("""    a.hexs('A9 01 8D %02X 0D' % ((WIPE_PEND) & 0xFF))  # lda #$01 / sta $0d43
    a.hexs('AD %02X 0D' % ((WIPE_BOT) & 0xFF))        # lda $0d41
""",
    """    a.hexs('A9 01 8D %02X 0D' % ((WIPE_PEND) & 0xFF))  # lda #$01 / sta $0d43
    a.hexs('AD %02X 0D 8D %02X 0D' % ((WIPE_TOP) & 0xFF,
                                      (WIPE_LO) & 0xFF))  # lda $0d40 / sta $0d58
    a.hexs('AD %02X 0D' % ((WIPE_BOT) & 0xFF))        # lda $0d41
""", 'arm LO')

# ------------------------------------------------------------------- main wire
sub("""    wb, wa = snes_of_rom(E3_WIPE)
    assert rom[HOOK_DRIVER:HOOK_DRIVER + 4] == bytes([0x08, 0x8B, 0xE2, 0x30]), \\
        rom[HOOK_DRIVER:HOOK_DRIVER + 4].hex(' ')
    rom[HOOK_DRIVER:HOOK_DRIVER + 4] = bytes([0x5C, wa & 0xFF, wa >> 8, wb])
""",
    """    assert rom[HOOK_DRIVER:HOOK_DRIVER + 4] == bytes([0x08, 0x8B, 0xE2, 0x30]), \\
        rom[HOOK_DRIVER:HOOK_DRIVER + 4].hex(' ')   # untouched: the drawer calls the wipe
""", 'main driver hook')

io.open(P, 'w', encoding='utf-8', newline='\n').write(src)
print('written', P)