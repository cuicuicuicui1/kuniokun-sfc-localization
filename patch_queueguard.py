"""Replace the dead $9AB6 based guard with an explicit queue page bound check.

$009AB6 ends in CLC/RTL on both paths (verified by disassembly: pha / lda $09dd /
cmp $09df / beq clear / bcs clear / pla / clc / adc $09df / rtl), so a "bcs defer"
after it can never fire.  The queue page is $0B00-$0BFF and $09DF is the first
free byte, so a draw may stage a request of N bytes iff $09DF + N <= 0x100.
"""
import io

p = 'cnbuild5.py'
s = io.open(p, encoding='utf-8', newline='').read()

old_occ = """    a.hexs('AD 6F 03')                     # lda $036f
    a.rel(0xD0, 'occ0')                    # bne occ0: not the row's first cell
    a.hexs('A9 %02X' % (ROW_WIPE + 8))     # lda #120: the wipe and this character's
                                           # own cell entry
    a.hexs('22 B6 9A 00')                  # jsl $009ab6: room in the queue page?
    a.far_rel(0xB0, 'defer0', 'occw')      # bcs defer0: retry next frame
"""
new_occ = """    a.hexs('AD DF 09')                     # lda $09df (first free queue byte)
    a.hexs('C9 %02X' % (0x101 - 8))        # cmp #$f9: the original drawer stages 8
    a.far_rel(0xB0, 'defer0', 'occr')      # bcs defer0: no room, retry next frame
    a.hexs('AD 6F 03')                     # lda $036f
    a.rel(0xD0, 'occ0')                    # bne occ0: not the row's first cell
    a.hexs('AD DF 09 C9 %02X' % (0x101 - ROW_WIPE - 8))
                                           # lda $09df / cmp #$89: the row wipe
                                           # plus that 8 byte entry must fit
    a.far_rel(0xB0, 'defer0', 'occw')      # bcs defer0: retry next frame
"""

old_cn = """    a.hexs('AD 6F 03')                     # lda $036f
    a.rel(0xF0, 'g88')                     # beq g88
    a.hexs('C9 %02X' % WRAP_COL)           # cmp #WRAP_COL
    a.rel(0x90, 'g88')                     # bcc g88
    a.hexs('A9 %02X' % ROW_WIPE_CHECK)     # lda #200 (wipe + glyph)
    a.rel(0x80, 'gdone')                   # bra gdone
    a.label('g88')
    a.hexs('A9 %02X' % GLYPH_COST)         # lda #GLYPH_COST
    a.label('gdone')
    a.hexs('22 B6 9A 00')                  # jsl $009ab6: room in the queue page?
    a.far_rel(0xB0, 'defer', 'guard')      # bcs defer
"""
new_cn = """    a.hexs('AD 6F 03')                     # lda $036f
    a.rel(0xF0, 'gwide')                   # beq gwide: column zero, row wipe too
    a.hexs('C9 %02X' % WRAP_COL)           # cmp #WRAP_COL
    a.rel(0x90, 'g88')                     # bcc g88: only the glyph is staged
    a.label('gwide')
    a.hexs('AD DF 09 C9 %02X' % (0x101 - ROW_WIPE_CHECK))
                                           # lda $09df / cmp #$39: row wipe plus
                                           # glyph must fit in the queue page
    a.rel(0x80, 'gdone')                   # bra gdone
    a.label('g88')
    a.hexs('AD DF 09 C9 %02X' % (0x101 - GLYPH_COST))
                                           # lda $09df / cmp #$a9
    a.label('gdone')
    a.far_rel(0xB0, 'defer', 'guard')      # bcs defer: no room, retry next frame
"""

for old, new in ((old_occ, new_occ), (old_cn, new_cn)):
    assert s.count(old) == 1, (old[:60], s.count(old))
    s = s.replace(old, new)
io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('queue guards now bound $09DF directly')