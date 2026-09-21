# -*- coding: utf-8 -*-
"""Fix the one byte code plumbing:

* the colouring may use every slot again -- a dynamic glyph may share a low slot
  with a one byte code glyph as long as the two never appear in one window, and
  pack_pool puts it on a page >= 1 (page 0 low slots belong to the codes)
* PAGES is bounded by the code space: $C5..$DF is 27 codes, each one byte code
  eats one of them, so PAGES + FIXED_N must stay <= 27
"""
import io
P = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/cnbuild5.py'
src = io.open(P, encoding='utf-8', newline='').read().replace('\r\n', '\n')

old = "            free = [s for s in range(FIXED_N, SLOTS) if s not in banned]"
assert src.count(old) == 1
src = src.replace(old, """            free = [s for s in range(SLOTS) if s not in banned]""")

old = """    PAGES = max(1, -(-len(enc.slot) // SLOTS))
    while True:
        try:
            enc.pack_pool()
            break
        except SystemExit:
            PAGES += 1
            if PAGES > 26:
                raise
            enc.cell, enc.order = {}, []"""
assert src.count(old) == 1
new = """    PAGES = max(1, -(-(len(enc.slot) - FIXED_N) // max(1, SLOTS - FIXED_N)))
    while True:
        try:
            enc.pack_pool()
            break
        except SystemExit:
            PAGES += 1
            if PAGES + FIXED_N > CODE_BUDGET:
                raise SystemExit(
                    'not enough codepoints: %d pages + %d one byte codes > %d '
                    '($C5..$DF); %d glyphs, %d slots'
                    % (PAGES, FIXED_N, CODE_BUDGET, len(enc.slot), SLOTS))
            enc.cell, enc.order = {}, []"""
src = src.replace(old, new)

old = "DRW_MODE = 0x0D48                       # drawer scratch: 0 two byte, 1 fixed"
assert src.count(old) == 1
src = src.replace(old, """DRW_MODE = 0x0D48                       # drawer scratch: 0 two byte, 1 fixed
CODE_BUDGET = 0xE0 - PREFIX0            # $C5..$DF: free codepoints""")

old = "FIXED_N = 8                             # how many of them (slots 0..N-1, page 0)"
assert src.count(old) == 1
src = src.replace(old, """FIXED_N = int(os.environ.get('FIXED_N', '4'))   # how many (slots 0..N-1, page 0)""")

assert src.count("    assert PAGES > 0") == 0
io.open(P, 'w', encoding='utf-8', newline='\n').write(src)
print('ok')