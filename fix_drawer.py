"""Splice in the corrected drawer copy.

The old copy ended in RTS while PBR was $3E (set by the JML hook), so the return
went into my glyph pool instead of the engine in bank $03 -- that is the freeze.
Every exit is now an explicit JML into bank $03, and the original routine (which
ends in its own RTS) does the work for non-Chinese codes, so the copy no longer
duplicates it.
"""
import re

PATH = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/cnbuild5.py'
src = open(PATH, encoding='utf-8').read()

NEW = '''def build_drawer_copy():
    """Chinese front end for the dialog drawer, entered through a JML planted at
    ROM 0x01FA30.

    The hook is a JML, so PBR is $3E inside this code: nothing here may return
    with RTS.  Every exit is an explicit JML back into bank $03 instead, which
    keeps the caller's return address untouched on the stack.

    The original routine is NOT copied.  For a non-Chinese code the front end
    replays its first instruction and jumps to $03:FA33, so the engine's own
    drawer -- including its right-edge guard and, more importantly, its RTS --
    does the whole job.  Only the two byte code needs its own path.

    Chinese codes take two bytes in the message buffer ([0xC5+page][id]), so the
    id is at $03EA + $03E9 + 1 and this code must consume BOTH bytes: it bumps
    $03E9 for the id, and the consumer bumps it again for the prefix.  The glyph
    goes into VRAM slot SLOTPAIR[id] and a tile map entry for it is staged in the
    RAM script buffer exactly like the original stages a Japanese one.

    Entry: A = code, $12 = code, DBR = PBR = $03, M = X = 8 bit.
    """
    a = Asm(E3_DRAWER)
    a.op(0xA5, 0x12)                     # LDA $12 -- the code really lives there
    a.op(0xC9, PREFIX0)                  # CMP #$C5
    a.rel(0x90, 'orig')
    a.op(0xC9, PREFIX0 + PAGES)          # CMP #$D2
    a.rel(0x90, 'cn')

    a.label('orig')
    # Not a Chinese code (Japanese, punctuation, a $D0-$EF macro byte, or the
    # all-zero code the line-erase loop passes in $12).  Hand it to the engine's
    # drawer: JML, not RTS, so PBR becomes $03 again and the routine's own RTS
    # returns to whoever called $FA30.
    a.op(0xAD, 0x6F, 0x03)               # LDA $036F (the original's 1st insn)
    a.long_to(0x01FA33)                  # JML $03:FA33 (CMP #$1A / ...)

    a.label('cn')
    a.op(0xAD, 0x6F, 0x03)               # LDA $036F (column)
    a.op(0xC9, 0x1A)                     # CMP #$1A
    a.rel(0x90, 'cngo')
    # Past the right edge: the original only advances the column, but a Chinese
    # code is two bytes, so its id byte has to be eaten here or the consumer
    # would decode it as the next code.
    a.op(0xAF, 0xE9, 0x03, 0x00)         # LDA $0003E9
    a.op(0x1A)                           # INC A (no INC long on the 65816)
    a.op(0x8F, 0xE9, 0x03, 0x00)         # STA $0003E9
    a.long_to(0x01FA7A)                  # JML $03:FA7A (INC $036F / RTS)

    a.label('cngo')
    # No DMA at all: channel 1 is shared with the game's HDMA (which writes
    # $420C from RAM $09FF), so borrowing the channel and writing $43x0-$43x6
    # lets the HDMA unit read a half rewritten setup back.  The glyph goes to
    # VRAM through the CPU data port instead: VMAIN = $80 makes one 16 bit write
    # to $2118 advance exactly one word, and the glyph's row interleaved 2bpp
    # byte pairs are one word per pixel row.  Only $2115-$2119 are touched.
    a.op(0x8B)                           # PHB (keep the caller's DBR = $03)
    a.op(0xA5, 0x12)                     # LDA $12
    a.op(0x38, 0xE9, PREFIX0)            # SEC / SBC #$C5 -> page
    a.op(0x18, 0x69, POOL_BANK0)         # CLC / ADC #$21 -> glyph bank
    a.op(0x48)                           # PHA (M = 8 on entry)
    a.op(0xAF, 0xE9, 0x03, 0x00)         # LDA $0003E9
    a.op(0x1A, 0xA8)                     # INC A / TAY -> index of the id byte
    a.op(0xB9, 0xEA, 0x03)               # LDA $03EA,Y -> id   (DBR = $03 here)
    a.op(0xC9, SLOTS)                    # CMP #SLOTS
    a.rel(0x90, 'cnok')
    a.op(0x68, 0xAB)                     # PLA / PLB -> back to the original path
    a.jmp_to('orig')
    a.label('cnok')
    a.op(0xAA)                           # TAX (id)
    a.op(0xAB)                           # PLB -> DBR = glyph bank
    a.op(0x8A)                           # TXA
    a.op(0xC2, 0x30, 0x29, 0xFF, 0x00)   # REP #$30 / AND #$00FF
    a.op(0x0A, 0x0A, 0x0A, 0x0A, 0x0A)   # ASL x5 -> id*32, offset in the pool
    a.op(0xA8)                           # TAY (16 bit index)
    a.op(0xE2, 0x20)                     # SEP #$20 (X/Y stay 16 bit)
    a.op(0xBF, 0x00, 0xE9, 0x03)         # LDA $03:E900,X -> tile pair
    a.op(0xC2, 0x20, 0x29, 0xFF, 0x00)
    a.op(0x0A, 0x0A, 0x0A)               # pair*8 words -> VRAM destination
    a.op(0x09, 0x00, 0x60, 0x8D, 0x16, 0x21)   # ORA #$6000 / STA $2116
    a.op(0xE2, 0x20)
    a.op(0xA9, 0x80, 0x8D, 0x15, 0x21)   # $2115 = $80: one word per write
    a.op(0xC2, 0x20)                     # REP #$20: stream the 16 words
    for _ in range(16):
        a.op(0xB9, 0x00, 0x80)           # LDA $8000,Y  (glyph row pair)
        a.op(0x8D, 0x18, 0x21)           # STA $2118    (whole word)
        a.op(0xC8, 0xC8)                 # INY / INY
    a.op(0xE2, 0x30)                     # SEP #$30
    a.op(0xAB)                           # PLB -> DBR = $03 again
    # stage the RAM DMA script exactly like the original drawer: X walks the
    # staging buffer at $0B00, Y is the text row
    a.op(0xBD, 0x00, 0xE9)               # LDA $E900,X -> tile pair
    a.op(0x48)                           # PHA
    a.op(0xA9, 0x81, 0x8D, 0x15, 0x21)   # $2115 = $81 for the tilemap script
    a.op(0xAE, 0xDF, 0x09)               # LDX $09DF (staging pointer)
    a.op(0xAC, 0x6E, 0x03)               # LDY $036E (row)
    a.op(0xB9, 0x8E, 0xFA, 0x18, 0x6D, 0x6F, 0x03)
    a.op(0x9D, 0x00, 0x0B, 0xE8)         # script byte 0: VRAM address low
    a.op(0xB9, 0x7E, 0xFA, 0x9D, 0x00, 0x0B, 0xE8)     # byte 1: address high
    a.op(0xA9, 0x81, 0x9D, 0x00, 0x0B, 0xE8)           # byte 2: $2115 = $81
    a.op(0xA9, 0x04, 0x9D, 0x00, 0x0B, 0xE8)           # byte 3: size 4
    a.op(0x68)                           # PLA -> top tile
    a.op(0x48)                           # keep a copy for the bottom tile
    a.op(0x9D, 0x00, 0x0B, 0xE8)
    a.op(0xA9, 0x24, 0x9D, 0x00, 0x0B, 0xE8)
    a.op(0x68, 0x1A)                     # PLA -> top tile, +1 = bottom tile
    a.op(0x9D, 0x00, 0x0B, 0xE8)
    a.op(0xA9, 0x24, 0x9D, 0x00, 0x0B, 0xE8)
    a.op(0x8E, 0xDF, 0x09)               # STX $09DF
    a.op(0xEE, 0xE9, 0x03)               # INC $03E9 (consume the id byte; the
                                         # consumer consumes the prefix)
    a.long_to(0x01FA7A)                  # JML $03:FA7A (INC $036F / RTS)

    return a.done()


'''

start = src.index('def build_drawer_copy():')
end = src.index('def build_sanitize():')
src = src[:start] + NEW + src[end:]
src = src.replace('INSTRUMENT = True', 'INSTRUMENT = False')
assert 'INSTRUMENT = False' in src
open(PATH, 'w', encoding='utf-8').write(src)
print('spliced, INSTRUMENT off')

# sanity: the new drawer copy must contain no RTS and no RTL
import importlib, sys
sys.path.insert(0, 'C:/Users/<user>/.zcode/workspace/default/sfc-recon')
import cnbuild5
body = cnbuild5.build_drawer_copy()
print('drawer copy: %d bytes at ROM %06X' % (len(body), cnbuild5.E3_DRAWER))
print('  RTS bytes: %d   RTL bytes: %d   JML exits: %d'
      % (body.count(0x60), body.count(0x6B), body.count(0x5C) + body.count(0x22)))
print('  hex: ' + ' '.join('%02X' % b for b in body))