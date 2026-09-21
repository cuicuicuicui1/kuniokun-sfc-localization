"""Decide: is dialogue rendered raw (macros drawn as boxes) or pre-expanded via $03EA buffer?"""
import re

d = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()


def lorom(off):
    return off // 0x8000, 0x8000 + (off % 0x8000)


def snes(off):
    b, a = lorom(off)
    return '$%02X:%04X' % (b, a)


def find(pat, name, limit=12):
    hits = [m.start() for m in re.finditer(re.escape(pat), d)]
    print('--- %-26s %s x%d' % (name, pat.hex(' '), len(hits)))
    for o in hits[:limit]:
        print('      %06X (%s) ctx: %s' % (o, snes(o),
              ' '.join('%02X' % x for x in d[max(0, o - 8):o + 6])))
    return hits


print('=== who calls the expander at $03:EBAF ? ===')
for pat, nm in ((bytes([0x20, 0xAF, 0xEB]), 'JSR $EBAF'),
                (bytes([0x22, 0xAF, 0xEB, 0x03]), 'JSL $03:EBAF'),
                (bytes([0x4C, 0xAF, 0xEB]), 'JMP $EBAF'),
                (bytes([0x20, 0xFC, 0xEB]), 'JSR $EBFC (macro dispatcher)'),
                (bytes([0x9C, 0x11, 0x00]), 'STZ $0011 (expander reset)')):
    find(pat, nm)

print()
print('=== who reads the expander output buffer $03EA ? ===')
for pat, nm in ((bytes([0xAD, 0xEA, 0x03]), 'LDA $03EA'),
                (bytes([0xBD, 0xEA, 0x03]), 'LDA $03EA,X'),
                (bytes([0xB9, 0xEA, 0x03]), 'LDA $03EA,Y'),
                (bytes([0xAD, 0xE8, 0x03]), 'LDA $03E8'),
                (bytes([0xAD, 0x11, 0x00]), 'LDA $0011'),
                (bytes([0xA5, 0x11]), 'LDA $11 (dp)')):
    find(pat, nm)

print()
print('=== who reads/writes the $036A/$036B source pointer ===')
for pat, nm in ((bytes([0xAD, 0x6A, 0x03]), 'LDA $036A'),
                (bytes([0x8D, 0x6A, 0x03]), 'STA $036A'),
                (bytes([0xAD, 0x6B, 0x03]), 'LDA $036B'),
                (bytes([0x8D, 0x6B, 0x03]), 'STA $036B')):
    find(pat, nm, limit=8)

print()
print('=== where is $036A/$036B initialised from a table pointer? (STA $036A near LDA tbl) ===')
for m in re.finditer(re.escape(bytes([0x8D, 0x6A, 0x03])), d):
    o = m.start()
    print('   %06X: %s' % (o, ' '.join('%02X' % x for x in d[o - 16:o + 8])))

print()
print('=== FA/FB table content check: what does code 0xE2 draw? ===')
FA = 0x01FA9E
FB = 0x01FB9E
for c in (0xE2, 0xEB, 0xED, 0xEE, 0xEF, 0xF0, 0xF4, 0xF6, 0xF7, 0xF8, 0xFF, 0x00, 0x09, 0x38, 0x39, 0x4C, 0x4E):
    print('   code 0x%02X -> FA=0x%02X FB=0x%02X' % (c, d[FA + c], d[FB + c]))