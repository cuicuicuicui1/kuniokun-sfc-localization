"""Remove the stale duplicate B block in verify16.py (it treated byte ints as
(kind, ...) tuples and crashed with TypeError: 'int' object is not subscriptable)."""
import os
BASE = os.path.dirname(os.path.abspath(__file__))
p = os.path.join(BASE, 'verify16.py')
src = open(p, encoding='utf-8').read()

stale_start = """checked = 0
for r in recs:
    key = '%06X' % r['text_rom_off']
    checked += 1
    if key in NO_TR:
        off = r['text_rom_off']
        if rom[off:off + 2] != orig[off:off + 2]:
            fail('entry %s (japanese table) was modified' % key)
        elif _act(off) != _act(off, orig):
            fail('entry %s (japanese table) decodes differently' % key)
        elif any(t[0] == 'cn' for t in _act(off)):
            fail('entry %s (japanese table) contains Chinese glyphs' % key)
        continue
    if key not in addr:
        fail('entry %s has no rebuilt address' % key)
        continue
    want, got = _dec(fixed[key] if key in fixed else _orig_text[key]), _act(addr[key])
    if got != want:
        nm = min(len(got), len(want))
        k = next((i for i in range(nm) if got[i] != want[i]), nm)
        fail('entry %s mismatch at %d: got %s want %s'
             % (key, k, got[k:k + 4], want[k:k + 4]))
print('   %d entries decoded' % checked)
"""
assert src.count(stale_start) == 1, ('stale block', src.count(stale_start))
src = src.replace(stale_start, "print('   %d entries decoded' % checked)\n")
open(p, 'w', encoding='utf-8').write(src)
print('verify16.py: stale B block removed')