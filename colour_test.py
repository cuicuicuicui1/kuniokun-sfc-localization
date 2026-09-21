# -*- coding: utf-8 -*-
"""How many slots does the co-occurrence colouring really need?

The box is wiped at every message entry, so only one message is on screen at a
time: the constraint is "characters that appear in the same message need
different slots".  Each message is therefore a clique, and the question is the
chromatic number of the union of those cliques.  Try several orderings.
"""
import itertools
import json
import random

import cnbuild5 as cb


def build_fixed():
    tr = json.load(open(cb.BASE + '/cn_translation.json', encoding='utf-8'))
    textrecs = json.load(open(cb.BASE + '/kuniokun_text.json', encoding='utf-8'))
    orig = {'%06X' % r['text_rom_off']: r['text'] for r in textrecs}
    tbl_of = {'%06X' % r['text_rom_off']: r['table_rom_off'] for r in textrecs}
    fixed = {}
    for k, v in tr.items():
        if tbl_of.get(k) in cb.NO_TRANSLATE:
            continue
        fixed[k] = cb.wrap_segments(cb.align_tokens(orig[k], cb.reflow(v)))
    cb.derive_keep1(fixed.values())
    return tr, textrecs, fixed


def windows_for(fixed, textrecs, win_main, win_list):
    per_table = {}
    for ti, (table_off, count) in enumerate(cb.TABLES):
        recs = sorted([r for r in textrecs if r['table_rom_off'] == table_off],
                      key=lambda r: r['index'])
        if table_off in cb.NO_TRANSLATE:
            per_table[ti] = []
            continue
        per_table[ti] = [cb.glyphs_of(fixed['%06X' % r['text_rom_off']]) for r in recs]
    windows = []
    for ti, gs in per_table.items():
        win = win_main if ti == 0 else win_list
        for i in range(len(gs)):
            u = set()
            for j in range(i, min(i + win, len(gs))):
                u |= gs[j]
            windows.append(u)
    return windows


windows_by_char = {}


def colour_with(windows_by_char, windows, nslots, order):
    slot = {}
    load = [0] * nslots
    for ch in order:
        banned = set()
        for w in windows_by_char.get(ch, ()):
            banned |= {slot[c] for c in w if c in slot}
        free = [s for s in range(nslots) if s not in banned]
        if not free:
            return None
        s = min(free, key=lambda x: (load[x], x))
        slot[ch] = s
        load[s] += 1
    return slot


tr, textrecs, fixed = build_fixed()
print('glyphs total: %d' % len(set().union(*[cb.glyphs_of(v) for v in fixed.values()]))
      if fixed else 0)

for win_main, win_list in ((1, 1), (1, 12), (2, 12)):
    ws = windows_for(fixed, textrecs, win_main, win_list)
    print('\nwin_main=%d win_list=%d: %d windows, widest %d'
          % (win_main, win_list, len(ws), max(len(w) for w in ws)))
    windows_by_char = {}
    for w in ws:
        for ch in w:
            windows_by_char.setdefault(ch, []).append(w)
    freq = {}
    for w in ws:
        for ch in w:
            freq[ch] = freq.get(ch, 0) + 1
    chars = sorted(freq, key=lambda c: (-freq[c], c))
    orders = {
        'freq-desc': chars,
        'freq-asc': chars[::-1],
        'alpha': sorted(freq),
    }
    rnd = list(chars)
    for seed in range(2):
        random.Random(seed).shuffle(rnd)
        orders['rnd%d' % seed] = list(rnd)
    for n in (39, 43, 53, 60):
        ok = []
        for name, order in orders.items():
            if colour(ws, n, order):
                ok.append(name)
        print('   %d slots: %s' % (n, ', '.join(ok) if ok else 'no ordering worked'))