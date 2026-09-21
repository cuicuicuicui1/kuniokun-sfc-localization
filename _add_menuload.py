import io
p = 'cnbuild5.py'
s = io.open(p, encoding='utf-8').read()

anchor = "def build_menuclose(rom):"
fn = '''def build_menuload(rom, table):
    """Stage the command window's label glyphs into the upload queue.

    Armed by the menu's own open step (build_menuclose's arming stub) and driven
    from the state dispatcher at $03:F0F8, which runs every frame the menu is
    open.  Each call copies up to three glyphs from the pool to the slot tiles
    the label codes name; the queue's VBlank flusher does the VRAM writes, so
    nothing here touches the VRAM ports.  Ten glyphs therefore land in four
    frames, which the player cannot see.

    The per-glyph record is [vram addr of t][vram addr of u][pool addr][pool
    bank]; the second 32 bytes of the glyph come from pool addr + 32.
    """
    nglyph = len(table) // 7
    a = Asm(MENU_STUB)
    a.hexs('08 E2 30')                     # php / sep #$30
    a.hexs('AD %02X %02X' % (MENU_LOAD & 0xFF, MENU_LOAD >> 8))
    a.rel(0xF0, 'out')                     # beq out: nothing pending
    a.hexs('64 14')                        # stz $14: glyphs staged this call
    a.label('next')
    a.hexs('AD %02X %02X' % (MENU_LOAD & 0xFF, MENU_LOAD >> 8))
    a.hexs('3A')                           # dec a -> 0 based glyph index
    a.hexs('C9 %02X' % nglyph)
    a.rel(0xB0, 'done')                    # bcs done: all of them staged
    a.hexs('85 15')                        # sta $15
    # room for both entries (2 x 36 bytes) or leave it to the next frame
    a.hexs('AD DF 09 C9 %02X' % (0x101 - 72))
    a.rel(0xB0, 'out')                     # bcs out: no room, retry next frame
    # the table offset = index * 7
    a.hexs('A5 15 0A 0A 0A 38 E5 15')      # lda $15 / asl x3 / sec / sbc $15
    a.hexs('AA')                           # tax
    a.hexs('BF %02X %02X %02X' % (MENU_TAB & 0xFF, (MENU_TAB >> 8) & 0xFF, MENU_TAB >> 15))
    a.hexs('85 1A')                        # lda table+0,x -> sta $1a (t addr lo)
    a.hexs('BF %02X %02X %02X' % ((MENU_TAB + 1) & 0xFF, (MENU_TAB >> 8) & 0xFF, MENU_TAB >> 15))
    a.hexs('85 1B')                        # -> $1b (t addr hi)
    a.hexs('BF %02X %02X %02X' % ((MENU_TAB + 2) & 0xFF, (MENU_TAB >> 8) & 0xFF, MENU_TAB >> 15))
    a.hexs('85 1C')                        # -> $1c (u addr lo)
    a.hexs('BF %02X %02X %02X' % ((MENU_TAB + 3) & 0xFF, (MENU_TAB >> 8) & 0xFF, MENU_TAB >> 15))
    a.hexs('85 1D')                        # -> $1d (u addr hi)
    a.hexs('BF %02X %02X %02X' % ((MENU_TAB + 4) & 0xFF, (MENU_TAB >> 8) & 0xFF, MENU_TAB >> 15))
    a.hexs('85 16')                        # -> $16 (pool addr lo)
    a.hexs('BF %02X %02X %02X' % ((MENU_TAB + 5) & 0xFF, (MENU_TAB >> 8) & 0xFF, MENU_TAB >> 15))
    a.hexs('85 17')                        # -> $17 (pool addr hi)
    a.hexs('BF %02X %02X %02X' % ((MENU_TAB + 6) & 0xFF, (MENU_TAB >> 8) & 0xFF, MENU_TAB >> 15))
    a.hexs('85 18')                        # -> $18 (pool bank)
    for half, (lo, hi) in enumerate((('1a', '1b'), ('1c', '1d'))):
        a.hexs('A5 %s 85 1E' % lo)         # lda addr lo / sta $1e (the header word)
        a.hexs('A5 %s 85 1F' % hi)         # lda addr hi / sta $1f
        a.hexs('AE DF 09')                 # ldx $09df
        a.hexs('A5 1E 9D 00 0B E8')        # lda $1e / sta $0b00,x / inx
        a.hexs('A5 1F 9D 00 0B E8')        # lda $1f / sta / inx
        a.hexs('A9 80 9D 00 0B E8')        # lda #$80 ($2115) / sta / inx
        a.hexs('A9 20 9D 00 0B E8')        # lda #32 (bytes) / sta / inx
        a.hexs('C2 20 A0 %02X' % (0 if half == 0 else 32))
        a.hexs('')                         # rep #$20 / ldy #0 or #32
        a.label('w%d' % half)
        a.hexs('B7 16 9D 00 0B E8 E8 C8 C8 C0 40')
        a.hexs('90 F5')                    # bcc w (cpy #64 / bcc w)
        a.hexs('E2 20 8E DF 09')           # sep #$20 / stx $09df (commit)
    a.hexs('E6 14')                        # inc $14
    a.hexs('EE %02X %02X' % (MENU_LOAD & 0xFF, MENU_LOAD >> 8))
    a.hexs('A5 14 C9 03')                  # lda $14 / cmp #3
    a.rel(0x90, 'next')                    # bcc next: three per frame is enough
    a.jmp_to('out')
    a.label('done')
    a.hexs('9C %02X %02X' % (MENU_LOAD & 0xFF, MENU_LOAD >> 8))
    a.label('out')
    a.hexs('28')                           # plp
    a.hexs('AD 92 03')                     # the instruction the hook ate
    a.long_to(0x01F0FB)                    # jml back into the dispatcher
    code = a.done()
    rom[MENU_STUB:MENU_STUB + len(code)] = code
    rom[MENU_TAB:MENU_TAB + len(table)] = table
    bk, ad = snes_of_rom(MENU_STUB)
    print('menu label uploader: %d bytes at $%02X:%04X, %d glyphs, table %d bytes'
          % (len(code), bk, ad, nglyph, len(table)))
    return bk, ad


def build_menuclose(rom):'''
assert anchor in s
s = s.replace(anchor, fn, 1)
io.open(p, 'w', encoding='utf-8').write(s)
print('ok')
