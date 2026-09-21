"""Stop storing extra line breaks: the drawer wraps over-long lines at runtime.

wrap_segments() inserted {F2F6} for every line that got too wide once Chinese is
counted as two cells (121 entries, 2 bytes each).  The drawer already replays the
F2 handler whenever a Chinese glyph would land past column 25, so those breaks
are printed at run time for free.  Dropping the stored ones buys back the text
space the terminator fix needed.
"""
import os
BASE = os.path.dirname(os.path.abspath(__file__))
p = os.path.join(BASE, 'cnbuild5.py')
src = open(p, encoding='utf-8').read()

old = """        # Chinese glyphs are two cells wide, so lines that were fine with kana
        # need extra in-box breaks.  Those may only be added after align_tokens().
        b = wrap_segments(a)
        if b != a:
            stats['wrapped'] += 1
        fixed[k] = b
"""
new = """        # Chinese glyphs are two cells wide, so lines that were fine with kana are
        # now too wide.  Storing a {F2F6} for each of them costs two bytes and we do
        # not have the room, so the drawer wraps those lines at run time instead (it
        # replays the F2 handler when a Chinese glyph would land past column 25).
        # wrap_segments() is still applied to count how many entries rely on that.
        b = wrap_segments(a)
        if b != a:
            stats['wrapped'] += 1
        fixed[k] = a
"""
assert src.count(old) == 1, src.count(old)
src = src.replace(old, new)

# report + safety: a line may only be wrapped by the drawer if the overflowing
# code is a Chinese one (the original drawer cannot wrap at all)
old2 = """    # width measured per prose run (between control tokens), which is what the
    # box actually shows on one line
"""
new2 = """    # The run-time wrapper only triggers on Chinese codes: for every entry check
    # that each line's overflow happens on a Chinese glyph, otherwise the original
    # drawer would drop the rest of that line.
    at_risk = []
    for k, v in fixed.items():
        col = 0
        for part in re.split(r'(\\{[0-9A-Fa-f]{2,4}\\})', v):
            if not part:
                continue
            m = TOKEN.fullmatch(part)
            if m:
                h = m.group(1)
                if len(h) & 1:
                    h = '0' + h
                bb = bytes.fromhex(h)
                if bb[0] == 0xF2:
                    col = 0                # newline / page break
                else:
                    col += cells_of_token(part)
                continue
            for ch in part:
                w = 1 if (ch == ' ' or ch in KEEP1) else 2
                if col + w > WRAP_COL + 1 and w == 1:
                    at_risk.append((k, ch, col))
                    break
                col += w
    if at_risk:
        print('   lines that overflow on a single-byte code: %d %s'
              % (len(at_risk), at_risk[:6]))

    # width measured per prose run (between control tokens), which is what the
    # box actually shows on one line
"""
assert src.count(old2) == 1, src.count(old2)
src = src.replace(old2, new2)
open(p, 'w', encoding='utf-8').write(src)
print('patched: stored breaks dropped, overflow risk reported')