"""Rewrite build_msgclear() to blank the box with a single DMA transfer.

Replaces the CPU direct write version (which hardware testing showed never
reached VRAM) and adds two small CPU store probes so the same build answers
which store form can reach VRAM at all.
"""
import io
import re

SRC = 'cnbuild5.py'
s = io.open(SRC, encoding='utf-8', newline='').read()

new = '''def build_msgclear():
    """Blank the box text area once per message, with one DMA transfer.

    Hooked over the row loader's first five bytes at $03:EB9E (replaced by
    ``5C 00 88 3E``), which are replayed before jumping back to $03:EBA3.  The
    loader runs for one line of text at a time and $0373 bit6 is clear exactly
    when that line starts a new entry, so this blanks once per message.

    The transfer is a plain DMA because that is the only mechanism observed to
    reach VRAM in this game: the engine's box opener $03:E9B6 fills
    $7800-$7FFF by writing $2116/$2118 from the CPU, but a hook doing the same
    thing (960 words, the address re-set before every word, exactly the
    engine's shape) changed nothing, while the same word written into the
    $0B00 queue - whose flusher is a DMA - landed and persisted for hundreds
    of frames.  The register pattern below is the flusher's own: DMAP $01
    (two bytes to $2118, so one VRAM word per two source bytes), source
    through $4302/$4303, count through $4305/$4306, trigger through $420B bit
    0.  NMI is masked only while the registers are set up, because a general
    DMA runs to completion before an interrupt is taken but the NMI handler
    would overwrite $4300+ with its own flush.

    The table at ROM $3F:8000 is the box's blank state, read off a hardware
    dump of the box right after the engine had opened it: $2C00 everywhere
    except the four border columns of every row (col 0/32 = $2CF0, col 31/63 =
    $6CF0).  Clearing includes the two 8x8 halves of a text cell, which are
    columns C and C+32 of the same row.

    The engine itself never clears between messages, so its box text simply
    accumulates; blanking here is a deliberate behaviour change (documented in
    the readme) that frees the 42 glyph slots from having to hold every glyph
    a screen might otherwise still be showing.
    """
    a = Asm(E3_MSG)
    if MSG_DEBUG:
        a.hexs('EE F1 0D')                 # inc $0df1: debug entry counter
    a.hexs('08 E2 30')                     # php / sep #$30: M = 8, X = 8
    a.hexs('AD 73 03 29 40')               # lda $0373 / and #$40
    a.rel(0xD0, 'noarm')                   # bne noarm (a continuation line)
    if MSG_DEBUG:
        a.hexs('EE F2 0D')                 # inc $0df2: blank branch taken
        # Probe A: address and data both written as single bytes.  If this one
        # lands, VRAM word $6008 becomes $ffff.
        a.hexs('A9 08 8D 16 21 A9 60 8D 17 21')    # word address $6008
        a.hexs('A9 FF 8D 18 21 8D 19 21')          # low byte, then high byte
        # Probe B: same address, but the data through a 16 bit store, which is
        # how $03:E9B6 writes.  If this one lands, word $6009 becomes $aaaa.
        a.hexs('A9 09 8D 16 21 A9 60 8D 17 21')    # word address $6009
        a.hexs('C2 20 A9 AA AA 8D 18 21 E2 20')    # rep / lda #$aaaa / sta $2118
    a.hexs('A9 80 8D 15 21')               # lda #$80 / sta $2115: +1 per word
    a.hexs('AD 00 42 48 29 7F 8D 00 42')   # save $4200, mask NMI off
    a.hexs('A9 00 8D 16 21 A9 7C 8D 17 21')  # VMADD = $7c00
    a.hexs('C2 30 A9 01 18 8D 00 43')      # rep #$30 / lda #$1801 / sta $4300
    a.hexs('A9 00 80 8D 02 43')            # lda #$8000 / sta $4302 (source)
    a.hexs('A9 00 08 8D 05 43')            # lda #$0800 / sta $4305 (2048 bytes)
    a.hexs('E2 20 A9 3F 8D 04 43')         # sep #$20 / lda #$3f / sta $4304
    a.hexs('A9 01 8D 0B 42')               # lda #$01 / sta $420b: channel 0
    a.hexs('68 8D 00 42')                  # pla / sta $4200: NMI back on
    if MSG_DEBUG:
        a.hexs('EE F3 0D')                 # inc $0df3: blank finished
    a.hexs('28')                           # plp
    a.label('noarm')
    a.hexs('A9 40 0C 73 03')               # lda #$40 / tsb $0373 (the hook's food)
    a.long_to(0x01EBA3)                    # jml $03:eba3
    return a.done()


'''

start = s.index('def build_msgclear():')
end = s.index('def build_sanitize():')
old = s[start:end]
assert old.count('def build_msgclear') == 1
s = s[:start] + new + s[end:]

# constants
old_c = "MSG_DEBUG = True        # per-message hook: count markers + a VRAM probe word"
assert s.count(old_c) == 1
new_c = ("MSG_DEBUG = True        # per-message hook: counters + two CPU store probes\n"
         "MSG_TABLE_ROM = 0x1F8000               # bank $3F: the box's blank tile map\n"
         "MSG_TABLE_LEN = 2048                   # words $7C00-$7FFF as bytes")
s = s.replace(old_c, new_c)

# build the table in main(): right after the glyph pool is written
anchor = "    rom[E3_SLOTPAIR:E3_SLOTPAIR + len(slotpairs)] = slotpairs"
assert s.count(anchor) == 1, s.count(anchor)
table_code = anchor + '''

    # the box's blank tile map: $2C00 everywhere, the four border columns of
    # every row kept, so that the blank restores the frame as the engine drew it
    blank = bytearray()
    for row in range(32):
        for col in range(64):
            v = 0x2CF0 if col in (0, 32) else 0x6CF0 if col in (31, 63) else 0x2C00
            blank += bytes((v & 0xFF, v >> 8))
    assert len(blank) == MSG_TABLE_LEN
    rom[MSG_TABLE_ROM:MSG_TABLE_ROM + MSG_TABLE_LEN] = blank'''
s = s.replace(anchor, table_code)

io.open(SRC, 'w', encoding='utf-8', newline='').write(s)
print('patched', SRC)