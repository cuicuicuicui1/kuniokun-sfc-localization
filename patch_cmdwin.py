"""Rewrite the command-window section of cnbuild5.py with the hooked version."""
import io

p = 'cnbuild5.py'
s = io.open(p, encoding='utf-8').read()

start = s.index('# ---------------------------------------------------------- command window')
end = s.index('_glyph_cache = {}', start)

NEW = r'''# ---------------------------------------------------------- command window
# The Start menu is not part of the text system.  The engine copies a fixed
# 52 byte table (26 cells x 2 rows) from ROM $01F743 to WRAM $040A, and its own
# routine at $01F95D turns each byte into a tilemap word through the FA/FB font
# tables -- FB[code] is the upper half of the cell, FA[code] the lower one.  A
# 16x16 hanzi therefore needs two adjacent cells and four tiles.
#
# Those four tiles cannot come from a free part of the font area: that area is
# full (the slot table alone owns 168 of its 256 tiles), and the routine's
# tilemap word hard-codes its high byte ($24), so a tile number above 255 cannot
# be written either.  What makes it possible is that the drawer re-uploads a slot
# entry whenever its glyph is drawn: the window borrows twelve slot entries,
# uploads its glyphs into them through the engine's own VRAM queue as the menu
# opens, and the message box is empty while the menu is up.  A hook at $01F72B
# does that upload before the engine copies the label table.
CMDWIN_ROM = 0x01F743
CMDWIN_ROW = 26
CMDWIN_LABELS = [               # (row, first cell, text) - two cells per hanzi
    (0, 1, '使用气力'),
    (0, 12, '使用道具'),
    (1, 1, '装备'),
    (1, 10, '状态'),
    (1, 21, '扔掉'),
]
CMDWIN_ENTRIES = 12             # slot entries borrowed to hold the window glyphs
CMDWIN_HOOK_SITE = 0x01F72B     # STZ $039E / INC $0392 in the open routine
CMDWIN_HOOK_ROM = 0x1F4200      # $3E:C200  the hook itself
CMDWIN_COPY_ROM = 0x1F4300      # $3E:C300  the 36 byte queue-entry copier
CMDWIN_BLOB_ROM = 0x1F4400      # $3E:C400  the pre-built queue entries
CMDWIN_APPEND = 0x09DF
CMDWIN_ROOM = 0x009AB6          # returns A = size + the append cursor
CMDWIN_ENTRY_BYTES = 36         # 4 byte header + one 32 byte tile pair
# Codes no string in the game uses, so repointing their FA/FB entries cannot
# change anything that is drawn.
CMDWIN_CODES = [0xE4, 0xE6, 0xE8, 0xE9, 0xF1, 0xF8, 0xF9, 0xFA, 0xFB, 0xFC,
                0xFD, 0xFE, 0xDD, 0xDE, 0x85, 0x86, 0x88, 0x8F, 0x95, 0x9C,
                0xA6, 0xA7, 0xA9, 0xAA, 0xB3, 0xBB]


def cmdwin_labels(rom):
    chars = []
    for _r, _c, txt in CMDWIN_LABELS:
        for ch in txt:
            if ch not in chars:
                chars.append(ch)
    need = len(chars) * 2
    if need > len(CMDWIN_CODES):
        raise SystemExit('command window needs %d codes, have %d'
                         % (need, len(CMDWIN_CODES)))
    n_entries = (SLOTS + LABEL_GLYPHS * LABEL_SETS
                 + LABEL_NAME_GLYPHS * LABEL_NAME_SETS)
    entries = list(range(CMDWIN_ENTRIES))
    if entries[-1] >= n_entries:
        raise SystemExit('not enough slot entries to borrow')

    blob = bytearray()
    code_of = {}
    for i, ch in enumerate(chars):
        e = entries[i]
        pa = rom[E3_SLOTPAIR + e]                 # left half, upper tile
        pb = rom[E3_SLOTPAIR + n_entries + e]     # right half, upper tile
        g = glyph64(ch)                           # TL BL TR BR, 16 bytes each
        for tile, data in ((pa, g[0:32]), (pb, g[32:64])):
            vm = 0x6000 + tile * 8                # the VRAM word address
            blob += bytes([vm & 0xFF, vm >> 8, 0x80, 0x20]) + data
        code_of[ch] = (CMDWIN_CODES[2 * i], CMDWIN_CODES[2 * i + 1])
    assert len(blob) == len(chars) * 2 * CMDWIN_ENTRY_BYTES, len(blob)
    rom[CMDWIN_BLOB_ROM:CMDWIN_BLOB_ROM + len(blob)] = bytes(blob)

    fa = bytearray(rom[km.FA_OFF:km.FA_OFF + 256])
    fb = bytearray(rom[km.FB_OFF:km.FB_OFF + 256])
    for i, ch in enumerate(chars):
        e = entries[i]
        pa = rom[E3_SLOTPAIR + e]
        pb = rom[E3_SLOTPAIR + n_entries + e]
        ca, cb_ = code_of[ch]
        fb[ca], fa[ca] = pa, pa + 1               # upper / lower of the left half
        fb[cb_], fa[cb_] = pb, pb + 1             # upper / lower of the right half
    rom[km.FA_OFF:km.FA_OFF + 256] = bytes(fa)
    rom[km.FB_OFF:km.FB_OFF + 256] = bytes(fb)

    tbl = bytearray(CMDWIN_ROW * 2)
    for row, cell, txt in CMDWIN_LABELS:
        q = row * CMDWIN_ROW + cell
        for ch in txt:
            ca, cb_ = code_of[ch]
            tbl[q], tbl[q + 1] = ca, cb_
            q += 2
    rom[CMDWIN_ROM:CMDWIN_ROM + len(tbl)] = bytes(tbl)

    cmdwin_hook(rom, len(chars))
    print('command window: %d labels, %d hanzi, entries 0..%d, codes $%02X-$%02X,'
          ' %d queue entries staged'
          % (len(CMDWIN_LABELS), len(chars), len(chars) - 1, CMDWIN_CODES[0],
             CMDWIN_CODES[need - 1], len(chars) * 2))


def cmdwin_hook(rom, nglyph):
    """Stage the window's glyphs into the borrowed entries, then open the menu.

    The hook sits where the open routine sets up ($01F72B) and replaces its two
    instructions, which it re-executes on the way out.  It pushes one 36 byte
    queue entry per pass, waiting through $009AB6 until the flusher has emptied
    the page, so twelve glyphs take a couple of dozen frames -- invisible, since
    the menu is not on screen yet.
    """
    total = nglyph * 2 * CMDWIN_ENTRY_BYTES
    c = Asm(CMDWIN_COPY_ROM)
    for k in range(CMDWIN_ENTRY_BYTES):
        c.hexs('BF %02X %02X 3E' % ((CMDWIN_BLOB_ROM + k) & 0xFF,
                                    ((CMDWIN_BLOB_ROM + k) >> 8) & 0xFF))
        c.hexs('99 00 0B')                          # sta $0b00,y
        c.hexs('E8 C8')                             # inx / iny
    c.hexs('6B')                                    # rtl
    rom[CMDWIN_COPY_ROM:CMDWIN_COPY_ROM + len(c.b)] = c.b

    a = Asm(CMDWIN_HOOK_ROM)
    a.hexs('08 E2 30 48 DA 5A')                     # php / sep #$30 / pha phx phy
    a.hexs('C2 10')                                 # rep #$10: 16 bit X
    a.hexs('A2 00 00')                              # ldx #$0000
    a.label('stage')
    a.hexs('A9 %02X' % CMDWIN_ENTRY_BYTES)          # lda #36
    a.hexs('22 B6 9A 00')                           # jsl $009ab6
    a.hexs('C9 F9')                                 # cmp #$f9
    a.rel(0xB0, 'stage')                            # bcs stage: page not free yet
    a.hexs('AC DF 09')                              # ldy $09df
    a.hexs('22 %02X %02X 3E' % (CMDWIN_COPY_ROM & 0xFF,
                                (CMDWIN_COPY_ROM >> 8) & 0xFF))   # jsl copier
    a.hexs('8C DF 09')                              # sty $09df
    a.hexs('E0 %02X %02X' % (total & 0xFF, total >> 8))   # cpx #total
    a.rel(0x90, 'stage')                            # bcc stage
    a.hexs('E2 10')                                 # sep #$10: 8 bit X again
    a.hexs('7A FA 68')                              # ply / plx / pla
    a.hexs('28')                                    # plp
    a.hexs('9C 9E 03')                              # stz $039e   (the instructions
    a.hexs('EE 92 03')                              # inc $0392   we replaced)
    a.hexs('A0 00')                                 # ldy #$00
    a.long_to(0x01F733)                             # and back into the routine
    rom[CMDWIN_HOOK_ROM:CMDWIN_HOOK_ROM + len(a.b)] = a.b

    bk, ad = snes_of_rom(CMDWIN_HOOK_ROM)
    site = bytes([0x5C, ad & 0xFF, ad >> 8, bk, 0xEA, 0xEA])
    assert rom[CMDWIN_HOOK_SITE:CMDWIN_HOOK_SITE + 2] == bytes([0x9C, 0x9E]), \
        rom[CMDWIN_HOOK_SITE:CMDWIN_HOOK_SITE + 6].hex(' ')
    rom[CMDWIN_HOOK_SITE:CMDWIN_HOOK_SITE + 6] = site


'''

s = s[:start] + NEW + s[end:]
io.open(p, 'w', encoding='utf-8').write(s)
print('command window section replaced')