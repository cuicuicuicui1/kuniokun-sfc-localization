# -*- coding: utf-8 -*-
"""Replace build_drawer_copy() in cnbuild5.py with the 16x16 version and add
build_wipe() / build_arm().  Run once: python patch_builder16.py"""

NEW = r'''def build_drawer_copy():
    """Draw one 16x16 Chinese glyph as four tiles in two screen cells.

    Entered through a JML planted at ROM 0x01FA30, so PBR is $3E inside this
    code and an RTS would return into the wrong bank: every exit is an explicit
    JML into bank $03.  The character code is read from RAM $12 like the
    original drawer does -- sub6 ($FA0B, the row eraser) calls the drawer with a
    leftover A that has nothing to do with the character.

    The glyph bitmap cannot be written to VRAM directly (the PPU drops a CPU
    write to $2118 outside VBlank), so it is appended to the engine's own upload
    queue in WRAM $0B00, which the flusher at $00:8385 turns into a channel 0
    DMA.  Queue entries are
        [+0/+1] VRAM word address, [+2] $2115, [+3] byte count, [+4...] data,
    and one 16x16 glyph costs 68 data bytes plus two 8 byte tile map cells.
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
    a.hexs('C9 1A')                        # cmp #$1a  (eaten by the 4 byte hook)
    a.long_to(0x01FA35)                    # jml $03:fa35  (the original drawer)

    # ---- Chinese branch ------------------------------------------------------
    a.label('cn')
    a.hexs('AD %02X 0D' % WIPE_PEND)       # lda $0d43  (a box wipe is running)
    a.rel(0xD0, 'defer')                   # bne defer
    a.hexs('AD 6F 03')                     # lda $036f
    a.hexs('C9 %02X' % WRAP_COL)           # cmp #WRAP_COL
    a.rel(0x90, 'room')                    # bcc room   (two cells still fit)
    a.hexs('EE 6E 03')                     # inc $036e  (next row, like $03:FCEA)
    a.hexs('AD 6E 03 C9 10')               # lda $036e / cmp #$10
    a.rel(0x90, 'w1')                      # bcc w1
    a.hexs('9C 6E 03')                     # stz $036e
    a.label('w1')
    a.hexs('9C 6F 03')                     # stz $036f
    a.hexs('EE 6D 03 AD 6D 03 C9 03')      # inc $036d / lda $036d / cmp #$03
    a.rel(0x90, 'room')                    # bcc room
    a.hexs('A9 03 8D 6D 03')               # lda #$03 / sta $036d
    a.hexs('AD 73 03 09 20 8D 73 03')      # lda $0373 / ora #$20 / sta $0373
    a.hexs('9C 71 03')                     # stz $0371
    a.label('room')
    a.hexs('A9 %02X' % GLYPH_COST)         # lda #GLYPH_COST
    a.hexs('22 B6 9A 00')                  # jsl $009ab6  (room in the queue page?)
    a.rel(0xB0, 'defer')                   # bcs defer

    # ---- stage one 64 byte glyph and its two tile map cells ------------------
    a.hexs('8B')                           # phb  (DBR is $03 here)
    a.hexs('A5 12 38 E9 %02X 18 69 %02X 48'
           % (PREFIX0, POOL_BANK0))        # glyph bank = code - $c5 + $21 -> stack
    a.hexs('AD E9 03 1A A8')               # lda $03e9 / inc a / tay
    a.hexs('B9 EA 03')                     # lda $03ea,y   (glyph id = slot)
    a.hexs('C9 %02X' % SLOTS)              # cmp #SLOTS
    a.rel(0xB0, 'cnbad')                   # bcs cnbad
    a.hexs('AA')                           # tax           (X = slot)
    a.hexs('BF 00 E9 03')                  # lda $03e900,x (quad base tile)
    a.hexs('8D %02X 0D' % WIPE_SLOT)       # sta scratch   (the quad tile)
    a.hexs('9C %02X 0D' % (WIPE_SLOT + 1))  # stz scratch+1
    a.hexs('AB')                           # plb           (DBR = glyph bank)
    a.hexs('C2 30')                        # rep #$30
    a.hexs('AF %02X 0D 00' % WIPE_SLOT)    # lda long scratch (the quad)
    a.hexs('29 FF 00')                     # and #$00ff
    a.hexs('0A 0A 0A')                     # asl x3        (quad * 8 words)
    a.hexs('09 00 60')                     # ora #$6000    (VRAM address)
    a.hexs('8F %02X 0D 00' % WIPE_VMADD)   # sta long scratch2
    a.hexs('E2 30')                        # sep #$30
    a.hexs('AF DF 09 00')                  # lda long $09df (append cursor)
    a.hexs('AA')                           # tax           (X = cursor)
    a.hexs('AF %02X 0D 00' % WIPE_VMADD)   # lda long vram address low
    a.hexs('9F 00 0B 00 E8')               # sta long $0b00,x / inx
    a.hexs('AF %02X 0D 00' % (WIPE_VMADD + 1))  # lda long vram address high
    a.hexs('9F 00 0B 00 E8')               # sta long $0b00,x / inx
    a.hexs('A9 80 9F 00 0B 00 E8')         # lda #$80 / sta / inx  (VMAIN)
    a.hexs('A9 %02X 9F 00 0B 00 E8' % POOL_STRIDE)  # count = 64 bytes
    a.hexs('C2 30')                        # rep #$30
    a.hexs('AF %02X 0D 00 29 FF 00' % WIPE_SLOT)  # lda quad / and #$00ff
    for _ in range(6):                     # y = slot * 64
        a.hexs('0A')
    a.hexs('A8')                           # tay
    for _ in range(POOL_STRIDE // 2):      # 32 words: left cell, then right cell
        a.hexs('B9 00 80')                 # lda $8000,y  (DBR = glyph bank)
        a.hexs('9F 00 0B 00')              # sta long $0b00,x
        a.hexs('E8 E8 C8 C8')              # inx inx / iny iny
    a.hexs('E2 30')                        # sep #$30
    a.hexs('A9 03 48 AB')                  # lda #$03 / pha / plb (DBR = $03)
    a.hexs('8E DF 09')                     # stx $09df  (cursor += 68)

    # ---- two tile map cells (the tail of the original drawer, twice) ---------
    a.hexs('AD %02X 0D' % WIPE_SLOT)       # lda quad
    a.hexs('8D %02X 0D' % WIPE_TILE)       # sta tile (scratch)
    a.hexs('AE DF 09')                     # ldx $09df
    a.hexs('AC 6E 03')                     # ldy $036e  (row)
    a.hexs('B9 8E FA')                     # lda $fa8e,y  (cell address low)
    a.hexs('18 6D 6F 03')                  # clc / adc $036f
    a.hexs('9D 00 0B E8')                  # sta $0b00,x / inx
    a.hexs('B9 7E FA 69 00')               # lda $fa7e,y / adc #$00 (carry)
    a.hexs('9D 00 0B E8')                  # sta $0b00,x / inx
    a.hexs('A9 81 9D 00 0B E8')            # lda #$81 / sta / inx
    a.hexs('A9 04 9D 00 0B E8')            # lda #$04 / sta / inx
    a.hexs('AD %02X 0D 09 24' % WIPE_TILE)  # lda tile / ora #$24 (upper half)
    a.hexs('9D 00 0B E8')                  # sta / inx
    a.hexs('AD %02X 0D 1A 09 24' % WIPE_TILE)  # lda tile+1 / ora #$24 (lower)
    a.hexs('9D 00 0B E8')                  # sta / inx
    a.hexs('AC 6E 03')                     # ldy $036e
    a.hexs('B9 8E FA 18 6D 6F 03 1A')      # cell address low of the next column
    a.hexs('9D 00 0B E8')                  # sta / inx
    a.hexs('B9 7E FA 69 00')               # cell address high (with carry)
    a.hexs('9D 00 0B E8')                  # sta / inx
    a.hexs('A9 81 9D 00 0B E8')            # lda #$81 / sta / inx
    a.hexs('A9 04 9D 00 0B E8')            # lda #$04 / sta / inx
    a.hexs('AD %02X 0D 1A 1A 09 24' % WIPE_TILE)  # lda tile+2 / ora #$24
    a.hexs('9D 00 0B E8')                  # sta / inx
    a.hexs('AD %02X 0D 1A 1A 1A 09 24' % WIPE_TILE)  # lda tile+3 / ora #$24
    a.hexs('9D 00 0B E8')                  # sta / inx
    a.hexs('8E DF 09')                     # stx $09df  (cursor += 16)

    # ---- bookkeeping --------------------------------------------------------
    a.hexs('EE E9 03')                     # inc $03e9  (consume the id byte)
    a.hexs('EE 6F 03')                     # inc $036f  ($FA7A adds the second)
    a.hexs('AD 6E 03')                     # lda $036e
    a.hexs('CD %02X 0D' % WIPE_TOP)        # cmp $0d40
    a.rel(0xB0, 'nt')                      # bcs nt     (not lower)
    a.hexs('8D %02X 0D' % WIPE_TOP)        # sta $0d40
    a.label('nt')
    a.hexs('AD 6E 03')                     # lda $036e
    a.hexs('CD %02X 0D' % WIPE_BOT)        # cmp $0d41
    a.rel(0x90, 'nb')                      # bcc nb     (not higher)
    a.hexs('8D %02X 0D' % WIPE_BOT)        # sta $0d41
    a.label('nb')
    a.hexs('68')                           # pla        (the saved DBR)
    a.long_to(0x01FA7A)                    # jml $03:fa7a  (inc $036f / rts)

    # ---- the character cannot be drawn yet: retry on a later frame ----------
    a.label('defer')
    a.hexs('AD E9 03')                     # lda $03e9
    a.rel(0xF0, 'defer2')                  # beq defer2 (index 0: nothing to undo)
    a.hexs('3A 8D E9 03')                  # dec a / sta $03e9 (cancel the consumer)
    a.label('defer2')
    a.long_to(0x01FA7D)                    # jml $03:fa7d  (plain rts)

    # ---- id out of range: eat the byte, leave the cells blank ---------------
    a.label('cnbad')
    a.hexs('68 68')                        # pla pla    (glyph bank + saved DBR)
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
    a.rel(0xD0, 'out')                     # bne out    (wait for the flusher)
    a.hexs('A9 %02X 22 B6 9A 00' % ROW_WIPE)  # lda #ROW_WIPE / jsl $009ab6
    a.rel(0xB0, 'out')                     # bcs out    (queue page full)
    a.hexs('AD %02X 0D' % WIPE_CUR)        # lda $0d42
    a.hexs('C9 10')                        # cmp #$10   (not a box row?)
    a.rel(0xB0, 'finish')                  # bcs finish
    a.hexs('C2 30 29 FF 00')               # rep #$30 / and #$00ff
    for _ in range(6):                     # row * $40
        a.hexs('0A')
    a.hexs('18 69 03 7C')                  # clc / adc #$7c03
    a.hexs('8F %02X 0D 00' % WIPE_VMADD)   # sta long vram address
    a.hexs('AE DF 09')                     # ldx $09df
    for k in (0, 0x20):                    # upper halves, then lower halves
        if k:
            a.hexs('AF %02X 0D 00 18 69 20' % WIPE_VMADD)  # address + 32 words
        else:
            a.hexs('AF %02X 0D 00' % WIPE_VMADD)
        a.hexs('9D 00 0B E8 E8')           # sta $0b00,x / inx inx
        a.hexs('E2 20 A9 80 9D 00 0B E8')  # sep #$20 / lda #$80 / sta / inx
        a.hexs('A9 34 9D 00 0B E8')        # lda #52 / sta / inx
        a.hexs('C2 20 A9 00 2C')           # rep #$20 / lda #$2c00 (blank cell)
        for _ in range(26):                # 26 cells per run
            a.hexs('9D 00 0B E8 E8')       # sta $0b00,x / inx inx
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
    a.long_to(0x01EE74)                    # jml $03:ee74  (phk / plb / ...)
    return a.done()


def build_arm():
    """Arm the box wipe when a new message entry is about to load.

    Hooked onto the engine's per line text loader at $03:EB9E.  $0373 bit6 is
    set while an entry still has lines to come (the loader sets it, the $F3 exit
    clears it), so a cleared bit means this line begins a new entry: the rows my
    glyphs left on screen are about to be reused by different characters and
    must be blanked before the new text draws into them.
    """
    a = Asm(E3_ARM)
    a.hexs('AD 73 03 29 40')               # lda $0373 / and #$40
    a.rel(0xD0, 'noarm')                   # bne noarm  (a continuation line)
    a.hexs('AD %02X 0D' % WIPE_PEND)       # lda $0d43
    a.rel(0xD0, 'noarm')                   # bne noarm  (one wipe at a time)
    a.hexs('AD %02X 0D' % WIPE_TOP)        # lda $0d40
    a.hexs('C9 10')                        # cmp #$10   (nothing drawn since)
    a.rel(0xB0, 'noarm')                   # bcs noarm
    a.hexs('A9 01 8D %02X 0D' % WIPE_PEND)  # lda #$01 / sta $0d43
    a.hexs('AD %02X 0D' % WIPE_BOT)        # lda $0d41
    a.hexs('8D %02X 0D' % WIPE_CUR)        # sta $0d42  (wipe from the top row)
    a.label('noarm')
    a.hexs('A9 10 8D %02X 0D' % WIPE_TOP)  # lda #$10 / sta $0d40
    a.hexs('9C %02X 0D' % WIPE_BOT)        # stz $0d41
    a.hexs('A9 40')                        # lda #$40   (replay the eaten op)
    a.hexs('0C 73 03')                     # tsb $0373
    a.long_to(0x01EBA3)                    # jml $03:eba3
    return a.done()


'''

src = open('cnbuild5.py', encoding='utf-8').read()
i = src.index('def build_drawer_copy():')
j = src.index('def build_sanitize():')
open('cnbuild5.py', 'w', encoding='utf-8').write(src[:i] + NEW + src[j:])
print('replaced %d bytes with %d' % (j - i, len(NEW)))