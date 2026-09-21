# -*- coding: utf-8 -*-
"""Lay out the code space properly.

$C0..$DF are 32 dead codepoints (nothing in the original ROM draws them: FA/FB
are the box glyph or leftover symbols, and no untranslated text uses them).
Layout: two byte prefixes grow up from PREFIX0, the one byte codes sit at the
top of the range, and the two must never overlap.

   $C0 .. PREFIX0+PAGES-1   two byte Chinese codes
   ...                      unused gap
   FIXED0 .. $DF            one byte Chinese codes

$C4 holds the original "ー" glyph and no longer needs protecting, so it leaves
KEEP1 (it would read as a prefix now).
"""
import io
P = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/cnbuild5.py'
s = io.open(P, encoding='utf-8', newline='').read().replace('\r\n', '\n')

old = """PREFIX0 = 0xC5
FIXED0 = 0xD2                           # one byte codes for frequent glyphs
FIXED_N = int(os.environ.get('FIXED_N', '4'))   # how many (slots 0..N-1, page 0)"""
assert s.count(old) == 1
s = s.replace(old, """PREFIX0 = 0xC0                       # first codepoint of the two byte codes
FIXED_N = int(os.environ.get('FIXED_N', '4'))   # one byte codes (slots 0..N-1, page 0)
FIXED0 = 0xE0 - FIXED_N                 # they sit at the top: $DC..$DF
# codepoints the engine never draws: FA/FB are the box glyph, no text uses them
NEVER_KEEP = {0xC0, 0xC1, 0xC2, 0xC3, 0xC4}""")

old = "CODE_BUDGET = 0xE0 - PREFIX0            # $C5..$DF: free codepoints"
assert s.count(old) == 1
s = s.replace(old, "CODE_BUDGET = FIXED0 - PREFIX0         # room for the two byte codes")

# derive_keep1: never keep a reserved codepoint
old = """        code = by_char[ch]
        if km.FA[code] in prot and km.FB[code] in prot:"""
assert s.count(old) == 1
s = s.replace(old, """        code = by_char[ch]
        if code in NEVER_KEEP:              # $C0..$C4 are prefixes now
            continue
        if km.FA[code] in prot and km.FB[code] in prot:""")

old = """            if PAGES + FIXED_N > CODE_BUDGET:"""
assert s.count(old) == 1
s = s.replace(old, """            if PAGES > CODE_BUDGET:""")
old = """                    'not enough codepoints: %d pages + %d one byte codes > %d '
                    '($C5..$DF); %d glyphs, %d slots'
                    % (PAGES, FIXED_N, CODE_BUDGET, len(enc.slot), SLOTS))"""
assert s.count(old) == 1
s = s.replace(old, """                    'not enough codepoints: %d pages > %d '
                    '($%02X..$%02X); %d glyphs, %d slots'
                    % (PAGES, CODE_BUDGET, PREFIX0, FIXED0 - 1,
                       len(enc.slot), SLOTS))""")

old = """    print('glyph slots: %d distinct, %d stored in %d pages of %d slots'
          % (len(enc.slot), len(enc.order), PAGES, SLOTS))"""
assert s.count(old) == 1
s = s.replace(old, """    assert PREFIX0 + PAGES <= FIXED0, (hex(PREFIX0 + PAGES), hex(FIXED0))
    print('glyph slots: %d distinct, %d stored in %d pages of %d slots '
          '(codes $%02X..$%02X, one byte $%02X..$DF)'
          % (len(enc.slot), len(enc.order), PAGES, SLOTS,
             PREFIX0, PREFIX0 + PAGES - 1, FIXED0))""")

# sanity: no reserved codepoint may appear in untranslated text
old = """    added = derive_keep1(fixed.values())"""
assert s.count(old) == 1
s = s.replace(old, """    _res = NEVER_KEEP & untranslated_codes()
    assert not _res, ('reserved codepoints appear in untranslated text: %s'
                      % sorted(_res))
    added = derive_keep1(fixed.values())""")

io.open(P, 'w', encoding='utf-8', newline='\n').write(s)
print('code layout patched')