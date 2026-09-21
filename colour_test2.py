# -*- coding: utf-8 -*-
"""Which (list window, slot budget) combinations actually colour?"""
import random
import colset as ct

tr, textrecs, fixed = ct.data()
print('distinct glyphs: %d' % len(set().union(*[ct.cb.glyphs_of(v) for v in fixed.values()])))
for win_list in (1, 2, 3, 4, 5, 6, 8, 10, 12):
    ws = ct.windows_for(textrecs, fixed, 1, win_list)
    per_char = ct.per_char_of(ws)
    freq = {}
    for w in ws:
        for ch in w:
            freq[ch] = freq.get(ch, 0) + 1
    chars = sorted(freq, key=lambda c: (-freq[c], c))
    orders = {'freq': chars, 'asc': chars[::-1]}
    for seed in range(3):
        r = list(chars)
        random.Random(seed).shuffle(r)
        orders['r%d' % seed] = r
    res = []
    for n in (43, 48, 53, 60):
        ok = [k for k, o in orders.items() if ct.colour_with(per_char, n, o)]
        res.append('%d:%s' % (n, (','.join(ok[:2]) if ok else '-')))
    print('win_list=%-2d widest=%-3d  %s'
          % (win_list, max(len(w) for w in ws), '  '.join(res)))
