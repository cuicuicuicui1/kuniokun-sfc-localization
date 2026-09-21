"""Fix the terminator-misplacement bug.

reflow() used to insert {F2F6} breaks *before* align_tokens().  align_tokens()
splits my prose at every token, so each break I added became a segment boundary
and the original's trailing {F2F3} got re-inserted at that boundary -- in the
middle of the sentence.  The engine's line loader stops dead at that $F3
(entry finished), so everything I wrote after it was never read: 78 entries had
a missing tail.  In-box breaks are added by wrap_segments() *after* alignment
instead, and {F2F6} continues the entry rather than ending it.
"""
import io, re, sys, os

BASE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- cnbuild5.py
p = os.path.join(BASE, 'cnbuild5.py')
src = open(p, encoding='utf-8').read()

old = """        w = reflow(v)
        if w != v:
            stats['changed'] += 1
        a = align_tokens(orig_text[k], w)
"""
new = """        # No line splitting before align_tokens(): a break inserted here is a
        # segment boundary for align_tokens(), which then drops the original's
        # trailing {F2F3} into the middle of the sentence -- and the loader stops
        # at the first $F3, so everything behind it is never read.  wrap_segments()
        # adds the in-box breaks after alignment instead ({F2F6} continues the).
        w = v
        if reflow(v) != v:
            stats['changed'] += 1
        a = align_tokens(orig_text[k], w)
"""
assert src.count(old) == 1, ('pipeline', src.count(old))
src = src.replace(old, new)

# reachability assertion + honest width report
old2 = """    over = [k for k, v in fixed.items()
            if any(ncells(l) > MAX_COL for l in v.replace('{F2F4}', '{F2F6}').split('{F2F6}'))]
    print('reflow: %d strings changed; %d aligned to the original control codes; '
          '%d needed extra line breaks; widest line %d cells, tallest page %d lines, '
          '%d entries still too wide; %d left in Japanese (item window)'
          % (stats['changed'], stats['aligned'], stats['wrapped'], stats['max_col'],
             stats['max_row'], len(over), stats['skipped']))
    if over:
        print('   too wide: %s' % over[:10])
"""
new2 = """    # Every byte behind the first $F3 of an entry is dead: the line loader stops
    # there and the message driver moves on.  Prose must never sit there.
    lost = []
    for k, v in fixed.items():
        img = bytearray()
        for part in re.split(r'(\\{[0-9A-Fa-f]{2,4}\\})', v):
            if not part:
                continue
            m = TOKEN.fullmatch(part)
            if m:
                h = m.group(1)
                if len(h) & 1:
                    h = '0' + h
                img += bytes.fromhex(h)
            else:
                img += b'\\x01' * len(part)      # one marker byte per prose char
        i = img.find(b'\\xf3')
        if i >= 0 and img[i + 1:].count(1):
            lost.append((k, bytes(img[i + 1:]).count(1)))
    assert not lost, ('text behind the entry terminator would never be read', lost[:10])

    # width measured per prose run (between control tokens), which is what the
    # box actually shows on one line
    over = []
    for k, v in fixed.items():
        for seg in re.split(r'\\{[0-9A-Fa-f]{2,4}\\}', v):
            if ncells(seg) > MAX_COL:
                over.append((k, ncells(seg)))
    print('text: %d strings reflowed; %d aligned to the original control codes; '
          '%d needed extra line breaks; widest prose run %d cells, tallest page %d lines, '
          '%d runs wider than the box; %d left in Japanese (item window)'
          % (stats['changed'], stats['aligned'], stats['wrapped'], stats['max_col'],
             stats['max_row'], len(over), stats['skipped']))
    if over:
        print('   too wide: %s' % over[:10])
"""
assert src.count(old2) == 1, ('report', src.count(old2))
src = src.replace(old2, new2)
open(p, 'w', encoding='utf-8').write(src)
print('cnbuild5.py patched')

# ---------------------------------------------------------------- verify16.py
p = os.path.join(BASE, 'verify16.py')
src = open(p, encoding='utf-8').read()
old3 = "cb.wrap_segments(cb.align_tokens(_orig_text[k], cb.reflow(v)))"
new3 = "cb.wrap_segments(cb.align_tokens(_orig_text[k], v))"
assert src.count(old3) == 1, ('verify', src.count(old3))
src = src.replace(old3, new3)
open(p, 'w', encoding='utf-8').write(src)
print('verify16.py patched')